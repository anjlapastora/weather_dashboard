"""
db/schema.py — Creates all tables and seeds the sites reference table.
Safe to run multiple times (uses IF NOT EXISTS + INSERT OR IGNORE).
"""

import sqlite3
import os
import sys

# Allow running directly: python -m db.schema
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH, LOCATIONS


DDL = """
-- ── Sites reference table ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS sites (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    key         TEXT    UNIQUE NOT NULL,
    label       TEXT    NOT NULL,
    region      TEXT    NOT NULL,
    emoji       TEXT,
    latitude    REAL    NOT NULL,
    longitude   REAL    NOT NULL,
    timezone    TEXT    NOT NULL,
    color       TEXT,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── Raw observations — exactly as received from Open-Meteo ──────────────────
CREATE TABLE IF NOT EXISTS raw_observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    observed_at     TEXT    NOT NULL,
    solar_ghi       REAL,
    solar_direct    REAL,
    wind_speed      REAL,
    wind_gusts      REAL,
    wind_direction  REAL,
    fetched_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(site_id, observed_at)
);

-- ── Cleaned & normalized observations — what the frontend reads ──────────────
CREATE TABLE IF NOT EXISTS cleaned_observations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id         INTEGER NOT NULL REFERENCES sites(id),
    observed_at     TEXT    NOT NULL,
    solar_ghi       REAL,
    solar_direct    REAL,
    wind_speed      REAL,
    wind_gusts      REAL,
    wind_direction  REAL,
    solar_zscore    REAL,
    wind_zscore     REAL,
    solar_iqr_flag  INTEGER DEFAULT 0,
    wind_iqr_flag   INTEGER DEFAULT 0,
    solar_anomaly   INTEGER DEFAULT 0,
    wind_anomaly    INTEGER DEFAULT 0,
    is_daytime      INTEGER DEFAULT 0,
    quality_flag    TEXT    DEFAULT 'ok',
    cleaned_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE(site_id, observed_at)
);

-- ── Pipeline run audit log ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    site_key        TEXT,
    started_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT,
    fetch_start     TEXT,
    fetch_end       TEXT,
    rows_fetched    INTEGER DEFAULT 0,
    rows_cleaned    INTEGER DEFAULT 0,
    rows_dropped    INTEGER DEFAULT 0,
    rows_flagged    INTEGER DEFAULT 0,
    status          TEXT    NOT NULL DEFAULT 'running',
    error_message   TEXT
);

-- ── Indexes for query performance ────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_raw_site_time
    ON raw_observations(site_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_cleaned_site_time
    ON cleaned_observations(site_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_cleaned_anomaly
    ON cleaned_observations(site_id, solar_anomaly, wind_anomaly);
"""


def init_db():
    """Create all tables and seed the sites reference table."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    try:
        con.executescript(DDL)

        # Seed sites — INSERT OR IGNORE keeps existing rows intact
        for site in LOCATIONS.values():
            con.execute("""
                INSERT OR IGNORE INTO sites
                    (key, label, region, emoji, latitude, longitude, timezone, color)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                site["key"], site["label"], site["region"], site["emoji"],
                site["lat"], site["lon"], site["tz"], site["color"],
            ))

        con.commit()
        print(f"✓ Database initialised at {DB_PATH}")
    finally:
        con.close()


if __name__ == "__main__":
    init_db()
