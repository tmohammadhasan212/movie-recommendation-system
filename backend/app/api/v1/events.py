from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.v1.identity import CsrfSession, _limit
from backend.app.core.db import get_db, utcnow
from backend.app.core.models import InteractionEvent, Movie, OutboxEvent

router = APIRouter(tags=["events"])
DB = Annotated[Session, Depends(get_db)]


class EventInput(BaseModel):
    id: uuid.UUID
    movie_id: int
    event_type: Literal["impression", "click", "detail_view"]
    occurred_at: datetime
    consent: bool


@router.post("/events", status_code=202)
def record_event(body: EventInput, request: Request, session: CsrfSession, db: DB) -> dict[str, str]:
    _limit(f"events:{session.user_id}", 120)
    now = utcnow()
    if not body.consent:
        raise HTTPException(403, "Consent required")
    if body.occurred_at.tzinfo is None or not now - timedelta(days=1) <= body.occurred_at <= now + timedelta(minutes=5):
        raise HTTPException(422, "Event time outside allowed window")
    movie = db.get(Movie, body.movie_id)
    if movie is None or not movie.active:
        raise HTTPException(404, "Movie not found")
    existing = db.get(InteractionEvent, body.id)
    if existing:
        if existing.user_id != session.user_id or existing.movie_id != body.movie_id or existing.event_type != body.event_type:
            raise HTTPException(409, "Event ID used for another action")
        return {"status": "accepted"}
    db.add(InteractionEvent(id=body.id, user_id=session.user_id, movie_id=body.movie_id, event_type=body.event_type, occurred_at=body.occurred_at, request_id=request.state.request_id, consent_source="explicit_api"))
    db.add(OutboxEvent(id=uuid.uuid4(), aggregate_ref=f"user:{session.user_id}", event_type=f"event.{body.event_type}", payload={"schema_version": 1, "event_id": str(body.id), "movie_id": body.movie_id}))
    db.commit()
    return {"status": "accepted"}
