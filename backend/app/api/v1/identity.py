from __future__ import annotations

import hmac
import uuid
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import get_settings
from backend.app.core.db import get_db, utcnow
from backend.app.core.models import (
    GenrePreference,
    IdempotencyRecord,
    InteractionEvent,
    LoginSession,
    OutboxEvent,
    Rating,
    User,
    WatchlistItem,
)
from backend.app.core.rate_limit import enforce_rate_limit
from backend.app.modules.identity.security import (
    REFRESH_SECONDS,
    hash_secret,
    new_csrf_token,
    new_refresh_token,
    normalize_email,
    password_hash,
    password_valid,
    sign_access_token,
    verify_access_token,
)

router = APIRouter(tags=["identity"])
DB = Annotated[Session, Depends(get_db)]


class Credentials(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=12, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email(value)


class Profile(BaseModel):
    id: uuid.UUID
    email: str
    profile_version: int
    genres: list[str]


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class EmailChange(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    current_password: str = Field(min_length=1, max_length=256)

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        return normalize_email(value)


def _set_cookies(response: Response, session: LoginSession, refresh: str, csrf: str) -> None:
    secure = get_settings().cookie_secure
    response.set_cookie("access", sign_access_token(session.id), max_age=900, httponly=True, secure=secure, samesite="lax", path="/")
    response.set_cookie("refresh", refresh, max_age=REFRESH_SECONDS, httponly=True, secure=secure, samesite="lax", path="/api/v1/auth")
    response.set_cookie("csrf", csrf, max_age=REFRESH_SECONDS, httponly=False, secure=secure, samesite="lax", path="/")


def _clear_cookies(response: Response) -> None:
    response.delete_cookie("access", path="/")
    response.delete_cookie("refresh", path="/api/v1/auth")
    response.delete_cookie("csrf", path="/")


def current_session(request: Request, db: DB) -> LoginSession:
    session_id = verify_access_token(request.cookies.get("access", ""))
    if session_id is None:
        raise HTTPException(401, "Authentication required")
    session = db.get(LoginSession, session_id)
    if session is None or session.revoked_at or session.expires_at <= utcnow():
        raise HTTPException(401, "Authentication required")
    return session


SessionDep = Annotated[LoginSession, Depends(current_session)]


def csrf_session(request: Request, session: SessionDep, x_csrf_token: Annotated[str | None, Header()] = None) -> LoginSession:
    if not x_csrf_token or not hmac.compare_digest(hash_secret(x_csrf_token), session.csrf_hash):
        raise HTTPException(403, "CSRF token required")
    return session


CsrfSession = Annotated[LoginSession, Depends(csrf_session)]


@router.post("/auth/register", status_code=202)
def register(credentials: Credentials, request: Request, db: DB) -> dict[str, str]:
    enforce_rate_limit(
        f"register:{hash_secret(request.client.host if request.client else 'unknown')}",
        "register",
        5,
    )
    exists = db.scalar(select(User.id).where(User.email == credentials.email, User.deleted_at.is_(None)))
    if not exists:
        db.add(User(email=credentials.email, password_hash=password_hash(credentials.password)))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return {"message": "If this address can be registered, the account is ready to sign in."}


@router.post("/auth/login")
def login(credentials: Credentials, request: Request, response: Response, db: DB) -> dict[str, str]:
    client_hash = hash_secret(request.client.host if request.client else "unknown")
    enforce_rate_limit(
        f"login:{client_hash}:{hash_secret(credentials.email)}", "login", 10
    )
    user = db.scalar(select(User).where(User.email == credentials.email, User.deleted_at.is_(None)))
    if user is None or not password_valid(user.password_hash, credentials.password):
        raise HTTPException(401, "Invalid credentials")
    session = LoginSession(id=uuid.uuid4(), user_id=user.id, refresh_hash="", csrf_hash="", expires_at=utcnow() + timedelta(seconds=REFRESH_SECONDS))
    refresh, session.refresh_hash = new_refresh_token(session.id)
    csrf, session.csrf_hash = new_csrf_token()
    db.add(session)
    db.commit()
    _set_cookies(response, session, refresh, csrf)
    return {"message": "Signed in"}


@router.post("/auth/refresh")
def refresh(request: Request, response: Response, db: DB, x_csrf_token: Annotated[str | None, Header()] = None) -> dict[str, str]:
    raw = request.cookies.get("refresh", "")
    try:
        session_id = uuid.UUID(raw.split(".", 1)[0])
    except ValueError:
        raise HTTPException(401, "Authentication required") from None
    session = db.get(LoginSession, session_id)
    if session is None or session.revoked_at or session.expires_at <= utcnow():
        raise HTTPException(401, "Authentication required")
    if not hmac.compare_digest(hash_secret(raw), session.refresh_hash):
        session.revoked_at = utcnow()
        db.commit()
        raise HTTPException(401, "Authentication required")
    if not x_csrf_token or not hmac.compare_digest(hash_secret(x_csrf_token), session.csrf_hash):
        raise HTTPException(403, "CSRF token required")
    token, session.refresh_hash = new_refresh_token(session.id)
    csrf, session.csrf_hash = new_csrf_token()
    session.rotated_at = utcnow()
    db.commit()
    _set_cookies(response, session, token, csrf)
    return {"message": "Session refreshed"}


@router.post("/auth/logout")
def logout(response: Response, session: CsrfSession, db: DB) -> dict[str, str]:
    session.revoked_at = utcnow()
    db.commit()
    _clear_cookies(response)
    return {"message": "Signed out"}


@router.get("/me", response_model=Profile)
def me(session: SessionDep, db: DB) -> Profile:
    user = db.get(User, session.user_id)
    if user is None or user.deleted_at:
        raise HTTPException(401, "Authentication required")
    genres = list(db.scalars(select(GenrePreference.genre).where(GenrePreference.user_id == user.id)))
    return Profile(id=user.id, email=user.email, profile_version=user.profile_version, genres=sorted(genres))


@router.get("/me/export")
def export_account(session: SessionDep, db: DB) -> dict[str, object]:
    profile = me(session, db)
    ratings = list(db.scalars(select(Rating).where(Rating.user_id == session.user_id)))
    watchlist = list(db.scalars(select(WatchlistItem).where(WatchlistItem.user_id == session.user_id)))
    events = list(db.scalars(select(InteractionEvent).where(InteractionEvent.user_id == session.user_id)))
    return {
        "profile": profile.model_dump(mode="json"),
        "ratings": [{"movie_id": row.movie_id, "rating": row.rating} for row in ratings],
        "watchlist": [{"movie_id": row.movie_id, "created_at": row.created_at.isoformat()} for row in watchlist],
        "events": [{"id": str(row.id), "movie_id": row.movie_id, "type": row.event_type, "occurred_at": row.occurred_at.isoformat()} for row in events],
    }


@router.put("/me/password")
def change_password(body: PasswordChange, session: CsrfSession, db: DB) -> dict[str, str]:
    enforce_rate_limit(f"password:{session.user_id}", "password", 5, 300)
    if utcnow() - session.authenticated_at > timedelta(minutes=15):
        raise HTTPException(403, "Sign in again before changing your password")
    user = db.get(User, session.user_id)
    if user is None or not password_valid(user.password_hash, body.current_password):
        raise HTTPException(403, "Current password is incorrect")
    user.password_hash = password_hash(body.new_password)
    db.query(LoginSession).filter(LoginSession.user_id == user.id, LoginSession.id != session.id).update({"revoked_at": utcnow()})
    db.commit()
    return {"message": "Password updated"}


@router.patch("/me", response_model=Profile)
def change_email(body: EmailChange, session: CsrfSession, db: DB) -> Profile:
    enforce_rate_limit(f"profile:{session.user_id}", "profile", 5, 300)
    if utcnow() - session.authenticated_at > timedelta(minutes=15):
        raise HTTPException(403, "Sign in again before changing your email")
    user = db.get(User, session.user_id)
    if user is None or not password_valid(user.password_hash, body.current_password):
        raise HTTPException(403, "Current password is incorrect")
    user.email = body.email
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Email unavailable") from None
    return me(session, db)


@router.delete("/me", status_code=204)
def delete_account(session: CsrfSession, db: DB) -> Response:
    if utcnow() - session.authenticated_at > timedelta(minutes=15):
        raise HTTPException(403, "Sign in again before deleting your account")
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(401, "Authentication required")
    db.query(Rating).filter(Rating.user_id == user.id).delete()
    db.query(WatchlistItem).filter(WatchlistItem.user_id == user.id).delete()
    db.query(GenrePreference).filter(GenrePreference.user_id == user.id).delete()
    db.query(IdempotencyRecord).filter(IdempotencyRecord.user_id == user.id).delete()
    db.query(InteractionEvent).filter(InteractionEvent.user_id == user.id).update({"user_id": None})
    db.query(OutboxEvent).filter(OutboxEvent.aggregate_ref == f"user:{user.id}").delete()
    db.query(LoginSession).filter(LoginSession.user_id == user.id).delete()
    user.email = f"deleted-{user.id}@invalid.local"
    user.password_hash = "deleted"
    user.deleted_at = utcnow()
    user.profile_version += 1
    db.commit()
    response = Response(status_code=204)
    _clear_cookies(response)
    return response
