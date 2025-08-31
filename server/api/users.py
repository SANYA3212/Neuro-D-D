from fastapi import APIRouter, Depends, HTTPException

from server.core import storage
from server.core.models import UserSettings
from server.api.auth import get_current_user_code

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/settings", response_model=UserSettings)
async def get_user_settings(user_code: str = Depends(get_current_user_code)):
    """
    Retrieves the current user's settings.
    If no settings file exists, returns default settings.
    """
    settings_path = storage.get_user_settings_file(user_code)
    if not settings_path:
        raise HTTPException(status_code=400, detail="Invalid user code format.")

    settings_data = storage.read_json(settings_path)
    if settings_data is None:
        return UserSettings()  # Return default settings

    return UserSettings(**settings_data)


@router.put("/settings", response_model=UserSettings)
async def update_user_settings(
    settings: UserSettings,
    user_code: str = Depends(get_current_user_code)
):
    """
    Updates the current user's settings.
    """
    settings_path = storage.get_user_settings_file(user_code)
    if not settings_path:
        raise HTTPException(status_code=400, detail="Invalid user code format.")

    storage.write_json(settings_path, settings.dict())
    return settings
