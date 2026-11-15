"""Password, cookie and CSRF primitives; no raw tokens are persisted."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import time
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.app.core.config import get_settings

hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
EMAIL_PATTERN = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
ACCESS_SECONDS = 15 * 60
REFRESH_SECONDS = 30 * 24 * 60 * 60
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=2$gwmgv7Wp4Ve2UWSxxah3JQ$"
    "LVZEId9/jzk39Rd3cSlBVsG0uf+xOvloBIEIwWZfrhg"
)


def normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if len(normalized) > 320 or not EMAIL_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid email address")
    return normalized


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def password_hash(password: str) -> str:
    return hasher.hash(password)


def password_valid(stored: str, submitted: str) -> bool:
    try:
        return hasher.verify(stored, submitted)
    except VerifyMismatchError:
        return False


def password_valid_or_dummy(stored: str | None, submitted: str) -> bool:
    """Perform one Argon2 verification even when no account hash exists."""
    return password_valid(stored or DUMMY_PASSWORD_HASH, submitted)


def new_refresh_token(session_id: uuid.UUID) -> tuple[str, str]:
    token = f"{session_id}.{secrets.token_urlsafe(48)}"
    return token, hash_secret(token)


def new_csrf_token() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return token, hash_secret(token)


def sign_access_token(session_id: uuid.UUID, *, now: int | None = None) -> str:
    expiry = (now or int(time.time())) + ACCESS_SECONDS
    payload = f"{session_id}.{expiry}"
    signature = hmac.new(get_settings().session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_access_token(token: str, *, now: int | None = None) -> uuid.UUID | None:
    try:
        raw_id, raw_expiry, signature = token.split(".")
        session_id = uuid.UUID(raw_id)
        expiry = int(raw_expiry)
    except (ValueError, AttributeError):
        return None
    payload = f"{raw_id}.{raw_expiry}"
    expected = hmac.new(get_settings().session_secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if expiry < (now or int(time.time())) or not hmac.compare_digest(signature, expected):
        return None
    return session_id
