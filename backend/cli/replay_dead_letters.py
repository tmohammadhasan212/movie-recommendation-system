"""Inspect and safely replay explicitly selected dead-letter outbox events."""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.models import OutboxEvent, OutboxReplay, ProcessedEvent

MAX_BATCH_SIZE = 100


def _event_summary(event: OutboxEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "event_type": event.event_type,
        "aggregate_ref": event.aggregate_ref,
        "attempt_count": event.attempt_count,
        "error_code": event.error_code,
        "created_at": event.created_at.isoformat(),
    }


def list_dead_letters(db: Session, *, limit: int = 25) -> list[dict[str, Any]]:
    if not 1 <= limit <= MAX_BATCH_SIZE:
        raise ValueError(f"limit must be between 1 and {MAX_BATCH_SIZE}")
    events = db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.status == "dead_letter")
        .order_by(OutboxEvent.created_at, OutboxEvent.id)
        .limit(limit)
    )
    return [_event_summary(event) for event in events]


def replay_dead_letters(
    db: Session,
    event_ids: list[uuid.UUID],
    *,
    apply: bool,
    reason: str | None = None,
    replayed_at: datetime | None = None,
) -> list[dict[str, Any]]:
    if not event_ids:
        raise ValueError("at least one event ID is required")
    if len(event_ids) > MAX_BATCH_SIZE:
        raise ValueError(f"no more than {MAX_BATCH_SIZE} events may be replayed at once")
    if len(set(event_ids)) != len(event_ids):
        raise ValueError("event IDs must be unique")
    clean_reason = reason.strip() if reason else ""
    if apply and not 3 <= len(clean_reason) <= 500:
        raise ValueError("reason must be between 3 and 500 characters when applying a replay")

    events = list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.id.in_(event_ids))
            .with_for_update()
        )
    )
    by_id = {event.id: event for event in events}
    missing = [str(event_id) for event_id in event_ids if event_id not in by_id]
    if missing:
        raise ValueError(f"outbox events not found: {', '.join(missing)}")

    invalid = [str(event.id) for event in events if event.status != "dead_letter"]
    if invalid:
        raise ValueError(f"events are not dead letters: {', '.join(sorted(invalid))}")

    processed_ids = set(
        db.scalars(select(ProcessedEvent.event_id).where(ProcessedEvent.event_id.in_(event_ids)))
    )
    if processed_ids:
        rendered = ", ".join(sorted(str(event_id) for event_id in processed_ids))
        raise ValueError(f"events already have processed records: {rendered}")

    ordered_events = [by_id[event_id] for event_id in event_ids]
    summaries = [_event_summary(event) for event in ordered_events]
    if not apply:
        return summaries

    timestamp = replayed_at or utcnow()
    for event in ordered_events:
        db.add(
            OutboxReplay(
                event_id=event.id,
                reason=clean_reason,
                previous_attempt_count=event.attempt_count,
                previous_error_code=event.error_code,
                replayed_at=timestamp,
            )
        )
        event.status = "pending"
        event.attempt_count = 0
        event.next_attempt_at = timestamp
        event.processed_at = None
        event.error_code = None
    return summaries


def _uuid(value: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("must be a UUID") from error


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true", help="list dead letters without payloads")
    mode.add_argument("--event-id", action="append", type=_uuid, dest="event_ids")
    parser.add_argument("--limit", type=int, default=25, help="maximum rows returned by --list")
    parser.add_argument("--apply", action="store_true", help="commit the selected replay")
    parser.add_argument("--reason", help="required operator reason when using --apply")
    args = parser.parse_args()

    if args.list and (args.apply or args.reason):
        parser.error("--apply and --reason can only be used with --event-id")

    try:
        if args.list:
            with SessionLocal() as db:
                events = list_dead_letters(db, limit=args.limit)
            print(json.dumps({"count": len(events), "events": events}))
            return

        with SessionLocal.begin() as db:
            events = replay_dead_letters(
                db,
                args.event_ids,
                apply=args.apply,
                reason=args.reason,
            )
        print(json.dumps({"applied": args.apply, "count": len(events), "events": events}))
    except ValueError as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
