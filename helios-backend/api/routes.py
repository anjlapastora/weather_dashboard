"""
api/routes.py — All Flask REST endpoints.

Endpoints:
    GET /api/sites                      → list all monitoring sites
    GET /api/data                       → cleaned time-series for one site
    GET /api/data/multi                 → cleaned data for multiple sites
    GET /api/anomalies                  → anomaly rows for one site
    GET /api/stats                      → summary statistics for one site
    GET /api/pipeline/runs              → recent pipeline run audit log
    POST /api/pipeline/trigger          → manually trigger the ETL pipeline
"""

from flask import Blueprint, jsonify, request
from datetime import date, timedelta
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOCATIONS, DEFAULT_METHOD, DEFAULT_Z_THRESHOLD
from db.queries import (
    get_all_sites, query_cleaned, query_anomalies, query_pipeline_runs
)

api = Blueprint("api", __name__, url_prefix="/api")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _default_range():
    end   = (date.today() - timedelta(days=1)).isoformat()
    start = (date.today() - timedelta(days=31)).isoformat()
    return start, end


def _error(msg: str, code: int = 400):
    return jsonify({"error": msg}), code


# ── Routes ────────────────────────────────────────────────────────────────────

@api.get("/sites")
def list_sites():
    """Return all configured monitoring sites."""
    return jsonify(get_all_sites())


@api.get("/data")
def get_data():
    """
    Cleaned hourly observations for one site.

    Query params:
        site   (str)  — site key, default 'riyadh'
        start  (str)  — YYYY-MM-DD, default 30 days ago
        end    (str)  — YYYY-MM-DD, default yesterday
        quality (str) — 'ok' | 'all', default 'all'
    """
    site    = request.args.get("site", "riyadh")
    quality = request.args.get("quality", "all")
    default_start, default_end = _default_range()
    start = request.args.get("start", default_start)
    end   = request.args.get("end",   default_end)

    if site not in LOCATIONS:
        return _error(f"Unknown site '{site}'. Valid: {list(LOCATIONS.keys())}")

    rows = query_cleaned(site, start, end)

    if quality == "ok":
        rows = [r for r in rows if r.get("quality_flag") == "ok"]

    return jsonify({
        "site":  site,
        "start": start,
        "end":   end,
        "count": len(rows),
        "data":  rows,
    })


@api.get("/data/multi")
def get_data_multi():
    """
    Cleaned data for multiple sites in one request.

    Query params:
        sites  (str)  — comma-separated site keys, e.g. 'riyadh,wellington'
        start, end    — same as /api/data
    """
    raw_sites = request.args.get("sites", ",".join(LOCATIONS.keys()))
    site_keys = [s.strip() for s in raw_sites.split(",") if s.strip()]
    default_start, default_end = _default_range()
    start = request.args.get("start", default_start)
    end   = request.args.get("end",   default_end)

    invalid = [k for k in site_keys if k not in LOCATIONS]
    if invalid:
        return _error(f"Unknown site keys: {invalid}")

    result = {}
    for key in site_keys:
        rows = query_cleaned(key, start, end)
        result[key] = {"count": len(rows), "data": rows}

    return jsonify({"start": start, "end": end, "sites": result})


@api.get("/anomalies")
def get_anomalies():
    """
    Anomaly-flagged hours for one site.

    Query params:
        site, start, end — same as /api/data
        type  (str)  — 'solar' | 'wind' | 'all', default 'all'
    """
    site  = request.args.get("site", "riyadh")
    atype = request.args.get("type", "all")
    default_start, default_end = _default_range()
    start = request.args.get("start", default_start)
    end   = request.args.get("end",   default_end)

    if site not in LOCATIONS:
        return _error(f"Unknown site '{site}'.")

    rows = query_anomalies(site, start, end)

    if atype == "solar":
        rows = [r for r in rows if r.get("solar_anomaly")]
    elif atype == "wind":
        rows = [r for r in rows if r.get("wind_anomaly")]

    return jsonify({
        "site":  site,
        "start": start,
        "end":   end,
        "count": len(rows),
        "anomalies": rows,
    })


