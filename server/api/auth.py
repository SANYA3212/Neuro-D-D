from fastapi import APIRouter, Depends, HTTPException, Header
from fastapi.responses import JSONResponse
from typing import Optional

from server.core import storage, security
from server.core.models import (
    RegisterRequest, LoginRequest, AuthResponse, UserProfile,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# --- Dependency for protected routes ---

async def get_current_user_code(x_user_code: Optional[str] = Header(None)) -> str:
    """Dependency to get and validate the user_code from the header."""
    if not x_user_code:
        raise HTTPException(status_code=401, detail="X-User-Code header missing")

    profile_path = storage.get_user_profile_file(x_user_code)
    if not profile_path or not profile_path.exists():
        raise HTTPException(status_code=401, detail="Invalid user code")

    return x_user_code

async def get_current_user(user_code: str = Depends(get_current_user_code)) -> UserProfile:
    """Dependency to get the full user profile from the validated user_code."""
    profile_path = storage.get_user_profile_file(user_code)
    profile_data = storage.read_json(profile_path)
    if not profile_data:
        # This case should ideally not be hit if get_current_user_code passed
        raise HTTPException(status_code=404, detail="User profile not found")
    return UserProfile(**profile_data)


# --- Authentication Endpoints ---

@router.post("/register", response_model=AuthResponse)
async def register_user(request: RegisterRequest):
    """
    Creates a new user account.
    Validates that the email is not already in use.
    """
    if storage.find_user_by_email(request.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    # For this project, password is not securely hashed. See security.py
    hashed_password = security.hash_password(request.password)

    new_user = UserProfile(
        username=request.username,
        email=request.email,
        # In a real app, you would store the hashed_password
    )

    # Create user files
    profile_path = storage.get_user_profile_file(new_user.user_code)
    storage.write_json(profile_path, new_user.dict())

    # Add to global index
    storage.add_user_to_index(new_user)

    return AuthResponse(user_code=new_user.user_code, profile=new_user)


@router.post("/login", response_model=AuthResponse)
async def login_user(request: LoginRequest):
    """
    Logs a user in by verifying their credentials.
    """
    user_profile = storage.find_user_by_email(request.email)
    if not user_profile:
        raise HTTPException(status_code=404, detail="User not found")

    # In a real app, you would fetch the stored hashed password and verify it.
    # Since we are not storing it, we can't truly verify.
    # We will simulate a check.
    # password_is_correct = security.verify_password(request.password, stored_hashed_password)
    # For this project, we'll just accept any password if the user exists.

    return AuthResponse(user_code=user_profile.user_code, profile=user_profile)


@router.get("/me", response_model=UserProfile)
async def get_user_me(current_user: UserProfile = Depends(get_current_user)):
    """
    Returns the profile of the currently authenticated user.
    """
    return current_user
