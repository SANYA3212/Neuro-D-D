from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from server.core import storage
from server.core.models import UserSettings, UserProfile, UserProfileResponse
from server.api.auth import get_current_user_code, get_current_user

router = APIRouter(prefix="/users", tags=["Users"])

class UpdateProfileRequest(BaseModel):
    username: Optional[str] = None
    avatar_url: Optional[str] = None

@router.put("/profile", response_model=UserProfileResponse)
async def update_user_profile(
    request: UpdateProfileRequest,
    current_user: UserProfile = Depends(get_current_user)
):
    """Updates the current user's profile (e.g., username)."""
    profile_path = storage.get_user_profile_file(current_user.user_code)
    if not profile_path:
        # This should not happen if get_current_user succeeds
        raise HTTPException(status_code=404, detail="User profile file not found.")

    updated_user = current_user.copy(update=request.dict(exclude_unset=True))

    storage.write_json(profile_path, updated_user.dict())

    # FastAPI will correctly serialize this to UserProfileResponse
    return updated_user.dict()


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
