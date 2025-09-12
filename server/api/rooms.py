import random
import string
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from server.core import storage
from server.core.connections import manager
from server.core.models import (
    Room, CreateRoomRequest, JoinRoomRequest, RoomDetailsResponse, PlayerInfo,
    CampaignMeta, PlayerState, CampaignJournal, Message
)
from server.api.auth import get_current_user_code
from server.game_logic.engine import get_room_details_logic

router = APIRouter(prefix="/rooms", tags=["Rooms & Lobby"])

def generate_room_code(length: int = 4) -> str:
    """Generates a short, user-friendly, base36 room code (uppercase letters + digits)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@router.post("", response_model=Room)
async def create_room(
    request: CreateRoomRequest,
    user_code: str = Depends(get_current_user_code)
):
    """
    Creates a new game room. The creator becomes the host.
    """
    all_rooms = storage.get_all_rooms()

    # Generate a unique room code
    while True:
        room_code = generate_room_code()
        if not any(r['room_code'] == room_code for r in all_rooms):
            break

    new_room = Room(
        room_code=room_code,
        host_user_code=user_code,
        name=request.name or f"Room {room_code}",
        is_public=request.is_public,
        players=[user_code], # Host is the first player
        campaign_id=request.campaign_id
    )

    all_rooms.append(new_room.dict())
    storage.write_all_rooms(all_rooms)
    return new_room

@router.get("/public")
async def list_public_rooms():
    """
    Returns a list of all public rooms.
    """
    all_rooms = storage.get_all_rooms()
    public_rooms = [Room(**r) for r in all_rooms if r.get('is_public')]
    return public_rooms

@router.post("/join")
async def join_room(
    request: JoinRoomRequest,
    user_code: str = Depends(get_current_user_code)
):
    """Allows a user to join an existing room and initializes their campaign state."""
    all_rooms = storage.get_all_rooms()
    room_to_join_data = next((r for r in all_rooms if r['room_code'] == request.room_code.upper()), None)

    if not room_to_join_data:
        raise HTTPException(status_code=404, detail="Room not found")

    room = Room(**room_to_join_data)

    if user_code not in room.players:
        room.players.append(user_code)
        for i, r in enumerate(all_rooms):
            if r['room_code'] == room.room_code:
                all_rooms[i] = room.dict()
                break
        storage.write_all_rooms(all_rooms)

    if room.campaign_id:
        host_user_code = room.host_user_code
        campaign_meta = storage.get_campaign_meta(host_user_code, room.campaign_id)
        if campaign_meta and user_code not in campaign_meta.player_states:
            campaign_meta.player_states[user_code] = PlayerState()
            storage.update_campaign_meta(host_user_code, room.campaign_id, campaign_meta.dict())

    return {"message": "Successfully joined room", "room_code": request.room_code.upper()}


@router.get("/{room_code}", response_model=RoomDetailsResponse)
async def get_room_details(room_code: str):
    """Gets the details of a specific room, including player profiles."""
    details = await get_room_details_logic(room_code)
    if not details:
        raise HTTPException(status_code=404, detail="Room not found")
    return details


@router.websocket("/ws/{room_code}/{user_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_code: str):
    """WebSocket endpoint for real-time communication within a room."""
    await manager.connect(websocket, room_code)
    try:
        room_details = await get_room_details_logic(room_code)
        if room_details:
            await manager.broadcast(jsonable_encoder(room_details), room_code)

        while True:
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                # ... (Chat logic will be verified later)
                pass

            elif data.get("type") == "player_ready":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    if user_code in room.ready_players:
                        room.ready_players.remove(user_code)
                    else:
                        room.ready_players.append(user_code)

                    print(f"DEBUG: Toggled ready status for {user_code}. New ready list: {room.ready_players}")

                    for i, r in enumerate(all_rooms):
                        if r['room_code'] == room.room_code:
                            all_rooms[i] = room.dict()
                            break
                    storage.write_all_rooms(all_rooms)
                    print(f"DEBUG: Saved updated rooms file.")

                    updated_room_details = await get_room_details_logic(room.room_code)
                    if updated_room_details:
                        print(f"DEBUG: Broadcasting update. Ready players in broadcast: {updated_room_details.ready_players}")
                        await manager.broadcast(jsonable_encoder(updated_room_details), room.room_code)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        storage.remove_player_from_room(room_code, user_code)
        updated_room_details = await get_room_details_logic(room_code)
        if updated_room_details:
            await manager.broadcast(jsonable_encoder(updated_room_details), room_code)
