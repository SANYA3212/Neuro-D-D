import re
import json
import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException

from server.core import config, storage
from server.core.connections import manager
from server.core.models import (
    AICompleteRequest, AICompleteResponse, Message, CampaignMeta, GameItem
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


@router.post("/complete", response_model=AICompleteResponse)
async def get_ai_completion(
    request: AICompleteRequest,
    user_code: str = Depends(get_current_user_code)
):
    """
    Generates a response from the AI Dungeon Master.
    """
    if not config.GEMINI_API_KEY or config.GEMINI_API_KEY == "__PUT_YOUR_KEY_HERE__":
        raise HTTPException(
            status_code=500,
            detail="Gemini API key is not configured on the server."
        )

    # 1. Gather context
    profile = storage.get_user_profile_by_code(user_code)
    if not profile:
        raise HTTPException(status_code=404, detail="User profile not found.")

    campaign_meta_data = storage.read_json(storage.get_campaign_meta_file(user_code, request.campaign_id))
    if not campaign_meta_data:
        raise HTTPException(status_code=404, detail="Campaign not found.")
    campaign_meta = CampaignMeta(**campaign_meta_data)
    user_settings = await get_user_settings(user_code)

    try:
        with open(config.SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="System prompt file not found.")

    # 2. Construct the prompt
    # The user already sends the message history, we just prepend the system prompt
    # and provide context variables.
    full_prompt_context = f"""
{system_prompt}

---
## Game Context
- Player Name: {profile.username}
- Campaign Name: {campaign_meta.name}
- Tone: {campaign_meta.tone}
- Difficulty: {campaign_meta.difficulty}
- Language: {request.language or user_settings.language}
- Last Dice Roll: {request.last_dice_roll if request.last_dice_roll else 'N/A'}
---
"""

    # Combine system prompt with the message history
    messages_for_ai = [{"role": "system", "content": full_prompt_context}]

    # Convert our Pydantic Message models to dicts for the AI
    for msg in request.messages:
        # The Gemini API uses 'model' for the assistant's role
        role = "model" if msg.role == "assistant" else msg.role
        messages_for_ai.append({"role": role, "parts": [msg.content]})

    # 3. Call Gemini API
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        model = genai.GenerativeModel(config.GEMINI_MODEL)

        # The API expects role/parts format. We need to adapt.
        # Let's reformat the messages for the `generate_content` method
        formatted_messages = []
        for msg in request.messages:
            role = "model" if msg.role == "assistant" else msg.role
            formatted_messages.append({'role': role, 'parts': [msg.content]})

        # The last message is the user's prompt, the history is the preceding messages
        # The library wants a history list and a final prompt.
        history = formatted_messages[:-1]
        prompt = formatted_messages[-1]['parts'][0]

        # Let's build a simpler message list, as the `chat` approach is tricky
        # The `generate_content` method can take a simple list of strings/parts
        final_prompt_list = [full_prompt_context]
        for msg in request.messages:
            final_prompt_list.append(f"**{msg.role.capitalize()}:** {msg.content}")

        print("--- FINAL PROMPT TO AI ---")
        print("\n".join(final_prompt_list))
        print("--------------------------")

        response = model.generate_content("\n".join(final_prompt_list))

        # 4. Parse and process response
        parsed_response = parse_ai_response(response.text)
        meta = parsed_response.meta

        if meta:
            state_changed = False
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
                storage.update_campaign_meta(campaign_meta.host_user_code, str(campaign_meta.id), campaign_meta.dict())

                # Find the room and broadcast the update
                room = storage.find_room_by_campaign_id(str(campaign_meta.id))
                if room:
                    updated_room_details = await get_room_details_logic(room['room_code'])
                    if updated_room_details:
                        await manager.broadcast(updated_room_details.dict(), room['room_code'])

        return parsed_response

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=503, detail=f"An error occurred with the AI service: {str(e)}")

# We can remove get_campaign_details as we are now reading the file directly
from server.api.users import get_user_settings
