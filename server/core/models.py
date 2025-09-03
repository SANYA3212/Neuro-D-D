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

class GameItem(BaseModel):
    """Represents an item in a player's inventory."""
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    description: Optional[str] = None
    uses: Optional[int] = None
    max_uses: Optional[int] = None

class PlayerState(BaseModel):
    """Represents the state of a player within a campaign (e.g., HP, status effects)."""
    hp: int = 20
    max_hp: int = 20
    inventory: List[GameItem] = Field(default_factory=list)

class CampaignMeta(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tone: str = "epic_fantasy"
    difficulty: str = "medium"
    host_user_code: str
    players: List[str] = []
    player_states: Dict[str, PlayerState] = Field(default_factory=dict)
    status: str = "active" # e.g., 'active', 'archived', 'completed'
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CampaignJournal(BaseModel):
    entries: List[Message] = Field(default_factory=list)
    lobby_chat: List[Message] = Field(default_factory=list)

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
    campaign_id: Optional[str] = None # Link to the campaign, if any
    created_at: datetime = Field(default_factory=datetime.utcnow)


# --- API Request/Response Models ---

class PlayerInfo(BaseModel):
    """Public information about a player in a room."""
    user_code: str
    username: str
    avatar_url: Optional[str] = None
    is_host: bool = False
    hp: int
    max_hp: int
    inventory: List[GameItem] = Field(default_factory=list)

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
    campaign_id: Optional[str] = None

class JoinRoomRequest(BaseModel):
    room_code: str

class RoomDetailsResponse(BaseModel):
    """A model for returning the full details of a room, including player profiles."""
    room_code: str
    host_user_code: str
    name: Optional[str] = None
    is_public: bool = False
    players: List[PlayerInfo] = []
    created_at: datetime
    journal: Optional[CampaignJournal] = None # Include the journal for state restoration

class RoomResponse(BaseModel):
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
    last_dice_roll: Optional[int] = None
    language: Optional[str] = None

class AICompleteResponse(BaseModel):
    text: str
    meta: Optional[Dict[str, Any]] = None
