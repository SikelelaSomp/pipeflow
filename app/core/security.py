import secrets
import bcrypt


def generate_api_key() -> str:
    """Generate a cryptographically secure API key. Return once — never stored raw."""
    return f"pf_{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    return bcrypt.hashpw(raw_key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    return bcrypt.checkpw(raw_key.encode(), hashed_key.encode())