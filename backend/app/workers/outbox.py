"""Durable PostgreSQL outbox dispatch with idempotent Celery consumption."""

from __future__ import annotations

import random
import uuid
from datetime import timedelta

from kombu.exceptions import OperationalError
from sqlalchemy import select

from backend.app.core.cache import record_worker_heartbeat
from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.metrics import OUTBOX_DEAD_LETTERS, OUTBOX_DISPATCHED, WORKER_HEARTBEAT
from backend.app.core.models import OutboxEvent, ProcessedEvent
from backend.app.workers.celery_app import celery_app

MAX_ATTEMPTS = 5
CONSUMER = "profile-events-v1"


def retry_delay(attempt: int, jitter: float) -> float:
    """Bound exponential retry to five minutes plus a small jitter."""
    return min(300.0, 2 ** min(attempt, 8)) + jitter


@celery_app.task(name="recsys.dispatch_outbox")
def dispatch_outbox() -> int:
    dispatched = 0
    with SessionLocal.begin() as db:
        rows = list(
            db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.status == "pending", OutboxEvent.next_attempt_at <= utcnow())
                .order_by(OutboxEvent.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            )
        )
        for event in rows:
            try:
                process_event.delay(str(event.id))
                event.status = "dispatched"
                OUTBOX_DISPATCHED.inc()
                dispatched += 1
            except OperationalError:
                event.attempt_count += 1
                event.error_code = "broker_unavailable"
                if event.attempt_count >= MAX_ATTEMPTS:
                    event.status = "dead_letter"
                    OUTBOX_DEAD_LETTERS.inc()
                else:
                    event.next_attempt_at = utcnow() + timedelta(seconds=retry_delay(event.attempt_count, random.random()))
    WORKER_HEARTBEAT.set_to_current_time()
    record_worker_heartbeat()
    return dispatched


@celery_app.task(name="recsys.process_event", bind=True, max_retries=5)
def process_event(self, event_id: str) -> None:
    with SessionLocal.begin() as db:
        event = db.scalar(select(OutboxEvent).where(OutboxEvent.id == uuid.UUID(event_id)).with_for_update())
        if event is None:
            return
        if db.get(ProcessedEvent, (event.id, CONSUMER)) is not None:
            event.status = "processed"
            return
        # Profile versioning makes recommendation cache changes visible without a worker.
        # This event remains an explicit durable audit of async processing.
        db.add(ProcessedEvent(event_id=event.id, consumer_name=CONSUMER))
        event.status = "processed"
        event.processed_at = utcnow()
        event.error_code = None
        WORKER_HEARTBEAT.set_to_current_time()
        record_worker_heartbeat()
