from celery import Celery
import os

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
REDIS_BACKEND_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/1"

celery_app = Celery(
    "self_media_backend",
    broker=REDIS_BROKER_URL,
    backend=REDIS_BACKEND_URL,
    include=["app.tasks"]
)

celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',
    enable_utc=True,
)
