"""
etl/normalize.py — Normalization and anomaly flagging stage.

Computes:
  - Z-scores for solar GHI (daytime only) and wind speed
  - IQR-based outlier flags for both variables
  - Combined anomaly flag (union of z-score and IQR for robustness)

Design notes:
  - Solar z-score is computed on DAYTIME hours only (nighttime zeros
    would collapse the mean/std and make the metric meaningless)
  - Wind uses all hours (wind blows day and night)
  - Both methods are always computed; which one drives `*_anomaly`
    is controlled by the `method` argument ('zscore' | 'iqr' | 'both')
"""

import pandas as pd
import numpy as np
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DEFAULT_Z_THRESHOLD


def normalize(
    df: pd.DataFrame,
    method: str = "zscore",
    z_thresh: float = DEFAULT_Z_THRESHOLD,
) -> pd.DataFrame:
    """
    Add z-score, IQR flag, and anomaly flag columns to a cleaned DataFrame.

    Args:
        df:        Output of etl.clean.clean()
        method:    'zscore' | 'iqr' | 'both'
                   Determines which method drives the *_anomaly columns.
        z_thresh:  Z-score magnitude above which a value is an anomaly.

    Returns:
        DataFrame with added columns:
            solar_zscore, wind_zscore,
            solar_iqr_flag, wind_iqr_flag,
            solar_anomaly, wind_anomaly
    """
    df = df.copy()

    # ── Solar Z-score (daytime observations only) ─────────────────────────────
    daytime_solar = df.loc[df["is_daytime"] == 1, "solar_ghi"].dropna()

    if len(daytime_solar) >= 10:
        s_mean = daytime_solar.mean()
        s_std  = daytime_solar.std(ddof=1)
        df["solar_zscore"] = (df["solar_ghi"] - s_mean) / (s_std if s_std > 0 else 1.0)
        # Nighttime hours get z-score 0 (they are not anomalous, just dark)
        df.loc[df["is_daytime"] == 0, "solar_zscore"] = 0.0
    else:
        print("  [normalize] Not enough daytime solar samples — solar_zscore set to NaN")
        df["solar_zscore"] = np.nan

    # ── Wind Z-score (all hours) ──────────────────────────────────────────────
    wind_vals = df["wind_speed"].dropna()

    if len(wind_vals) >= 10:
        w_mean = wind_vals.mean()
        w_std  = wind_vals.std(ddof=1)
        df["wind_zscore"] = (df["wind_speed"] - w_mean) / (w_std if w_std > 0 else 1.0)
    else:
        print("  [normalize] Not enough wind samples — wind_zscore set to NaN")
        df["wind_zscore"] = np.nan

    # ── Solar IQR flag ────────────────────────────────────────────────────────
    df["solar_iqr_flag"] = _iqr_flag(df.loc[df["is_daytime"] == 1, "solar_ghi"], df["solar_ghi"])

    # ── Wind IQR flag ─────────────────────────────────────────────────────────
    df["wind_iqr_flag"] = _iqr_flag(df["wind_speed"], df["wind_speed"])

    # ── Combined anomaly columns ──────────────────────────────────────────────
    if method == "zscore":
        df["solar_anomaly"] = (df["solar_zscore"].abs() > z_thresh).fillna(False).astype(int)
        df["wind_anomaly"]  = (df["wind_zscore"].abs()  > z_thresh).fillna(False).astype(int)
    elif method == "iqr":
        df["solar_anomaly"] = df["solar_iqr_flag"]
        df["wind_anomaly"]  = df["wind_iqr_flag"]
    else:  # 'both' — union of z-score and IQR
        df["solar_anomaly"] = (
            (df["solar_zscore"].abs() > z_thresh).fillna(False) | df["solar_iqr_flag"].astype(bool)
        ).astype(int)
        df["wind_anomaly"] = (
            (df["wind_zscore"].abs() > z_thresh).fillna(False) | df["wind_iqr_flag"].astype(bool)
        ).astype(int)

    n_solar = int(df["solar_anomaly"].sum())
    n_wind  = int(df["wind_anomaly"].sum())
    print(f"  [normalize] Flagged {n_solar} solar anomalies, {n_wind} wind anomalies "
          f"(method={method}, z_thresh={z_thresh})")

    return df


# ── Internal helpers ──────────────────────────────────────────────────────────

def _iqr_flag(reference_series: pd.Series, target_series: pd.Series) -> pd.Series:
    """
    Compute IQR outlier flags.
    Bounds are computed from reference_series (e.g. daytime-only for solar),
    but flags are applied to the full target_series index.
    """
    vals = reference_series.dropna()
    if len(vals) < 4:
        return pd.Series(0, index=target_series.index, dtype=int)

    q1  = vals.quantile(0.25)
    q3  = vals.quantile(0.75)
    iqr = q3 - q1
    lo  = q1 - 1.5 * iqr
    hi  = q3 + 1.5 * iqr

    flag = (
        target_series.notna() &
        ((target_series < lo) | (target_series > hi))
    ).astype(int)

    return flag.reindex(target_series.index, fill_value=0)
