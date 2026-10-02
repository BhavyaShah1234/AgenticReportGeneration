"""Password hashing and JWT helpers."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from app.config import get_settings

ALGO = "HS256"
COOKIE_NAME = "session"
PRINT_TOKEN_TTL = timedelta(minutes=5)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def _jwt_key() -> str:
    """HS256 key derived from APP_SECRET_KEY (fixed 64-char length, domain-separated from Fernet)."""
    return hashlib.sha256(f"jwt:{get_settings().app_secret_key}".encode()).hexdigest()


def _encode(payload: dict[str, Any], ttl: timedelta) -> str:
    now = datetime.now(UTC)
    body = {**payload, "iat": now, "exp": now + ttl}
    return jwt.encode(body, _jwt_key(), algorithm=ALGO)


def decode_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, _jwt_key(), algorithms=[ALGO])
    except jwt.PyJWTError:
        return None


def create_session_token(user_id: str, company_id: str) -> str:
    return _encode({"sub": user_id, "cid": company_id, "purpose": "session"}, timedelta(hours=get_settings().jwt_ttl_hours))


def create_print_token(run_id: str) -> str:
    return _encode({"run_id": run_id, "purpose": "print"}, PRINT_TOKEN_TTL)


def verify_print_token(token: str, run_id: str) -> bool:
    data = decode_token(token)
    return bool(data and data.get("purpose") == "print" and data.get("run_id") == run_id)
