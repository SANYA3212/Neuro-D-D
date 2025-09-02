from typing import Dict, Any, Optional
from fastapi import HTTPException

from server.core import storage
from server.core.models import (
    Room, RoomDetailsResponse, PlayerInfo, CampaignMeta
)

# This is a placeholder for the main game engine logic.
# In a more complex implementation, this engine would manage state,
# process events, and interact with the AI and storage layers.

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
        meta_path = storage.get_campaign_meta_file(room.host_user_code, room.campaign_id)
        journal_path = storage.get_campaign_journal_file(room.host_user_code, room.campaign_id)
        if meta_path and journal_path:
            meta_data = storage.read_json(meta_path)
            journal_data = storage.read_json(journal_path)
            if meta_data:
                campaign_meta = CampaignMeta(**meta_data)
            if journal_data:
                journal = CampaignJournal(**journal_data)

    player_profiles = []
    for player_code in room.players:
        profile = storage.get_user_profile_by_code(player_code)
        if profile:
            player_state = campaign_meta.player_states.get(player_code) if campaign_meta else None

            player_profiles.append(
                PlayerInfo(
                    user_code=profile.user_code,
                    username=profile.username,
                    avatar_url=profile.avatar_url,
                    is_host=(profile.user_code == room.host_user_code),
                    hp=player_state.hp if player_state else 20,
                    max_hp=player_state.max_hp if player_state else 20,
                    inventory=player_state.inventory if player_state else []
                )
            )

    return RoomDetailsResponse(
        room_code=room.room_code,
        host_user_code=room.host_user_code,
        name=room.name,
        is_public=room.is_public,
        created_at=room.created_at,
        players=player_profiles,
        journal=journal
    )

def process_player_action(
    action: Message,
    campaign_meta: CampaignMeta,
    campaign_journal: list[Message],
    user_settings: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Processes a player's action, prepares the context for the AI,
    and returns the data needed for the AI completion call.

    This function will be the bridge between the API layer and the AI call.
    """

    # 1. Prepare context for the AI
    #    - Get system prompt
    #    - Get recent journal entries
    #    - Format everything into a list of messages

    # 2. (Optional) Perform game rule checks based on the action
    #    - e.g., if action is "I attack the goblin", roll dice here.

    # 3. Call the AI completion service
    #    - This will be handled in the API layer for now (api/ai.py)

    # 4. Process the AI's response
    #    - Parse structured data
    #    - Update journal

    # For now, this is just a placeholder. The logic will be built out
    # in the api/ai.py file initially.

    print(f"Engine processing action for campaign {campaign_meta.id}: {action.content}")

    # This function would return the context payload for the AI
    return {
        "messages": campaign_journal + [action],
        "context": {
            "tone": campaign_meta.tone,
            "difficulty": campaign_meta.difficulty,
            "language": user_settings.get("language", "en")
        }
    }
