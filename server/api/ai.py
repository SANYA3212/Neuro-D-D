import re
import json
import google.generativeai as genai
from fastapi import APIRouter, Depends, HTTPException

from server.core import config, storage
from server.core.models import AICompleteRequest, AICompleteResponse, Message
from server.api.auth import get_current_user_code, get_current_user

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
    campaign_details = await get_campaign_details(request.campaign_id, user_code)
    user_settings = await get_user_settings(user_code)

    try:
        with open(config.SYSTEM_PROMPT_FILE, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="System prompt file not found.")

    # Determine which language to use: from the request or fallback to user settings
    language_to_use = request.language or user_settings.language

    # 2. Construct the prompt
    # The user already sends the message history, we just prepend the system prompt
    # and provide context variables.
    full_prompt_context = f"""
{system_prompt}

---
## Game Context
- Campaign Name: {campaign_details.meta.name}
- Tone: {campaign_details.meta.tone}
- Difficulty: {campaign_details.meta.difficulty}
- Language: {language_to_use}
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

        response = model.generate_content("\n".join(final_prompt_list))

        # 4. Parse and return response
        return parse_ai_response(response.text)

    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        raise HTTPException(status_code=503, detail=f"An error occurred with the AI service: {str(e)}")

# Need to import these from the other routers to avoid circular dependencies
from server.api.campaigns import get_campaign_details
from server.api.users import get_user_settings
