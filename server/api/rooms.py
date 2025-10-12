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
        ready_players=[], # Initialize empty ready list
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


async def broadcast_full_room_state(room_code: str):
    """Fetches the full room state and broadcasts it to all clients in the room."""
    updated_state = await get_room_details_logic(room_code)
    if updated_state:
        await manager.broadcast(jsonable_encoder(updated_state), room_code)

@router.websocket("/ws/{room_code}/{user_code}")
async def websocket_endpoint(websocket: WebSocket, room_code: str, user_code: str):
    """WebSocket endpoint for real-time communication within a room."""
    await manager.connect(websocket, room_code)

    # 1. Send the full state to the connecting user
    initial_state = await get_room_details_logic(room_code)
    if initial_state:
        await websocket.send_json(jsonable_encoder(initial_state))

    # 2. Notify all users (including the new one) of the updated player list
    await broadcast_full_room_state(room_code)

    try:
        while True:
            data = await websocket.receive_json()
            action_taken = False

            if data.get("type") == "chat":
                text = data.get("text")
                if text:
                    room = storage.find_room_by_code(room_code)
                    if room and room.get('campaign_id'):
                        campaign_id = room['campaign_id']
                        host_user_code = room['host_user_code']
                        new_message = Message(role=user_code, content=text)
                        storage.add_lobby_chat_message(host_user_code, campaign_id, new_message)
                        action_taken = True

            elif data.get("type") == "player_ready":
                storage.toggle_player_ready(room_code, user_code)
                action_taken = True

            elif data.get("type") == "start_game":
                room = storage.find_room_by_code(room_code)
                if room and room.get('host_user_code') == user_code:
                    # We don't need to persist anything, just notify clients to change page
                    await manager.broadcast({"type": "game_starting"}, room_code)

            if action_taken:
                # If any state-changing action was taken, broadcast the new canonical state
                await broadcast_full_room_state(room_code)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # Remove player from the room's list in storage
        storage.remove_player_from_room(room_code, user_code)
        # Broadcast the updated state to the remaining clients
        await broadcast_full_room_state(room_code)
