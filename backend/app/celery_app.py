from celery import Celery
from app.core.config import settings

broker_url = settings.celery_broker_url or settings.redis_url
backend_url = settings.celery_result_backend or (
    settings.redis_url.rsplit("/", 1)[0] + "/1" if "/" in settings.redis_url else settings.redis_url
)

celery_app = Celery(
    "documind",
    broker=broker_url,
    backend=backend_url,
    include=[
        "app.tasks.test_tasks",
        "app.tasks.document_tasks",
        "app.tasks.chunking_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)