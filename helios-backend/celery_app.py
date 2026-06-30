"""
celery_app.py — Celery application instance and Beat schedule.

Start the worker:
    celery -A celery_app worker --loglevel=info

Start the Beat scheduler (in a separate terminal):
    celery -A celery_app beat --loglevel=info
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery import Celery
from celery.schedules import crontab
from config import (
    CELERY_BROKER_URL,
    CELERY_RESULT_BACKEND,
    PIPELINE_CRON_HOUR,
    PIPELINE_CRON_MINUTE,
)

celery = Celery(
    "helios",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
    include=["tasks"],
)

celery.conf.update(
    timezone="UTC",
    enable_utc=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    beat_schedule={
        "daily-etl-pipeline": {
            "task": "tasks.run_daily_pipeline",
            "schedule": crontab(
                hour=PIPELINE_CRON_HOUR,
                minute=PIPELINE_CRON_MINUTE,
            ),
        },
    },
)
