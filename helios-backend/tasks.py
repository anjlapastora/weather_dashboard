"""
tasks.py — Celery tasks for the Helios ETL pipeline.
"""

import sys
import os
import logging
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from celery_app import celery
from config import PIPELINE_DAYS_BACK, DEFAULT_METHOD, DEFAULT_Z_THRESHOLD

log = logging.getLogger("helios.tasks")


@celery.task(
    name="tasks.run_daily_pipeline",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # retry after 5 min on failure
)
def run_daily_pipeline(self):
    """
    Fetch, clean, and store the last PIPELINE_DAYS_BACK days of data
    for all three sites. Scheduled daily at 00:00 UTC via Celery Beat.
    """
    from etl.pipeline import run_all

    end   = str(date.today() - timedelta(days=1))
    start = str(date.today() - timedelta(days=PIPELINE_DAYS_BACK + 1))

    log.info("Daily pipeline starting: %s → %s", start, end)

    try:
        summaries = run_all(start, end, method=DEFAULT_METHOD, z_thresh=DEFAULT_Z_THRESHOLD)
        log.info("Daily pipeline complete: %s", summaries)
        return summaries
    except Exception as exc:
        log.error("Daily pipeline failed: %s", exc)
        raise self.retry(exc=exc)


@celery.task(name="tasks.run_site_pipeline")
def run_site_pipeline(site_key: str, start: str, end: str):
    """
    Run the pipeline for a single site and date range.
    Can be triggered manually via the Flask API or CLI.
    """
    from etl.pipeline import run_site

    log.info("Site pipeline starting: %s %s → %s", site_key, start, end)
    result = run_site(site_key, start, end)
    log.info("Site pipeline complete: %s", result)
    return result
