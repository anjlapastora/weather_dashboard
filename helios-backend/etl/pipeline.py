"""
etl/pipeline.py — Orchestrates the full ETL pipeline for one or all sites.

Flow:  fetch → clean → normalize → upsert_raw → upsert_cleaned → log

Usage:
    # Run all sites (default last 30 days)
    python -m etl.pipeline

    # Run a specific site
    python -m etl.pipeline --site riyadh

    # Run with a custom date range
    python -m etl.pipeline --start 2026-05-01 --end 2026-05-31
"""

import argparse
import sys, os
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LOCATIONS, PIPELINE_DAYS_BACK, DEFAULT_Z_THRESHOLD, DEFAULT_METHOD
from etl.fetch import fetch_site
from etl.clean import clean
from etl.normalize import normalize
from db.queries import upsert_raw, upsert_cleaned, start_run, finish_run, fail_run


def run_site(
    site_key: str,
    start: str,
    end: str,
    method: str = DEFAULT_METHOD,
    z_thresh: float = DEFAULT_Z_THRESHOLD,
) -> dict:
    """
    Run the full pipeline for a single site.
    Returns a summary dict.
    """
    site = LOCATIONS.get(site_key)
    if not site:
        raise ValueError(f"Unknown site: {site_key!r}. Valid keys: {list(LOCATIONS.keys())}")

    print(f"\n{'='*55}")
    print(f"  Pipeline: {site['emoji']} {site['label']}  |  {start} → {end}")
    print(f"{'='*55}")

    run_id = start_run(site_key, start, end)

    try:
        # ── 1. Fetch ──────────────────────────────────────────────────────────
        print(f"\n[1/4] Fetching from Open-Meteo…")
        raw_df = fetch_site(site, start, end)
        print(f"      {len(raw_df)} hourly rows received")

        # ── 2. Persist raw ────────────────────────────────────────────────────
        print(f"\n[2/4] Saving raw observations…")
        raw_written = upsert_raw(raw_df, site_key)
        print(f"      {raw_written} rows written (duplicates skipped)")

        # ── 3. Clean ──────────────────────────────────────────────────────────
        print(f"\n[3/4] Cleaning…")
        cleaned_df = clean(raw_df)
        rows_dropped = len(raw_df) - len(cleaned_df)

        # ── 4. Normalize & flag ───────────────────────────────────────────────
        print(f"\n[4/4] Normalizing & flagging anomalies…")
        normed_df = normalize(cleaned_df, method=method, z_thresh=z_thresh)

        # Persist cleaned
        cleaned_written = upsert_cleaned(normed_df, site_key)
        print(f"      {cleaned_written} rows written to cleaned_observations")

        rows_flagged = int(
            normed_df["solar_anomaly"].sum() + normed_df["wind_anomaly"].sum()
        )

        finish_run(
            run_id,
            rows_fetched=len(raw_df),
            rows_cleaned=len(cleaned_df),
            rows_dropped=rows_dropped,
            rows_flagged=rows_flagged,
        )

        summary = {
            "site":         site_key,
            "start":        start,
            "end":          end,
            "rows_fetched": len(raw_df),
            "rows_cleaned": len(cleaned_df),
            "rows_dropped": rows_dropped,
            "rows_flagged": rows_flagged,
            "status":       "success",
        }
        print(f"\n✓ Done: {summary}")
        return summary

    except Exception as exc:
        fail_run(run_id, str(exc))
        print(f"\n✗ Pipeline failed for {site_key}: {exc}", file=sys.stderr)
        raise


def run_all(
    start: str,
    end: str,
    method: str = DEFAULT_METHOD,
    z_thresh: float = DEFAULT_Z_THRESHOLD,
) -> list[dict]:
    """Run the pipeline for every configured site."""
    summaries = []
    for key in LOCATIONS:
        try:
            summary = run_site(key, start, end, method, z_thresh)
            summaries.append(summary)
        except Exception as exc:
            summaries.append({"site": key, "status": "failed", "error": str(exc)})
    return summaries


# ── CLI entry point ───────────────────────────────────────────────────────────

def _default_dates():
    end   = date.today() - timedelta(days=1)
    start = end - timedelta(days=PIPELINE_DAYS_BACK)
    return str(start), str(end)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Helios ETL pipeline")
    parser.add_argument("--site",   default=None, help="Site key (default: all)")
    parser.add_argument("--start",  default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--end",    default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--method", default=DEFAULT_METHOD, choices=["zscore", "iqr", "both"])
    parser.add_argument("--z",      default=DEFAULT_Z_THRESHOLD, type=float)
    args = parser.parse_args()

    default_start, default_end = _default_dates()
    start = args.start or default_start
    end   = args.end   or default_end

    if args.site:
        run_site(args.site, start, end, method=args.method, z_thresh=args.z)
    else:
        run_all(start, end, method=args.method, z_thresh=args.z)
