import random
import string
from fastapi import APIRouter, Depends, HTTPException

from server.core import storage
from server.core.models import Room, CreateRoomRequest, JoinRoomRequest, RoomResponse, RoomDetailsResponse
from server.api.auth import get_current_user_code
from server.game_logic.engine import get_room_details_logic
from server.core.connections import manager
from fastapi import WebSocket, WebSocketDisconnect
import uuid

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
        players=[user_code] # Host is the first player
    )

    all_rooms.append(new_room.dict())
    storage.write_all_rooms(all_rooms)

    return new_room

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
                new_message = Message(role=user_code, content=data.get("text", ""))

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

                await manager.broadcast({
                    "type": "new_message",
                    "id": str(uuid.uuid4()),
                    "timestamp": new_message.timestamp.isoformat() + "Z",
                    "sender": username,
                    "text": new_message.content
                }, room_code)

            elif data.get("type") == "player_ready":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    if user_code in room.ready_players:
                        room.ready_players.remove(user_code)
                    else:
                        room.ready_players.append(user_code)

                    for i, r in enumerate(all_rooms):
                        if r['room_code'] == room.room_code:
                            all_rooms[i] = room.dict()
                            break
                    # This is the critical fix: persist the state change.
                    storage.write_all_rooms(all_rooms)

                    updated_room_details = await get_room_details_logic(room.room_code)
                    if updated_room_details:
                        await manager.broadcast(updated_room_details.dict(), room.room_code)

            elif data.get("type") == "start_game":
                all_rooms = storage.get_all_rooms()
                room_data = next((r for r in all_rooms if r['room_code'] == room_code), None)
                if room_data:
                    room = Room(**room_data)
                    if user_code == room.host_user_code and set(room.players) == set(room.ready_players) and len(room.players) > 0:
                        await manager.broadcast({"type": "game_starting"}, room.room_code)

    except WebSocketDisconnect:
        manager.disconnect(websocket, room_code)
        # Remove player from the room data and broadcast the update
        storage.remove_player_from_room(room_code, user_code)
        # Broadcast the new state to the remaining players
        updated_room_details = await get_room_details_logic(room_code)
        if updated_room_details:
            await manager.broadcast(updated_room_details.dict(), room_code)

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
    """
    Allows a user to join an existing room.
    """
    all_rooms = storage.get_all_rooms()
    room_to_join = None

    for r in all_rooms:
        if r['room_code'] == request.room_code.upper():
            room_to_join = r
            break

    if not room_to_join:
        raise HTTPException(status_code=404, detail="Room not found")

    if user_code not in room_to_join['players']:
        room_to_join['players'].append(user_code)
        storage.write_all_rooms(all_rooms)

    return {"message": "Successfully joined room", "room_code": request.room_code.upper()}
