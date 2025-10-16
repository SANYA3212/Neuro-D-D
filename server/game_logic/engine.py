from typing import Optional
from fastapi.encoders import jsonable_encoder

from server.core import storage
from server.core.models import (
    Room, RoomDetailsResponse, PlayerInfo, CampaignMeta, CampaignJournal, PlayerState
)

async def get_room_details_logic(room_code: str) -> Optional[RoomDetailsResponse]:
    """
    A reusable function to get all details for a room.
    It fetches the room, the campaign state, and enriches player data.
    This function is critical for state synchronization.
    Returns None if the room doesn't exist.
    """
    all_rooms = storage.get_all_rooms()
    room_data = next((r for r in all_rooms if r['room_code'] == room_code.upper()), None)

    if not room_data:
        return None

    room = Room(**room_data)

    # Load campaign meta and journal if a campaign is associated with the room
    campaign_meta = None
    journal = None
    if room.campaign_id:
        host_user_code = room.host_user_code
        meta_path = storage.get_campaign_meta_file(host_user_code, room.campaign_id)
        if meta_path:
            meta_data = storage.read_json(meta_path)
            if meta_data:
                campaign_meta = CampaignMeta(**meta_data)

        journal_path = storage.get_campaign_journal_file(host_user_code, room.campaign_id)
        if journal_path:
            journal_data = storage.read_json(journal_path)
            if journal_data:
                journal = CampaignJournal(**journal_data)

    # --- THIS IS THE REWORKED LOGIC ---
    # Always iterate through players. Conditionally access campaign data inside the loop.
    player_profiles = []
    for player_code in room.players:
        profile = storage.get_user_profile_by_code(player_code)
        if not profile:
            continue # Skip if profile not found for some reason

        hp = 100
        max_hp = 100
        inventory = []
        effects = []

        # Get player-specific state only if a campaign exists
        if room.campaign_id:
            player_state = storage.get_player_state(room.host_user_code, room.campaign_id, player_code)
            if player_state:
                hp = player_state.hp
                max_hp = player_state.max_hp
                inventory = player_state.inventory
                effects = player_state.effects

        player_profiles.append(
            PlayerInfo(
                user_code=profile.user_code,
                username=profile.username,
                avatar_url=profile.avatar_url,
                is_host=(profile.user_code == room.host_user_code),
                hp=hp,
                max_hp=max_hp,
                inventory=inventory,
                effects=effects
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
        ready_players_turn=room.ready_players_turn,
        player_turns=room.player_turns,
        campaign_id=room.campaign_id,
        campaign_meta=campaign_meta,
        journal=journal
    )
