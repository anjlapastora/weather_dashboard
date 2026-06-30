"""
app.py — Helios Flask application entry point.

Starts the Flask API server and optionally the APScheduler background
pipeline that runs the ETL every day at 2 AM.

Usage:
    python app.py                   # starts server + scheduler
    FLASK_DEBUG=true python app.py  # hot-reload, scheduler disabled
"""

import os
import sys
import logging
from datetime import date, timedelta

from flask import Flask
from flask_cors import CORS

# ── Bootstrap ─────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    FLASK_HOST, FLASK_PORT, FLASK_DEBUG,
    PIPELINE_CRON_HOUR, PIPELINE_CRON_MINUTE, PIPELINE_DAYS_BACK,
    LOG_DIR, LOCATIONS,
)
from db.schema import init_db
from api.routes import api

# ── Logging ───────────────────────────────────────────────────────────────────
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(LOG_DIR, "helios.log")),
    ],
)
log = logging.getLogger("helios")

# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> Flask:
    app = Flask(__name__)
    CORS(app)  # allow the React frontend on a different port

    app.register_blueprint(api)

    @app.get("/")
    def index():
        from flask import jsonify
        return jsonify({
            "app":     "Helios Solar & Wind Monitor",
            "version": "1.0.0",
            "docs":    "/api/health",
        })

    return app


# ── Scheduler ─────────────────────────────────────────────────────────────────

def start_scheduler(app: Flask):
    """
    Register a daily cron job that runs the full ETL pipeline.
    Disabled in debug mode to avoid double-execution with the reloader.
    """
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.cron import CronTrigger
    except ImportError:
        log.warning("apscheduler not installed — scheduled pipeline disabled. "
                    "Run: pip install apscheduler")
        return

    def _run_all():
        end   = str(date.today() - timedelta(days=1))
        start = str(date.today() - timedelta(days=PIPELINE_DAYS_BACK + 1))
        log.info(f"Scheduled pipeline triggered: {start} → {end}")
        with app.app_context():
            from etl.pipeline import run_all
            results = run_all(start, end)
            for r in results:
                log.info(f"  {r}")

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        func=_run_all,
        trigger=CronTrigger(hour=PIPELINE_CRON_HOUR, minute=PIPELINE_CRON_MINUTE),
        id="daily_pipeline",
        name="Daily ETL pipeline",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    log.info(f"Scheduler started — pipeline runs daily at "
             f"{PIPELINE_CRON_HOUR:02d}:{PIPELINE_CRON_MINUTE:02d}")
    return scheduler


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Initialising database…")
    init_db()

    app = create_app()

    if not FLASK_DEBUG:
        start_scheduler(app)
    else:
        log.info("Debug mode — scheduler disabled")

    log.info(f"Starting Helios on http://{FLASK_HOST}:{FLASK_PORT}")
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