@api.get("/stats")
def get_stats():
    """
    Summary statistics for one site over a date range.

    Returns avg/max solar, avg/max wind, anomaly counts, data quality breakdown.
    """
    site = request.args.get("site", "riyadh")
    default_start, default_end = _default_range()
    start = request.args.get("start", default_start)
    end   = request.args.get("end",   default_end)

    if site not in LOCATIONS:
        return _error(f"Unknown site '{site}'.")

    rows = query_cleaned(site, start, end)
    if not rows:
        return jsonify({"site": site, "count": 0, "stats": {}})

    solar_vals = [r["solar_ghi"] for r in rows if r["solar_ghi"] is not None and r["is_daytime"]]
    wind_vals  = [r["wind_speed"] for r in rows if r["wind_speed"] is not None]
    all_solar  = [r["solar_ghi"] for r in rows if r["solar_ghi"] is not None]

    def safe_avg(lst): return round(sum(lst) / len(lst), 2) if lst else None
    def safe_max(lst): return round(max(lst), 2) if lst else None

    quality_counts = {}
    for r in rows:
        q = r.get("quality_flag", "unknown")
        quality_counts[q] = quality_counts.get(q, 0) + 1

    return jsonify({
        "site":  site,
        "start": start,
        "end":   end,
        "count": len(rows),
        "stats": {
            "avg_solar_daytime_wm2":  safe_avg(solar_vals),
            "max_solar_wm2":          safe_max(all_solar),
            "avg_wind_kmh":           safe_avg(wind_vals),
            "max_wind_kmh":           safe_max(wind_vals),
            "solar_anomaly_count":    sum(1 for r in rows if r.get("solar_anomaly")),
            "wind_anomaly_count":     sum(1 for r in rows if r.get("wind_anomaly")),
            "daytime_hours":          sum(1 for r in rows if r.get("is_daytime")),
            "quality_breakdown":      quality_counts,
        },
    })


@api.get("/pipeline/runs")
def pipeline_runs():
    """Recent pipeline run audit log."""
    limit = min(int(request.args.get("limit", 20)), 100)
    return jsonify(query_pipeline_runs(limit))


@api.post("/pipeline/trigger")
def trigger_pipeline():
    """
    Manually dispatch the ETL pipeline as a Celery task (async).
    Returns immediately with the task ID; the worker runs it in the background.

    Body (JSON, all optional):
        site     (str)   — run one site only; omit for all
        start    (str)   — YYYY-MM-DD
        end      (str)   — YYYY-MM-DD
    """
    from tasks import run_daily_pipeline, run_site_pipeline

    body  = request.get_json(silent=True) or {}
    default_start, default_end = _default_range()

    site  = body.get("site")
    start = body.get("start", default_start)
    end   = body.get("end",   default_end)

    try:
        if site:
            task = run_site_pipeline.delay(site, start, end)
        else:
            task = run_daily_pipeline.delay()

        return jsonify({
            "status":  "queued",
            "task_id": task.id,
            "site":    site or "all",
            "start":   start,
            "end":     end,
            "message": "Task queued. Check /pipeline/task/<task_id> for status.",
        }), 202
    except Exception as exc:
        return _error(f"Could not queue task: {exc}", 500)


@api.get("/pipeline/task/<task_id>")
def pipeline_task_status(task_id: str):
    """Check the status of a queued pipeline task."""
    from celery_app import celery
    from celery.result import AsyncResult

    result = AsyncResult(task_id, app=celery)
    response = {
        "task_id": task_id,
        "status":  result.status,
    }
    if result.ready():
        if result.successful():
            response["result"] = result.result
        else:
            response["error"] = str(result.result)
    return jsonify(response)


@api.get("/health")
def health():
    """Simple health check."""
    return jsonify({"status": "ok", "sites": list(LOCATIONS.keys())})
