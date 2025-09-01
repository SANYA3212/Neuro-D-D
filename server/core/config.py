import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Core Paths ---
# The root directory of the project
ROOT_DIR = Path(__file__).parent.parent.parent

# Data directory
DATA_DIR = ROOT_DIR / "data"
USERS_DIR = DATA_DIR / "users"
ROOMS_FILE = DATA_DIR / "rooms.json"
INDEX_FILE = DATA_DIR / "index.json"

# Game Logic Prompts
PROMPTS_DIR = ROOT_DIR / "server" / "game_logic" / "prompts"
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "system_prompt.txt"
EXAMPLES_FILE = PROMPTS_DIR / "examples.md"


# --- Gemini AI Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash") # Use flash for speed and cost, but allow override

# --- Security ---
# For simplicity, we're not using a complex signing key, but this is where it would go.
SECRET_KEY = os.getenv("SECRET_KEY", "a_very_secret_default_key_for_dev")
PASSWORD_SALT = os.getenv("PASSWORD_SALT", "a_not_so_secret_salt_for_dev_passwords")

# --- Ensure directories exist ---
DATA_DIR.mkdir(exist_ok=True)
USERS_DIR.mkdir(exist_ok=True)
