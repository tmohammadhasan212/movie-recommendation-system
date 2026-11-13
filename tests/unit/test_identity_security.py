import uuid

from backend.app.modules.identity.security import (
    hash_secret,
    new_csrf_token,
    new_refresh_token,
    normalize_email,
    password_hash,
    password_valid,
    sign_access_token,
    verify_access_token,
)


def test_email_normalization() -> None:
    assert normalize_email("  USER@Example.Com ") == "user@example.com"


def test_password_is_hashed_and_verified() -> None:
    stored = password_hash("a long test password")
    assert "a long test password" not in stored
    assert password_valid(stored, "a long test password")
    assert not password_valid(stored, "wrong password")


def test_access_cookie_signature_and_expiry() -> None:
    session_id = uuid.uuid4()
    token = sign_access_token(session_id, now=1000)
    assert verify_access_token(token, now=1100) == session_id
    assert verify_access_token(token, now=2000) is None
    assert verify_access_token(token + "tampered", now=1100) is None


def test_refresh_and_csrf_are_random_and_hashable() -> None:
    first, first_hash = new_refresh_token(uuid.uuid4())
    second, _ = new_refresh_token(uuid.uuid4())
    assert first != second
    assert hash_secret(first) == first_hash
    csrf, csrf_hash = new_csrf_token()
    assert csrf != csrf_hash
    assert hash_secret(csrf) == csrf_hash
