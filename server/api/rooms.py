import random
import string
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

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

    # Add player to room if not already in it
    if user_code not in room.players:
        room.players.append(user_code)
        # Find the room in the original list and update it
        for i, r in enumerate(all_rooms):
            if r['room_code'] == room.room_code:
                all_rooms[i] = room.dict()
                break
        storage.write_all_rooms(all_rooms)

    # If the room is part of a campaign, initialize player state (HP)
    if room.campaign_id:
        # The campaign is owned by the host, so we need their user_code to find it
        host_user_code = room.host_user_code
        meta_path = storage.get_campaign_meta_file(host_user_code, room.campaign_id)
        if meta_path:
            meta_data = storage.read_json(meta_path)
            if meta_data:
                campaign_meta = CampaignMeta(**meta_data)
                # If player is not in the campaign, add them with default state
                if user_code not in campaign_meta.player_states:
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
        # Announce the user joined by broadcasting the new room state
        room_details = await get_room_details_logic(room_code)
        if room_details:
            await manager.broadcast(room_details.dict(), room_code)

        while True:
            data = await websocket.receive_json()
            if data.get("type") == "chat":
                profile = storage.get_user_profile_by_code(user_code)
                username = profile.username if profile else "Unknown"

                new_message = Message(role=user_code, content=data.get("text", "")) # Use user_code as role for identification

                # --- Save chat message to journal ---
                room_data = next((r for r in storage.get_all_rooms() if r['room_code'] == room_code), None)

                if room_data and room_data.get("campaign_id"):
                    campaign_id = room_data["campaign_id"]
                    host_user_code = room_data["host_user_code"]
                    journal_path = storage.get_campaign_journal_file(host_user_code, campaign_id)

                    if journal_path:
                        journal_data = storage.read_json(journal_path)
                        if journal_data is not None:
                            journal = CampaignJournal(**journal_data)
                            journal.lobby_chat.append(new_message)
                            storage.write_json(journal_path, journal.dict())

                # --- Broadcast message to all clients ---
                await manager.broadcast(
                    {
                        "type": "new_message",
                        "id": str(uuid.uuid4()),
                        "timestamp": new_message.timestamp.isoformat() + "Z",
                        "sender": username,
                        "text": new_message.content
                    },
                    room_code
                )

            elif data.get("type") == "player_ready":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    if user_code in room.ready_players:
                        room.ready_players.remove(user_code)
                    else:
                        room.ready_players.append(user_code)

                    # Update the room in storage
                    for i, r in enumerate(all_rooms):
                        if r['room_code'] == room.room_code:
                            all_rooms[i] = room.dict()
                            break
                    storage.write_all_rooms(all_rooms)

                    # Broadcast the change
                    updated_room_details = await get_room_details_logic(room.room_code)
                    if updated_room_details:
                        await manager.broadcast(updated_room_details.dict(), room.room_code)

            elif data.get("type") == "start_game":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    # Check if the sender is the host and everyone is ready
                    if user_code == room.host_user_code and set(room.players) == set(room.ready_players):
                        await manager.broadcast({"type": "game_starting"}, room.room_code)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # Remove player from the room data and broadcast the update
        storage.remove_player_from_room(room_code, user_code)
        # Broadcast the new state to the remaining players
        updated_room_details = await get_room_details_logic(room_code)
        if updated_room_details:
            await manager.broadcast(updated_room_details.dict(), room_code)
