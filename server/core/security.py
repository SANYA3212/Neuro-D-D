import uuid
import hashlib
from server.core import config

def generate_user_code() -> str:
    """Generates a new, unique user code."""
    return str(uuid.uuid4())

def hash_password(password: str) -> str:
    """
    Hashes a password using SHA256 with a static salt.
    This is a basic implementation for demonstration.
    A real-world application should use a library like passlib with unique salts per user.
    """
    salted_password = password + config.PASSWORD_SALT
    return hashlib.sha256(salted_password.encode('utf-8')).hexdigest()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifies a plain password against a hashed one.
    """
    return hash_password(plain_password) == hashed_password
