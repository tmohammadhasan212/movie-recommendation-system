from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.core.models import OutboxEvent, OutboxReplay, ProcessedEvent
from backend.cli.replay_dead_letters import list_dead_letters, replay_dead_letters


@pytest.fixture
def db() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    OutboxEvent.__table__.create(engine)
    OutboxReplay.__table__.create(engine)
    ProcessedEvent.__table__.create(engine)
    with Session(engine) as session:
        yield session


def add_event(
    db: Session,
    *,
    status: str = "dead_letter",
    created_at: datetime | None = None,
) -> OutboxEvent:
    timestamp = created_at or datetime(2026, 11, 15, 10, tzinfo=UTC)
    event = OutboxEvent(
        aggregate_ref="user:example",
        event_type="rating.upserted",
        payload={"schema_version": 1, "private": "not-for-listing"},
        status=status,
        attempt_count=5,
        next_attempt_at=timestamp,
        created_at=timestamp,
        error_code="broker_unavailable",
    )
    db.add(event)
    db.commit()
    return event


def test_list_returns_only_dead_letters_without_payload(db: Session) -> None:
    dead_letter = add_event(db)
    add_event(db, status="pending")

    result = list_dead_letters(db)

    assert result == [
        {
            "id": str(dead_letter.id),
            "event_type": "rating.upserted",
            "aggregate_ref": "user:example",
            "attempt_count": 5,
            "error_code": "broker_unavailable",
            "created_at": dead_letter.created_at.isoformat(),
        }
    ]
    assert "payload" not in result[0]


def test_dry_run_does_not_change_event_or_write_audit(db: Session) -> None:
    event = add_event(db)

    result = replay_dead_letters(db, [event.id], apply=False)
    db.commit()

    db.refresh(event)
    assert result[0]["id"] == str(event.id)
    assert event.status == "dead_letter"
    assert event.attempt_count == 5
    assert db.scalar(select(OutboxReplay)) is None


def test_apply_requeues_event_and_preserves_audit_details(db: Session) -> None:
    event = add_event(db)
    replayed_at = datetime(2026, 11, 15, 12, tzinfo=UTC)

    replay_dead_letters(
        db,
        [event.id],
        apply=True,
        reason="Broker incident resolved",
        replayed_at=replayed_at,
    )
    db.commit()

    db.refresh(event)
    audit = db.scalar(select(OutboxReplay))
    assert event.status == "pending"
    assert event.attempt_count == 0
    assert event.error_code is None
    assert event.next_attempt_at.replace(tzinfo=UTC) == replayed_at
    assert audit is not None
    assert audit.event_id == event.id
    assert audit.previous_attempt_count == 5
    assert audit.previous_error_code == "broker_unavailable"
    assert audit.reason == "Broker incident resolved"


def test_batch_validation_rejects_non_dead_letter_without_changes(db: Session) -> None:
    dead_letter = add_event(db)
    pending = add_event(db, status="pending")

    with pytest.raises(ValueError, match="not dead letters"):
        replay_dead_letters(
            db,
            [dead_letter.id, pending.id],
            apply=True,
            reason="Reviewed batch replay",
        )

    assert dead_letter.status == "dead_letter"
    assert db.scalar(select(OutboxReplay)) is None


def test_replay_rejects_processed_or_duplicate_events(db: Session) -> None:
    event = add_event(db)
    db.add(ProcessedEvent(event_id=event.id, consumer_name="profile-events-v1"))
    db.commit()

    with pytest.raises(ValueError, match="processed records"):
        replay_dead_letters(db, [event.id], apply=False)
    with pytest.raises(ValueError, match="must be unique"):
        replay_dead_letters(db, [event.id, event.id], apply=False)


def test_apply_requires_operator_reason(db: Session) -> None:
    event = add_event(db)

    with pytest.raises(ValueError, match="reason must be between"):
        replay_dead_letters(db, [event.id], apply=True, reason="")
    with pytest.raises(ValueError, match="not found"):
        replay_dead_letters(db, [uuid.uuid4()], apply=False)
