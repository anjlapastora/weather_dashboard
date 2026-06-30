"""
db_context.py — Live SQLite queries that supply dynamic context to the chatbot.

Called by rag.py when the user's question contains a time phrase such as
"last 7 days", "past week", or "this month".  Returns a pre-formatted text
block that is prepended to the retrieved static knowledge so the LLM can
answer with real, up-to-date numbers instead of the static markdown snapshots.
"""

from __future__ import annotations

import re
import sqlite3
from datetime import date, timedelta
from pathlib import Path


# ── Time phrase parser ─────────────────────────────────────────────────────────

def parse_time_window(question: str) -> int | None:
    """
    Detect a time window in *question* and return it as a number of days.
    Returns ``None`` if no recognisable time phrase is found.

    Examples
    --------
    "last 7 days"     → 7
    "last week"       → 7
    "past 2 weeks"    → 14
    "past month"      → 30
    "yesterday"       → 1
    "recent anomaly"  → 7  (default for "recent")
    "What is Helios?" → None
    """
    q = question.lower()

    # "last/past N days"
    m = re.search(r'\b(?:last|past)\s+(\d+)\s+days?\b', q)
    if m:
        return int(m.group(1))

    # "last/past N weeks"
    m = re.search(r'\b(?:last|past)\s+(\d+)\s+weeks?\b', q)
    if m:
        return int(m.group(1)) * 7

    # "last/past/this week"
    if re.search(r'\b(?:last|past|this)\s+week\b', q):
        return 7

    # "last/past/this month"
    if re.search(r'\b(?:last|past|this)\s+month\b', q):
        return 30

    # "yesterday"
    if re.search(r'\byesterday\b', q):
        return 1

    # "recent" / "recently"
    if re.search(r'\brecent(?:ly)?\b', q):
        return 7

    return None


# ── Database helpers ───────────────────────────────────────────────────────────

def _connect(db_path: str) -> sqlite3.Connection:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    return con


# ── Live query functions ───────────────────────────────────────────────────────

def fetch_wind_anomalies(days: int, db_path: str, site_key: str | None = None) -> str:
    """Return a markdown table of wind anomalies in the last *days* days."""
    end   = date.today()
    start = end - timedelta(days=days)

    site_filter = "AND s.key = ?" if site_key else ""
    params: list = [str(start), str(end)]
    if site_key:
        params.append(site_key)

    con = _connect(db_path)
    try:
        rows = con.execute(f"""
            SELECT s.label, s.region,
                   c.observed_at,
                   c.wind_speed, c.wind_gusts
            FROM   cleaned_observations c
            JOIN   sites s ON s.id = c.site_id
            WHERE  c.wind_iqr_flag = 1
              AND  date(c.observed_at) BETWEEN ? AND ?
              {site_filter}
            ORDER  BY s.label, c.observed_at
        """, params).fetchall()
    finally:
        con.close()

    site_desc = f"for {site_key} " if site_key else ""
    period    = f"{start} to {end}"

    if not rows:
        return (
            f"Wind anomalies {site_desc}in the last {days} days ({period}): "
            "**none detected.**"
        )

    # Group by site
    by_site: dict[str, list] = {}
    for r in rows:
        label = f"{r['label']} ({r['region']})"
        by_site.setdefault(label, []).append(r)

    lines = [f"Wind anomalies (IQR method) in the last {days} days ({period}):\n"]
    for site_label, site_rows in by_site.items():
        lines.append(f"\n### {site_label} — {len(site_rows)} anomalous reading(s)\n")
        lines.append("| Timestamp (UTC) | Wind Speed | Gusts |")
        lines.append("|-----------------|-----------|-------|")
        for r in site_rows:
            ts   = str(r["observed_at"])[:16]
            ws   = f"{r['wind_speed']:.1f} km/h" if r["wind_speed"] is not None else "N/A"
            gust = f"{r['wind_gusts']:.1f} km/h"  if r["wind_gusts"] is not None else "N/A"
            lines.append(f"| {ts} | {ws} | {gust} |")

    return "\n".join(lines)


