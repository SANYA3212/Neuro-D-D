import json
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import filelock

from server.core import config
from server.core.models import UserProfile

# --- Path Helpers ---

def get_user_dir(user_code: str) -> Optional[Path]:
    """Returns the directory path for a given user. Returns None if invalid."""
    try:
        # Validate that user_code is a valid UUID format to prevent directory traversal
        uuid.UUID(user_code)
        user_dir = config.USERS_DIR / f"user_{user_code}"
        return user_dir
    except ValueError:
        return None

def get_user_profile_file(user_code: str) -> Optional[Path]:
    user_dir = get_user_dir(user_code)
    return user_dir / "profile.json" if user_dir else None

def get_user_settings_file(user_code: str) -> Optional[Path]:
    user_dir = get_user_dir(user_code)
    return user_dir / "settings.json" if user_dir else None

def get_campaigns_dir(user_code: str) -> Optional[Path]:
    user_dir = get_user_dir(user_code)
    return user_dir / "campaigns" if user_dir else None

def get_campaign_meta_file(user_code: str, campaign_id: str) -> Optional[Path]:
    try:
        uuid.UUID(campaign_id)
        campaigns_dir = get_campaigns_dir(user_code)
        return campaigns_dir / f"camp_{campaign_id}" / "meta.json" if campaigns_dir else None
    except ValueError:
        return None

def get_campaign_journal_file(user_code: str, campaign_id: str) -> Optional[Path]:
    try:
        uuid.UUID(campaign_id)
        campaigns_dir = get_campaigns_dir(user_code)
        return campaigns_dir / f"camp_{campaign_id}" / "journal.json" if campaigns_dir else None
    except ValueError:
        return None

# --- Generic Read/Write with Locking ---

def read_json(file_path: Path) -> Optional[Any]:
    """Reads a JSON file and returns its content. Returns None if file doesn't exist."""
    if not file_path.exists():
        return None
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return None # Or handle corrupted file case

def write_json(file_path: Path, data: Any):
    """Writes data to a JSON file with file locking to prevent race conditions."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = file_path.with_suffix('.lock')
    lock = filelock.FileLock(lock_path)

    with lock:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str) # Use default=str for datetime/uuid

# --- User Management ---

def find_user_by_email(email: str) -> Optional[UserProfile]:
    """Finds a user by email by checking the global index."""
    index = read_json(config.INDEX_FILE)
    if not index or 'users' not in index:
        return None

    user_email_map = index['users']
    if email in user_email_map:
        user_code = user_email_map[email].get("user_code")
        profile_path = get_user_profile_file(user_code)
        if profile_path:
            profile_data = read_json(profile_path)
            if profile_data:
                return UserProfile(**profile_data)
    return None

def add_user_to_index(user_profile: UserProfile):
    """Adds a user's email and code to the global index."""
    index = read_json(config.INDEX_FILE) or {"users": {}, "campaigns": {}}
    index["users"][user_profile.email] = {
        "user_code": user_profile.user_code,
        "username": user_profile.username
    }
    write_json(config.INDEX_FILE, index)


# --- Campaign Management ---

def get_campaign_dir(user_code: str, campaign_id: str) -> Optional[Path]:
    """Gets the full path to a specific campaign directory."""
    try:
        uuid.UUID(campaign_id) # Validate format
        campaigns_dir = get_campaigns_dir(user_code)
        if not campaigns_dir:
            return None
        return campaigns_dir / f"camp_{campaign_id}"
    except ValueError:
        return None

def delete_campaign_files(user_code: str, campaign_id: str):
    """Deletes the entire directory for a given campaign."""
    campaign_dir = get_campaign_dir(user_code, campaign_id)

    if campaign_dir and campaign_dir.exists() and campaign_dir.is_dir():
        # Safety check: Ensure we are not deleting something outside the user's data folder.
        if config.USERS_DIR not in campaign_dir.resolve().parents:
             raise PermissionError("Attempted to delete a directory outside the allowed scope.")
        shutil.rmtree(campaign_dir)
    else:
        # If directory doesn't exist, it's not an error for a DELETE operation.
        # We can just silently succeed.
        return


# --- Room Management ---

def get_all_rooms() -> List[Dict]:
    """Reads the list of all rooms."""
    return read_json(config.ROOMS_FILE) or []

def write_all_rooms(rooms: List[Dict]):
    """Writes the list of all rooms."""
    write_json(config.ROOMS_FILE, rooms)
