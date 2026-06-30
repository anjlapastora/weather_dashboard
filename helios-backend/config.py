"""
config.py — Central configuration for Helios backend.
All site definitions, API settings, cleaning thresholds, and paths live here.
"""

import os

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "db", "helios.db")
LOG_DIR = os.path.join(BASE_DIR, "logs")

# ── Flask ────────────────────────────────────────────────────────────────────
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"

# ── Open-Meteo ───────────────────────────────────────────────────────────────
OPENMETEO_URL = "https://archive-api.open-meteo.com/v1/archive"
OPENMETEO_TIMEOUT = 30  # seconds
OPENMETEO_VARS = (
    "shortwave_radiation,"
    "direct_radiation,"
    "wind_speed_10m,"
    "wind_gusts_10m,"
    "wind_direction_10m"
)

# ── Monitoring sites ──────────────────────────────────────────────────────────
LOCATIONS = {
    "riyadh": {
        "key": "riyadh",
        "label": "Riyadh",
        "region": "Saudi Arabia",
        "emoji": "🏜️",
        "lat": 24.69,
        "lon": 46.72,
        "tz": "Asia/Riyadh",
        "color": "#F59E0B",
    },
    "wellington": {
        "key": "wellington",
        "label": "Wellington",
        "region": "New Zealand",
        "emoji": "🌬️",
        "lat": -41.29,
        "lon": 174.78,
        "tz": "Pacific/Auckland",
        "color": "#60A5FA",
    },
    "manila": {
        "key": "manila",
        "label": "Manila",
        "region": "Philippines",
        "emoji": "🌧️",
        "lat": 14.60,
        "lon": 120.98,
        "tz": "Asia/Manila",
        "color": "#34D399",
    },
}

# ── Cleaning thresholds ───────────────────────────────────────────────────────
# Physical plausibility bounds — values outside these are set to NaN
PHYSICAL_BOUNDS = {
    "solar_ghi": (0, 1400),  # W/m²  — solar constant ≈ 1361 W/m²
    "solar_direct": (0, 1400),
    "wind_speed": (0, 250),  # km/h  — above 250 = instrument error
    "wind_gusts": (0, 400),
    "wind_direction": (0, 360),  # degrees
}

# Max consecutive null hours to forward-fill for wind columns
WIND_FFILL_LIMIT = 2

# Solar GHI threshold below which we consider it nighttime
DAYTIME_THRESHOLD = 10  # W/m²

# ── Anomaly detection ─────────────────────────────────────────────────────────
DEFAULT_Z_THRESHOLD = 2.5  # σ — used for Z-Score method
DEFAULT_METHOD = "iqr"  # "zscore" | "iqr"

# ── Pipeline schedule (Celery Beat cron) ─────────────────────────────────────
PIPELINE_CRON_HOUR = 0    # midnight
PIPELINE_CRON_MINUTE = 0
PIPELINE_DAYS_BACK = 30   # how many days of history to fetch each run

# ── Celery / Redis ────────────────────────────────────────────────────────────
CELERY_BROKER_URL  = os.getenv("CELERY_BROKER_URL",  "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")