def fetch_solar_stats(days: int, db_path: str, site_key: str | None = None) -> str:
    """Return a markdown table of daytime solar statistics for the last *days* days."""
    end   = date.today()
    start = end - timedelta(days=days)

    site_filter = "AND s.key = ?" if site_key else ""
    params: list = [str(start), str(end)]
    if site_key:
        params.append(site_key)

    con = _connect(db_path)
    try:
        rows = con.execute(f"""
            SELECT s.label, s.region,
                   ROUND(AVG(CASE WHEN c.is_daytime = 1 THEN c.solar_ghi END), 1) AS avg_solar,
                   ROUND(MAX(c.solar_ghi), 1)                                       AS peak_solar,
                   COUNT(CASE WHEN c.solar_iqr_flag = 1 THEN 1 END)                  AS solar_anomalies
            FROM   cleaned_observations c
            JOIN   sites s ON s.id = c.site_id
            WHERE  date(c.observed_at) BETWEEN ? AND ?
              {site_filter}
            GROUP  BY s.id, s.label, s.region
            ORDER  BY avg_solar DESC NULLS LAST
        """, params).fetchall()
    finally:
        con.close()

    period = f"{start} to {end}"

    if not rows:
        return f"No solar data available for the last {days} days ({period})."

    lines = [
        f"Solar radiation — last {days} days ({period}), daytime averages (IQR anomaly detection):\n",
        "| Site | Avg GHI (daytime) | Peak GHI | IQR Anomalies |",
        "|------|-------------------|----------|---------------|",
    ]
    for r in rows:
        label = f"{r['label']} ({r['region']})"
        avg   = f"{r['avg_solar']} W/m²"  if r["avg_solar"]  is not None else "N/A"
        peak  = f"{r['peak_solar']} W/m²" if r["peak_solar"] is not None else "N/A"
        lines.append(f"| {label} | {avg} | {peak} | {r['solar_anomalies']} |")

    best = rows[0]
    if best["avg_solar"] is not None:
        lines.append(
            f"\nHighest daytime average: **{best['label']}** at {best['avg_solar']} W/m²."
        )
    return "\n".join(lines)


def fetch_site_comparison(days: int, db_path: str) -> str:
    """Return a cross-site comparison (solar + wind) for the last *days* days."""
    end   = date.today()
    start = end - timedelta(days=days)

    con = _connect(db_path)
    try:
        rows = con.execute("""
            SELECT s.label, s.region,
                   ROUND(AVG(CASE WHEN c.is_daytime = 1 THEN c.solar_ghi END), 1) AS avg_solar,
                   ROUND(MAX(c.solar_ghi), 1)                                       AS peak_solar,
                   ROUND(AVG(c.wind_speed), 1)                                      AS avg_wind,
                   ROUND(MAX(c.wind_gusts), 1)                                      AS max_gust,
                   COUNT(CASE WHEN c.wind_iqr_flag  = 1 THEN 1 END)                  AS wind_anomalies,
                   COUNT(CASE WHEN c.solar_iqr_flag = 1 THEN 1 END)                 AS solar_anomalies
            FROM   cleaned_observations c
            JOIN   sites s ON s.id = c.site_id
            WHERE  date(c.observed_at) BETWEEN ? AND ?
            GROUP  BY s.id, s.label, s.region
            ORDER  BY avg_solar DESC NULLS LAST
        """, [str(start), str(end)]).fetchall()
    finally:
        con.close()

    period = f"{start} to {end}"

    if not rows:
        return f"No data available for the last {days} days ({period})."

    lines = [
        f"Site comparison — last {days} days ({period}):\n",
        "| Site | Avg Solar (daytime) | Peak Solar | Avg Wind | Max Gust | Wind Anomalies |",
        "|------|---------------------|------------|----------|----------|----------------|",
    ]
    for r in rows:
        label  = f"{r['label']} ({r['region']})"
        avg_s  = f"{r['avg_solar']} W/m²"  if r["avg_solar"]  is not None else "N/A"
        peak_s = f"{r['peak_solar']} W/m²" if r["peak_solar"] is not None else "N/A"
        avg_w  = f"{r['avg_wind']} km/h"   if r["avg_wind"]   is not None else "N/A"
        max_g  = f"{r['max_gust']} km/h"   if r["max_gust"]   is not None else "N/A"
        lines.append(
            f"| {label} | {avg_s} | {peak_s} | {avg_w} | {max_g} | {r['wind_anomalies']} |"
        )

    return "\n".join(lines)


# ── Public entry point ─────────────────────────────────────────────────────────

def get_live_context(question: str, db_path: str) -> str | None:
    """
    Return a formatted live-data block for injection into the RAG prompt,
    or ``None`` if the question has no time phrase or the DB is unavailable.

    The returned string is designed to be prepended to the retrieved static
    knowledge so the LLM sees current numbers rather than stale snapshots.
    """
    if not Path(db_path).exists():
        return None

    days = parse_time_window(question)
    if days is None:
        return None

    q          = question.lower()
    is_wind    = any(w in q for w in ("wind", "gust", "anomal"))
    is_solar   = any(w in q for w in ("solar", "radiation", "irradiance", "photovoltaic"))
    is_compare = any(w in q for w in ("compar", "all three", "all sites", "across", "which site",
                                       "generation potential", "highest"))

    today = date.today()
    header = (
        f"## Live database snapshot (queried {today}, covering last {days} day(s): "
        f"{today - timedelta(days=days)} to {today})\n\n"
        "Use the figures below to answer the question. "
        "They are more accurate than anything in the static documents.\n\n"
    )

    try:
        if is_compare:
            body = fetch_site_comparison(days, db_path)
            if is_wind:
                body += "\n\n" + fetch_wind_anomalies(days, db_path)
        elif is_wind:
            body = fetch_wind_anomalies(days, db_path)
        elif is_solar:
            body = fetch_solar_stats(days, db_path)
        else:
            # Fallback: return full comparison when topic is ambiguous
            body = fetch_site_comparison(days, db_path)

        return header + body

    except Exception:
        # Never let a DB error crash the chatbot — fall back to static docs
        return None
