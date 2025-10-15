from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sound.tts import synthesize_text

router = APIRouter()

class TTSRequest(BaseModel):
    text: str

@router.post("/sound/tts", tags=["Sound"])
async def text_to_speech(request: TTSRequest):
    """
    Generates audio from text using SileroTTS.
    """
    if not request.text:
        raise HTTPException(status_code=400, detail="Text cannot be empty.")

    try:
        file_path = await synthesize_text(request.text)
        return {"file_path": file_path}
    except Exception as e:
        # Log the exception for debugging
        print(f"TTS endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to generate audio: {str(e)}")
