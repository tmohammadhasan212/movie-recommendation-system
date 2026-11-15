from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any, cast

import pytest
from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

from backend.app.api.v1 import identity
from backend.app.api.v1.identity import Credentials
from backend.app.modules.identity.security import (
    DUMMY_PASSWORD_HASH,
    password_valid_or_dummy,
)


class FakeDB:
    def __init__(self, scalar_result: object) -> None:
        self.scalar_result = scalar_result
        self.added: list[object] = []
        self.commits = 0

    def scalar(self, statement: object) -> Any:
        return self.scalar_result

    def add(self, value: object) -> None:
        self.added.append(value)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        raise AssertionError("rollback was not expected")


def request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "server": ("testserver", 80),
            "client": ("127.0.0.1", 1234),
            "path": "/api/v1/auth/login",
            "query_string": b"",
            "headers": [(b"host", b"testserver")],
        }
    )


@pytest.mark.parametrize("account_exists", [False, True])
def test_registration_hashes_password_whether_account_exists(
    monkeypatch: pytest.MonkeyPatch,
    account_exists: bool,
) -> None:
    hashes: list[str] = []
    monkeypatch.setattr(identity, "enforce_rate_limit", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        identity,
        "password_hash",
        lambda password: hashes.append(password) or "candidate-hash",
    )
    db = FakeDB(uuid.uuid4() if account_exists else None)
    credentials = Credentials(email="person@example.test", password="correct horse battery")

    result = identity.register(credentials, request(), cast(Session, db))

    assert hashes == [credentials.password]
    assert "account is ready to sign in" in result["message"]
    assert len(db.added) == (0 if account_exists else 1)


@pytest.mark.parametrize("account_exists", [False, True])
def test_failed_login_verifies_real_or_dummy_hash_exactly_once(
    monkeypatch: pytest.MonkeyPatch,
    account_exists: bool,
) -> None:
    stored_hashes: list[str | None] = []
    monkeypatch.setattr(identity, "enforce_rate_limit", lambda *args, **kwargs: None)

    def invalid(stored: str | None, submitted: str) -> bool:
        stored_hashes.append(stored)
        assert submitted == "incorrect password"
        return False

    monkeypatch.setattr(identity, "password_valid_or_dummy", invalid)
    user = SimpleNamespace(id=uuid.uuid4(), password_hash="real-account-hash")
    db = FakeDB(user if account_exists else None)
    credentials = Credentials(email="person@example.test", password="incorrect password")

    with pytest.raises(HTTPException) as captured:
        identity.login(credentials, request(), Response(), cast(Session, db))

    assert captured.value.status_code == 401
    assert stored_hashes == ["real-account-hash" if account_exists else None]


def test_dummy_hash_matches_current_argon2_policy() -> None:
    assert "$m=65536,t=3,p=2$" in DUMMY_PASSWORD_HASH
    assert not password_valid_or_dummy(None, "any submitted password")
