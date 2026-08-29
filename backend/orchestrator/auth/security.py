"""
Authentication & Cryptographic Security Utilities (Phase 4B).

Features:
  - Password hashing & verification with native Bcrypt / SHA256.
  - JWT token generation & verification (HMAC-SHA256).
  - Built-in predefined officer / supervisor / auditor credentials for hackathon evaluation.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel

from backend.config import settings
from backend.logging_config import get_logger

logger = get_logger("orchestrator.auth")


class UserTokenData(BaseModel):
    user_id: str
    email: str
    role: str  # officer | supervisor | auditor | admin
    badge_number: str
    checkpoint_id: str


def get_password_hash(password: str) -> str:
    """Hash password with bcrypt."""
    pw_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


# Pre-configured demo users for offline & live evaluations
DEMO_USERS: dict[str, dict[str, Any]] = {
    "officer@borderguard.gov": {
        "user_id": "00000000-0000-0000-0000-000000000001",
        "email": "officer@borderguard.gov",
        "password_hash": get_password_hash("officer123"),
        "role": "officer",
        "name": "Officer J. Miller",
        "badge_number": "BG-7492",
        "checkpoint_id": "CP-DEL-T3",
    },
    "supervisor@borderguard.gov": {
        "user_id": "00000000-0000-0000-0000-000000000002",
        "email": "supervisor@borderguard.gov",
        "password_hash": get_password_hash("supervisor123"),
        "role": "supervisor",
        "name": "Supervisor S. Rao",
        "badge_number": "BG-SUP-014",
        "checkpoint_id": "CP-DEL-T3",
    },
    "auditor@borderguard.gov": {
        "user_id": "00000000-0000-0000-0000-000000000003",
        "email": "auditor@borderguard.gov",
        "password_hash": get_password_hash("auditor123"),
        "role": "auditor",
        "name": "Auditor M. Chen",
        "badge_number": "BG-AUD-990",
        "checkpoint_id": "HQ-AUDIT-CENTRAL",
    },
    "admin@borderguard.gov": {
        "user_id": "00000000-0000-0000-0000-000000000004",
        "email": "admin@borderguard.gov",
        "password_hash": get_password_hash("admin123"),
        "role": "admin",
        "name": "Administrator",
        "badge_number": "BG-ADM-001",
        "checkpoint_id": "HQ-ADMIN",
    },
}


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes)

    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt


def decode_access_token(token: str) -> UserTokenData | None:
    """Decode and validate a JWT access token."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        email = payload.get("email")
        role = payload.get("role")
        badge = payload.get("badge_number", "BG-XXXX")
        cp = payload.get("checkpoint_id", "CP-DEFAULT")

        if user_id is None or role is None:
            return None

        return UserTokenData(
            user_id=user_id,
            email=email or "",
            role=role,
            badge_number=badge,
            checkpoint_id=cp,
        )
    except JWTError as exc:
        logger.debug("jwt_decode_failed", error=str(exc))
        return None
