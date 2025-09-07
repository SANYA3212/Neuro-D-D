from typing import Dict, Any, Optional
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder

from server.core import storage
from server.core.models import (
    Room, RoomDetailsResponse, PlayerInfo, CampaignMeta, Message, CampaignJournal, PlayerState
)

async def get_room_details_logic(room_code: str) -> Optional[RoomDetailsResponse]:
    """
    A reusable function to get all details for a room.
    It fetches the room, the campaign state, and enriches player data.
    Returns None if the room doesn't exist.
    """
    all_rooms = storage.get_all_rooms()
    room_data = next((r for r in all_rooms if r['room_code'] == room_code.upper()), None)

    if not room_data:
        return None

    room = Room(**room_data)

    # Load campaign meta and journal if it exists
    campaign_meta = None
    journal = None
    if room.campaign_id:
        # The host's user_code is needed to find the campaign files
        host_user_code = room.host_user_code
        meta_path = storage.get_campaign_meta_file(host_user_code, room.campaign_id)
        journal_path = storage.get_campaign_journal_file(host_user_code, room.campaign_id)

        if meta_path and journal_path:
            meta_data = storage.read_json(meta_path)
            journal_data = storage.read_json(journal_path)
            if meta_data:
                campaign_meta = CampaignMeta(**meta_data)
            if journal_data:
                journal = CampaignJournal(**journal_data)

    player_profiles = []
    if campaign_meta:
        for player_code in room.players:
            profile = storage.get_user_profile_by_code(player_code)
            if profile:
                player_state = campaign_meta.player_states.get(player_code)
                if not player_state:
                    player_state = PlayerState() # Create default if not exists

                player_profiles.append(
                    PlayerInfo(
                        user_code=profile.user_code,
                        username=profile.username,
                        avatar_url=profile.avatar_url,
                        is_host=(profile.user_code == room.host_user_code),
                        hp=player_state.hp,
                        max_hp=player_state.max_hp,
                        inventory=player_state.inventory
                    )
                )

    return RoomDetailsResponse(
        room_code=room.room_code,
        host_user_code=room.host_user_code,
        name=room.name,
        is_public=room.is_public,
        created_at=room.created_at,
        players=player_profiles,
        ready_players=room.ready_players,
        journal=journal
    )
