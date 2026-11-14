from datetime import timedelta

from sqlalchemy import delete

from backend.app.core.db import SessionLocal, utcnow
from backend.app.core.models import InteractionEvent
from backend.app.workers.celery_app import celery_app


@celery_app.task(name="recsys.purge_old_events")
def purge_old_events(days: int = 30) -> int:
    if not 1 <= days <= 365:
        raise ValueError("Retention days must be between 1 and 365")
    with SessionLocal.begin() as db:
        result = db.execute(
            delete(InteractionEvent).where(InteractionEvent.received_at < utcnow() - timedelta(days=days))
        )
        return result.rowcount
