"""
etl/fetch.py — Pulls hourly data from the Open-Meteo archive API.
Returns a raw, unmodified DataFrame — no cleaning happens here.
"""

import requests
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import OPENMETEO_URL, OPENMETEO_VARS, OPENMETEO_TIMEOUT


def fetch_site(site: dict, start: str, end: str) -> pd.DataFrame:
    """
    Fetch hourly observations for one site over [start, end] (ISO date strings).

    Args:
        site:  A dict from config.LOCATIONS (must have lat, lon, tz, key).
        start: 'YYYY-MM-DD'
        end:   'YYYY-MM-DD'

    Returns:
        Raw DataFrame with columns:
            observed_at, solar_ghi, solar_direct,
            wind_speed, wind_gusts, wind_direction, site_key
    """
    params = {
        "latitude":       site["lat"],
        "longitude":      site["lon"],
        "start_date":     start,
        "end_date":       end,
        "hourly":         OPENMETEO_VARS,
        "timezone":       site["tz"],
        "wind_speed_unit": "kmh",
    }

    resp = requests.get(OPENMETEO_URL, params=params, timeout=OPENMETEO_TIMEOUT)
    resp.raise_for_status()

    payload = resp.json()
    if "hourly" not in payload:
        raise ValueError(f"Unexpected API response for {site['key']}: {payload}")

    h = payload["hourly"]

    df = pd.DataFrame({
        "observed_at":   h.get("time",                 []),
        "solar_ghi":     h.get("shortwave_radiation",  []),
        "solar_direct":  h.get("direct_radiation",     []),
        "wind_speed":    h.get("wind_speed_10m",       []),
        "wind_gusts":    h.get("wind_gusts_10m",       []),
        "wind_direction":h.get("wind_direction_10m",   []),
    })

    df["site_key"] = site["key"]
    return df
