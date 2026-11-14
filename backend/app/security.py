"""Password hashing, bearer tokens, and agent token handling.

- Users: bcrypt passwords, signed JWT bearer tokens.
- Agents: opaque random tokens. Only SHA-256 hashes are stored; the
  plaintext is shown exactly once at issuance and never again.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

logger = logging.getLogger("infrapulse.security")

_ALGORITHM = "HS256"


def hash_password(plaintext: str) -> str:
    return bcrypt.hashpw(plaintext.encode(), bcrypt.gensalt()).decode()


def verify_password(plaintext: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plaintext.encode(), hashed.encode())
    except (ValueError, TypeError):
        return False


def create_token(user_id: str, username: str, is_admin: bool = False) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "username": username,
        "admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expiry_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[_ALGORITHM])
    except jwt.PyJWTError:
        return None


def generate_agent_token() -> tuple[str, str]:
    """Return (plaintext_token, sha256_hex) for a new agent credential."""
    plaintext = "ipa_" + secrets.token_urlsafe(32)
    digest = hashlib.sha256(plaintext.encode()).hexdigest()
    return plaintext, digest


def hash_agent_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode()).hexdigest()
