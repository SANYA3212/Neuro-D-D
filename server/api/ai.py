import re
import json
import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException, Body

from server.core import config, storage
from server.core.connections import manager
from server.core.models import (
    AICompleteRequest, AICompleteResponse, Message, CampaignMeta, GameItem, CampaignJournal
)
from server.api.auth import get_current_user_code
from server.game_logic.engine import get_room_details_logic

router = APIRouter(prefix="/ai", tags=["AI"])

def parse_ai_response(response_text: str) -> AICompleteResponse:
    """
    Parses the raw text from the AI, separating the narrative
    from the structured JSON metadata block.
    """
    json_block_match = re.search(r"```json\n({.*?})\n```", response_text, re.DOTALL)

    text_content = response_text
    meta_data = None

    if json_block_match:
        json_str = json_block_match.group(1)
        text_content = response_text.replace(json_block_match.group(0), "").strip()
        try:
            meta_data = json.loads(json_str)
        except json.JSONDecodeError:
            print(f"Warning: Failed to parse JSON metadata from AI response: {json_str}")
            meta_data = {"error": "failed_to_parse_json"}

    return AICompleteResponse(text=text_content, meta=meta_data)


async def _get_ai_completion_logic(room_code: str, user_code: str):
    """
    Processes the collected player turns for a room, sends them to the AI,
    and returns the AI's response.
    """
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "__PUT_YOUR_KEY_HERE__":
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured on the server."
        )
    if not config.GEMINI_MODEL:
        raise HTTPException(
            status_code=500,
            detail="Gemini model is not configured on the server."
        )

    # 1. Gather context from the room state
    room = storage.find_room_by_code(room_code)
    if not room or not room.get('campaign_id'):
        raise HTTPException(status_code=404, detail="Room or campaign not found.")

    campaign_id = room['campaign_id']
    host_user_code = room['host_user_code']

    campaign_meta = storage.get_campaign_meta(host_user_code, campaign_id)
    if not campaign_meta:
        raise HTTPException(status_code=404, detail="Campaign not found.")

    player_turns = room.get('player_turns', {})
    if not player_turns:
        raise HTTPException(status_code=400, detail="No player turns to process.")

    try:
        with open(config.SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="System prompt file not found.")

    # 2. Construct the prompt from all player turns
    turn_summary = []
    for player_code, turn_data in player_turns.items():
        player_profile = storage.get_user_profile_by_code(player_code)
        player_name = player_profile.username if player_profile else "Unknown Player"
        action = turn_data.get('action', 'does nothing.')
        dice_roll = turn_data.get('dice_roll')
        roll_str = ""
        if dice_roll and isinstance(dice_roll, dict):
            roll_str = f" (бросок d{dice_roll.get('sides')} → {dice_roll.get('result')})"

        turn_summary.append(f"- **{player_name}**: {action}{roll_str}")

    full_prompt_context = f"""
{system_prompt}

---
## Game Context
- Campaign Name: {campaign_meta.name}
- Tone: {campaign_meta.tone}
- Difficulty: {campaign_meta.difficulty}
---
## Player Actions This Turn:
{chr(10).join(turn_summary)}
---
"""
    # Get the last 20 messages from the journal to use as history
    journal = storage.get_campaign_journal(host_user_code, campaign_id)
    history = journal.entries[-20:] if journal else []

    messages_for_ai = [Message(role="system", content=full_prompt_context)] + history

    # 3. Call Gemini API
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)

        final_prompt_list = [full_prompt_context]
        for msg in history:
             final_prompt_list.append(f"**{msg.role.capitalize()}:** {msg.content}")

        response = model.generate_content("\n".join(final_prompt_list))

        # After getting a response, clear the turn data for the next round
        storage.clear_turn_data(room_code)

        # 4. Parse and process response
        parsed_response = parse_ai_response(response.text)
        meta = parsed_response.meta
        state_changed = False
        return parsed_response

        # --- Persist AI response to journal ---
        # This is critical for synchronization, as it saves the AI's narrative.
        journal_path = storage.get_campaign_journal_file(campaign_meta.host_user_code, str(campaign_meta.id))
        journal_data = storage.read_json(journal_path)
        if journal_data is not None:
            journal = CampaignJournal(**journal_data)

            # Add user's message to journal
            journal.entries.append(request.messages[-1])

            # Add AI's message to journal
            assistant_message = Message(role='assistant', content=parsed_response.text)
            journal.entries.append(assistant_message)

            storage.write_json(journal_path, journal.dict())
            state_changed = True # The journal state has changed, so we must broadcast.
        else:
            print(f"WARNING: Could not find journal to save AI response for campaign {campaign_meta.id}")


        if meta:
            # Handle HP changes
            hp_change = meta.get("hp_change")
            if isinstance(hp_change, int):
                player_state = campaign_meta.player_states.get(user_code)
                if player_state:
                    player_state.hp = max(0, player_state.hp + hp_change)
                    state_changed = True

            # Handle adding item to inventory
            item_data = meta.get("add_to_inventory")
            if isinstance(item_data, dict):
                player_state = campaign_meta.player_states.get(user_code)
                if player_state:
                    # Make sure we don't add duplicate items if the AI makes a mistake
                    if not any(item.name == item_data.get("name") for item in player_state.inventory):
                        new_item = GameItem(**item_data)
                        player_state.inventory.append(new_item)
                        state_changed = True

        if state_changed:
            # Save the metadata changes (HP, inventory)
            storage.update_campaign_meta(campaign_meta.host_user_code, str(campaign_meta.id), campaign_meta.dict())

            # Find the room and broadcast the all-inclusive update
            room = storage.find_room_by_campaign_id(str(campaign_meta.id))
            if room:
                print(f"BROADCASTING state update to room {room['room_code']} due to state change.")
                updated_room_details = await get_room_details_logic(room['room_code'])
                if updated_room_details:
                    await manager.broadcast(updated_room_details.dict(), room['room_code'])

        return parsed_response

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=503, detail=f"An error occurred with the AI service: {str(e)}")

# We can remove get_campaign_details as we are now reading the file directly
from server.api.users import get_user_settings
