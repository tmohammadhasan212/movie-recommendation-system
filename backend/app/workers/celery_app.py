from celery import Celery

from backend.app.core.config import get_settings

celery_app = Celery("recsys", broker=get_settings().redis_url)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_backend=None,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_transport_options={"visibility_timeout": 3600},
    beat_schedule={"dispatch-outbox": {"task": "recsys.dispatch_outbox", "schedule": 5.0}},
    imports=("backend.app.workers.outbox",),
)
