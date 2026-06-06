from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "voice_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "workers.tasks.post_call",
        "workers.tasks.kb_ingestion",
        "workers.tasks.crm_sync",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)
