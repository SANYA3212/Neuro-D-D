import random
import string
from fastapi import APIRouter, Depends, HTTPException

from server.core import storage
from server.core.models import Room, CreateRoomRequest, JoinRoomRequest, RoomResponse, UserProfileResponse
from server.api.auth import get_current_user_code

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

def get_player_profile(user_code: str) -> UserProfileResponse:
    """Helper to fetch a user's public profile."""
    profile_path = storage.get_user_profile_file(user_code)
    if not profile_path:
        return None # Or a default profile
    data = storage.read_json(profile_path)
    if not data:
        return None
    # Manually create the response model to ensure no sensitive data leaks
    return UserProfileResponse(**data)

@router.get("/{room_code}", response_model=RoomResponse)
async def get_room_details(room_code: str):
    """Gets the details of a specific room, including resolved player profiles."""
    all_rooms = storage.get_all_rooms()
    room_data = next((r for r in all_rooms if r['room_code'] == room_code.upper()), None)
    if not room_data:
        raise HTTPException(status_code=404, detail="Room not found")

    player_profiles = [get_player_profile(uc) for uc in room_data.get('players', [])]

    return RoomResponse(
        **room_data,
        players=[p for p in player_profiles if p is not None]
    )

@router.get("/public")
async def list_public_rooms():
    """
    Returns a list of all public rooms.
    """
    all_rooms = storage.get_all_rooms()
    public_rooms = [Room(**r) for r in all_rooms if r.get('is_public')]
    return public_rooms

@router.post("/join", response_model=RoomResponse)
async def join_room(
    request: JoinRoomRequest,
    user_code: str = Depends(get_current_user_code)
):
    """
    Allows a user to join an existing room.
    """
    all_rooms = storage.get_all_rooms()
    room_to_join_data = None

    for r in all_rooms:
        if r['room_code'] == request.room_code.upper():
            room_to_join_data = r
            break

    if not room_to_join_data:
        raise HTTPException(status_code=404, detail="Room not found")

    if user_code not in room_to_join_data['players']:
        room_to_join_data['players'].append(user_code)
        storage.write_all_rooms(all_rooms)

    # Fetch and return the full room details
    return await get_room_details(request.room_code)
