import uuid
from datetime import datetime
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field

# --- Base Models ---

class UserProfile(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_code: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str # In a real app, this would be validated and kept secure
    hashed_password: str
    avatar_url: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserSettings(BaseModel):
    theme: str = "dark"
    language: str = "en"
    # other settings can be added here

class Message(BaseModel):
    role: str # 'user', 'assistant', or 'system'
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class CampaignMeta(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tone: str = "epic_fantasy"
    difficulty: str = "medium"
    host_user_code: str
    players: List[str] = []
    status: str = "active" # e.g., 'active', 'archived', 'completed'
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignJournal(BaseModel):
    entries: List[Message] = []

class CampaignCheckpoint(BaseModel):
    timestamp: datetime
    journal_state: CampaignJournal
    meta_state: CampaignMeta

class DiceRoll(BaseModel):
    sides: int
    result: int
    parts: Optional[Dict[str, int]] = None # For D100, e.g., {"tens": 80, "ones": 5}

class Room(BaseModel):
    room_code: str
    host_user_code: str
    name: Optional[str] = None
    is_public: bool = False
    players: List[str] = [] # List of user_codes
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RoomResponse(BaseModel):
    """Full room details including resolved player profiles."""
    room_code: str
    host_user_code: str
    name: Optional[str] = None
    is_public: bool = False
    players: List["UserProfileResponse"] = []
    created_at: datetime


# --- API Request/Response Models ---

# Auth
class RegisterRequest(BaseModel):
    email: str
    password: str # Note: We are not implementing secure password hashing for this project's scope
    username: str

class LoginRequest(BaseModel):
    email: str
    password: str

class UserProfileResponse(BaseModel):
    """User profile data returned to the client, without sensitive info."""
    id: uuid.UUID
    user_code: str
    username: str
    email: str
    avatar_url: Optional[str] = None
    created_at: datetime

class AuthResponse(BaseModel):
    user_code: str
    profile: UserProfileResponse

# Rooms
class CreateRoomRequest(BaseModel):
    is_public: bool
    name: Optional[str] = None

class JoinRoomRequest(BaseModel):
    room_code: str

# Campaigns
class CreateCampaignRequest(BaseModel):
    name: str
    tone: str = "epic_fantasy"
    difficulty: str = "medium"

class CampaignDetailsResponse(BaseModel):
    meta: CampaignMeta
    journal: CampaignJournal

class AddJournalEntryRequest(BaseModel):
    message: Message

# Dice
class RollRequest(BaseModel):
    sides: int
    private: bool = False
    seed: Optional[int] = None

# AI
class AICompleteRequest(BaseModel):
    campaign_id: str
    messages: List[Message]
    context: Optional[Dict[str, Any]] = None

class AICompleteResponse(BaseModel):
    text: str
    meta: Optional[Dict[str, Any]] = None
