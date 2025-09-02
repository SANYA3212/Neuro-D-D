import shutil
import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Optional

from server.core.config import ROOT_DIR

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
    return updated_user


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


@router.post("/avatar", response_model=UserProfileResponse)
async def upload_avatar(
    current_user: UserProfile = Depends(get_current_user),
    file: UploadFile = File(...)
):
    """Uploads a new avatar for the current user."""
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/gif"]:
        raise HTTPException(status_code=400, detail="Invalid image type. Please use JPG, PNG, or GIF.")

    # Generate a unique filename to avoid collisions
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{current_user.user_code}_{uuid.uuid4()}.{file_extension}"

    avatars_dir = ROOT_DIR / "frontend/assets/avatars"
    avatars_dir.mkdir(exist_ok=True) # Ensure directory exists

    file_path = avatars_dir / unique_filename

    # Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    finally:
        file.file.close()

    # Update user profile with the new avatar URL
    avatar_url = f"/assets/avatars/{unique_filename}"
    current_user.avatar_url = avatar_url

    profile_path = storage.get_user_profile_file(current_user.user_code)
    storage.write_json(profile_path, current_user.dict())

    return current_user
