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
    # Player connects
    await manager.connect(websocket, room_code)

    # 1. Send the full state to the connecting user
    initial_state = await get_room_details_logic(room_code)
    if initial_state:
        await websocket.send_json(jsonable_encoder(initial_state))

    # 2. Notify other users that a new player has joined
    profile = storage.get_user_profile_by_code(user_code)
    if profile:
        # We need to construct the PlayerInfo object similar to how get_room_details_logic does it
        all_rooms = storage.get_all_rooms()
        room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
        if room_data:
            room = Room(**room_data)
            hp = 100
            max_hp = 100
            energy = 100
            max_energy = 100
            inventory = []

            # If a campaign is running, get the real stats
            if room.campaign_id:
                meta = storage.get_campaign_meta(room.host_user_code, room.campaign_id)
                if meta and user_code in meta.player_states:
                    player_state = meta.player_states[user_code]
                    hp = player_state.hp
                    max_hp = player_state.max_hp
                    energy = player_state.energy
                    max_energy = player_state.max_energy
                    inventory = player_state.inventory

            player_info = PlayerInfo(
                user_code=profile.user_code,
                username=profile.username,
                avatar_url=profile.avatar_url,
                is_host=(profile.user_code == room.host_user_code),
                hp=hp,
                max_hp=max_hp,
                energy=energy,
                max_energy=max_energy,
                inventory=inventory
            )

            join_message = {"type": "player_joined", "player": jsonable_encoder(player_info)}
            await manager.broadcast(join_message, room_code, exclude=[websocket])

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "chat":
                text = data.get("text")
                if text:
                    # 1. Find the room and its associated campaign
                    all_rooms = storage.get_all_rooms()
                    room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                    if not room_data or not room_data.get('campaign_id'):
                        continue # Or send an error to the user

                    room = Room(**room_data)
                    campaign_id = room.campaign_id
                    host_user_code = room.host_user_code

                    # 2. Create the message object
                    new_message = Message(role=user_code, content=text)

                    # 3. Save the message to the campaign journal
                    journal_path = storage.get_campaign_journal_file(host_user_code, campaign_id)
                    if journal_path:
                        journal_data = storage.read_json(journal_path) or {}
                        journal = CampaignJournal(**journal_data)
                        journal.lobby_chat.append(new_message)
                        storage.write_json(journal_path, journal.dict())

                    # 4. Get sender's username for the broadcast message
                    sender_profile = storage.get_user_profile_by_code(user_code)
                    sender_name = sender_profile.username if sender_profile else "Unknown"

                    # 5. Broadcast the new message delta
                    broadcast_message = {
                        "type": "new_message",
                        "id": str(new_message.id),
                        "text": new_message.content,
                        "sender": sender_name,
                        "timestamp": new_message.timestamp.isoformat()
                    }
                    await manager.broadcast(broadcast_message, room_code)

            elif data.get("type") == "player_ready":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    is_ready = False
                    if user_code in room.ready_players:
                        room.ready_players.remove(user_code)
                        is_ready = False
                    else:
                        room.ready_players.append(user_code)
                        is_ready = True

                    # Save the change
                    for i, r in enumerate(all_rooms):
                        if r['room_code'] == room.room_code:
                            all_rooms[i] = room.dict()
                            break
                    storage.write_all_rooms(all_rooms)

                    # Broadcast the delta update
                    update_message = {
                        "type": "player_ready_changed",
                        "user_code": user_code,
                        "is_ready": is_ready
                    }
                    await manager.broadcast(update_message, room_code)

            elif data.get("type") == "start_game":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data and room_data.get('host_user_code') == user_code:
                    # Only the host can start the game
                    await manager.broadcast({"type": "game_starting"}, room_code)


    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # The user is already gone from the connection manager at this point.
        # We just need to notify the other clients.

        # First, update the canonical list of players in storage.
        storage.remove_player_from_room(room_code, user_code)

        # Then, broadcast the delta update to the remaining clients.
        leave_message = {"type": "player_left", "user_code": user_code}
        await manager.broadcast(leave_message, room_code)
