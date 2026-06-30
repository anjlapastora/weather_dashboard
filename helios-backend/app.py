"""
app.py — Helios Flask application entry point.

The ETL pipeline is scheduled via Celery Beat (runs daily at 00:00 UTC).
This file starts only the Flask API server.

Usage:
    python app.py                   # start the API server
    FLASK_DEBUG=true python app.py  # hot-reload mode

Celery (run in separate terminals):
    celery -A celery_app worker --loglevel=info
    celery -A celery_app beat   --loglevel=info
"""

import os
import sys
import logging

from flask import Flask
from flask_cors import CORS

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import FLASK_HOST, FLASK_PORT, FLASK_DEBUG, LOG_DIR
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
    CORS(app)

    app.register_blueprint(api)

    @app.get("/")
    def index():
        from flask import jsonify
        return jsonify({
            "app":       "Helios Solar & Wind Monitor",
            "version":   "1.0.0",
            "scheduler": "Celery Beat — daily pipeline at 00:00 UTC",
            "docs":      "/api/health",
        })

    return app


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    log.info("Initialising database…")
    init_db()

    app = create_app()

    log.info("ETL schedule: Celery Beat — daily at 00:00 UTC")
    log.info("  Start worker: celery -A celery_app worker --loglevel=info")
    log.info("  Start beat:   celery -A celery_app beat   --loglevel=info")
    log.info(f"Starting Helios API on http://{FLASK_HOST}:{FLASK_PORT}")

    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
