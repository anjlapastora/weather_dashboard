"""
db/queries.py — All SQLite read/write helpers.
Every function opens its own connection so they're safe to call from threads.
"""

import sqlite3
from datetime import datetime
from typing import Optional
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DB_PATH


def _connect() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")   # safe concurrent reads + writes
    con.execute("PRAGMA foreign_keys=ON")
    return con


# ── Site helpers ──────────────────────────────────────────────────────────────

def get_site_id(key: str) -> Optional[int]:
    with _connect() as con:
        row = con.execute("SELECT id FROM sites WHERE key = ?", (key,)).fetchone()
    return row["id"] if row else None


def get_all_sites() -> list[dict]:
    with _connect() as con:
        rows = con.execute("SELECT * FROM sites ORDER BY id").fetchall()
    return [dict(r) for r in rows]


# ── Raw observations ──────────────────────────────────────────────────────────

def upsert_raw(df: pd.DataFrame, site_key: str) -> int:
    """
    Insert raw rows — skips duplicates via INSERT OR IGNORE.
    Returns the number of rows actually written.
    """
    site_id = get_site_id(site_key)
    if site_id is None:
        raise ValueError(f"Unknown site key: {site_key!r}")

    rows = df[[
        "observed_at", "solar_ghi", "solar_direct",
        "wind_speed", "wind_gusts", "wind_direction",
    ]].copy()
    rows.insert(0, "site_id", site_id)

    inserted = 0
    with _connect() as con:
        for _, r in rows.iterrows():
            cur = con.execute("""
                INSERT OR IGNORE INTO raw_observations
                    (site_id, observed_at, solar_ghi, solar_direct,
                     wind_speed, wind_gusts, wind_direction)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                site_id, r["observed_at"],
                _nan_to_none(r["solar_ghi"]),
                _nan_to_none(r["solar_direct"]),
                _nan_to_none(r["wind_speed"]),
                _nan_to_none(r["wind_gusts"]),
                _nan_to_none(r["wind_direction"]),
            ))
            inserted += cur.rowcount
        con.commit()
    return inserted


# ── Cleaned observations ──────────────────────────────────────────────────────

def upsert_cleaned(df: pd.DataFrame, site_key: str) -> int:
    """
    Insert or replace cleaned rows.
    Uses INSERT OR REPLACE so re-running the pipeline updates values in-place.
    Returns the number of rows written.
    """
    site_id = get_site_id(site_key)
    if site_id is None:
        raise ValueError(f"Unknown site key: {site_key!r}")

    cols = [
        "observed_at", "solar_ghi", "solar_direct",
        "wind_speed", "wind_gusts", "wind_direction",
        "solar_zscore", "wind_zscore",
        "solar_iqr_flag", "wind_iqr_flag",
        "solar_anomaly", "wind_anomaly",
        "is_daytime", "quality_flag",
    ]
    inserted = 0
    with _connect() as con:
        for _, r in df[cols].iterrows():
            cur = con.execute("""
                INSERT OR REPLACE INTO cleaned_observations
                    (site_id, observed_at, solar_ghi, solar_direct,
                     wind_speed, wind_gusts, wind_direction,
                     solar_zscore, wind_zscore,
                     solar_iqr_flag, wind_iqr_flag,
                     solar_anomaly, wind_anomaly,
                     is_daytime, quality_flag)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                site_id,
                r["observed_at"],
                _nan_to_none(r["solar_ghi"]),
                _nan_to_none(r["solar_direct"]),
                _nan_to_none(r["wind_speed"]),
                _nan_to_none(r["wind_gusts"]),
                _nan_to_none(r["wind_direction"]),
                _nan_to_none(r["solar_zscore"]),
                _nan_to_none(r["wind_zscore"]),
                int(r.get("solar_iqr_flag", 0)),
                int(r.get("wind_iqr_flag", 0)),
                int(r.get("solar_anomaly", 0)),
                int(r.get("wind_anomaly", 0)),
                int(r.get("is_daytime", 0)),
                r.get("quality_flag", "ok"),
            ))
            inserted += cur.rowcount
        con.commit()
    return inserted


# ── Query helpers for API routes ──────────────────────────────────────────────

def query_cleaned(site_key: str, start: str, end: str) -> list[dict]:
    with _connect() as con:
        rows = con.execute("""
            SELECT c.*
            FROM cleaned_observations c
            JOIN sites s ON s.id = c.site_id
            WHERE s.key = ?
              AND c.observed_at >= ?
              AND c.observed_at <  date(?, '+1 day')
            ORDER BY c.observed_at
        """, (site_key, start, end)).fetchall()
    return [dict(r) for r in rows]


def query_anomalies(site_key: str, start: str = None, end: str = None) -> list[dict]:
    sql = """
        SELECT c.*
        FROM cleaned_observations c
        JOIN sites s ON s.id = c.site_id
        WHERE s.key = ?
          AND (c.solar_anomaly = 1 OR c.wind_anomaly = 1)
    """
    params = [site_key]
    if start:
        sql += " AND c.observed_at >= ?"
        params.append(start)
    if end:
        sql += " AND c.observed_at <= ?"
        params.append(end)
    sql += " ORDER BY c.observed_at DESC"

    with _connect() as con:
        rows = con.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def query_pipeline_runs(limit: int = 20) -> list[dict]:
    with _connect() as con:
        rows = con.execute("""
            SELECT * FROM pipeline_runs
            ORDER BY started_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    return [dict(r) for r in rows]


# ── Pipeline run logging ──────────────────────────────────────────────────────

def start_run(site_key: str, fetch_start: str, fetch_end: str) -> int:
    with _connect() as con:
        cur = con.execute("""
            INSERT INTO pipeline_runs (site_key, fetch_start, fetch_end, status)
            VALUES (?, ?, ?, 'running')
        """, (site_key, fetch_start, fetch_end))
        con.commit()
        return cur.lastrowid


def finish_run(run_id: int, rows_fetched: int, rows_cleaned: int,
               rows_dropped: int, rows_flagged: int):
    with _connect() as con:
        con.execute("""
            UPDATE pipeline_runs
            SET completed_at = datetime('now'),
                rows_fetched  = ?,
                rows_cleaned  = ?,
                rows_dropped  = ?,
                rows_flagged  = ?,
                status        = 'success'
            WHERE id = ?
        """, (rows_fetched, rows_cleaned, rows_dropped, rows_flagged, run_id))
        con.commit()


def fail_run(run_id: int, error: str):
    with _connect() as con:
        con.execute("""
            UPDATE pipeline_runs
            SET completed_at  = datetime('now'),
                status        = 'failed',
                error_message = ?
            WHERE id = ?
        """, (error, run_id))
        con.commit()


# ── Internal utility ─────────────────────────────────────────────────────────

def _nan_to_none(value):
    """Convert NaN / pandas NA to Python None for SQLite."""
    try:
        import math
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        return value
    except (TypeError, ValueError):
        return None
