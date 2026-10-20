from celery import Celery
from app.core.config import settings

raw_broker = settings.celery_broker_url or settings.redis_url
broker_url = raw_broker.replace("://localhost:", "://127.0.0.1:") if "://localhost:" in raw_broker else raw_broker

raw_backend = settings.celery_result_backend or (
    settings.redis_url.rsplit("/", 1)[0] + "/1" if "/" in settings.redis_url else settings.redis_url
)
backend_url = raw_backend.replace("://localhost:", "://127.0.0.1:") if "://localhost:" in raw_backend else raw_backend

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
    # Broker & worker connectivity reliability
    broker_connection_retry_on_startup=True,
    broker_transport_options={
        "visibility_timeout": 3600,
        "max_retries": 5,
        "interval_start": 1.0,
        "interval_step": 1.0,
        "interval_max": 10.0,
    },
    # Worker concurrency & queue dispatching
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    result_expires=3600,
    # Task execution timeouts (prevent runaway OCR or LLM extractions)
    task_soft_time_limit=180,
    task_time_limit=240,
)