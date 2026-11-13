from celery import Celery

from backend.app.core.config import get_settings

celery_app = Celery("recsys", broker=get_settings().redis_url)
celery_app.conf.update(task_serializer="json", accept_content=["json"], result_backend=None)
