"""
etl/clean.py — Data cleaning stage.

Handles:
  1. Timestamp parsing and invalid row removal
  2. Duplicate (site, timestamp) removal
  3. Physical plausibility bounds — values outside range → NaN
  4. Nighttime solar correction — NaN at night → 0 (physically correct)
  5. Wind null imputation — forward-fill up to WIND_FFILL_LIMIT hours
  6. Quality flag assignment per row
"""

import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import PHYSICAL_BOUNDS, WIND_FFILL_LIMIT, DAYTIME_THRESHOLD


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean a raw DataFrame returned by etl.fetch.fetch_site().

    Returns a cleaned DataFrame with the same columns plus:
        is_daytime (int 0/1), quality_flag (str)
    """
    df = df.copy()
    original_len = len(df)

    # ── 1. Parse timestamps ───────────────────────────────────────────────────
    df["observed_at"] = pd.to_datetime(df["observed_at"], errors="coerce")

    bad_ts = df["observed_at"].isna().sum()
    if bad_ts:
        print(f"  [clean] Dropping {bad_ts} rows with unparseable timestamps")
    df = df.dropna(subset=["observed_at"])

    # ── 2. Cast numeric columns — coerce bad strings to NaN ──────────────────
    num_cols = ["solar_ghi", "solar_direct", "wind_speed", "wind_gusts", "wind_direction"]
    for col in num_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 3. Remove duplicate (site, timestamp) rows — keep first occurrence ────
    before = len(df)
    df = df.drop_duplicates(subset=["site_key", "observed_at"], keep="first")
    dupes = before - len(df)
    if dupes:
        print(f"  [clean] Removed {dupes} duplicate rows")

    # ── 4. Sort by time (needed for ffill to work correctly) ─────────────────
    df = df.sort_values("observed_at").reset_index(drop=True)

    # ── 5. Physical plausibility bounds — out-of-range values → NaN ──────────
    for col, (lo, hi) in PHYSICAL_BOUNDS.items():
        if col not in df.columns:
            continue
        bad_mask = df[col].notna() & ((df[col] < lo) | (df[col] > hi))
        n_bad = bad_mask.sum()
        if n_bad:
            print(f"  [clean] {col}: {n_bad} values outside [{lo}, {hi}] → NaN")
        df.loc[bad_mask, col] = np.nan

    # ── 6. Nighttime solar correction ────────────────────────────────────────
    #    Open-Meteo returns null for solar at night.
    #    Null and zero mean different things — zero is physically correct at night.
    df["is_daytime"] = (df["solar_ghi"].fillna(0) > DAYTIME_THRESHOLD).astype(int)
    nighttime_mask = df["is_daytime"] == 0
    df.loc[nighttime_mask, "solar_ghi"]    = df.loc[nighttime_mask, "solar_ghi"].fillna(0)
    df.loc[nighttime_mask, "solar_direct"] = df.loc[nighttime_mask, "solar_direct"].fillna(0)

    # ── 7. Wind null imputation — forward-fill short gaps only ───────────────
    #    Up to WIND_FFILL_LIMIT consecutive nulls are filled (sensor dropout).
    #    Longer gaps remain NaN — too uncertain to impute.
    for col in ["wind_speed", "wind_gusts", "wind_direction"]:
        null_before = df[col].isna().sum()
        df[col] = df[col].ffill(limit=WIND_FFILL_LIMIT)
        null_after = df[col].isna().sum()
        filled = null_before - null_after
        if filled:
            print(f"  [clean] {col}: forward-filled {filled} nulls (≤{WIND_FFILL_LIMIT}h gaps)")

    # ── 8. Quality flag ───────────────────────────────────────────────────────
    core_nulls = df[["solar_ghi", "wind_speed"]].isna().any(axis=1)
    df["quality_flag"] = "ok"
    df.loc[core_nulls, "quality_flag"] = "incomplete"

    # ── 9. Format timestamp for SQLite storage ────────────────────────────────
    df["observed_at"] = df["observed_at"].dt.strftime("%Y-%m-%dT%H:%M")

    rows_dropped = original_len - len(df)
    print(f"  [clean] {original_len} → {len(df)} rows "
          f"({rows_dropped} dropped, {core_nulls.sum()} incomplete)")

    return df
