import random
import string
from fastapi import APIRouter, Depends, HTTPException

from server.core import storage
from server.core.models import Room, CreateRoomRequest, JoinRoomRequest, RoomResponse
from server.api.auth import get_current_user_code

router = APIRouter(prefix="/rooms", tags=["Rooms & Lobby"])

def generate_room_code(length: int = 4) -> str:
    """Generates a short, user-friendly, base36 room code (uppercase letters + digits)."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

@router.post("", response_model=RoomResponse)
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
        name=request.name,
        is_public=request.is_public,
        players=[user_code] # Host is the first player
    )

    all_rooms.append(new_room.dict())
    storage.write_all_rooms(all_rooms)

    return RoomResponse(room_code=new_room.room_code)

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
