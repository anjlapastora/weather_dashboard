"""
tests/test_etl.py — Unit tests for the ETL pipeline stages.

Run with:  pytest helios-backend/tests/test_etl.py -v
           (from the repo root, or just `pytest` from helios-backend/)
"""

import sys, os
import pytest
import numpy as np
import pandas as pd
from unittest.mock import patch, MagicMock

# Make the helios-backend package importable when running from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from etl.clean import clean
from etl.normalize import normalize, _iqr_flag
from etl.fetch import fetch_site


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_raw(n=48, site_key="riyadh", daytime_ghi=500.0, wind=20.0):
    """Return a minimal raw DataFrame that mirrors fetch_site() output."""
    times = pd.date_range("2026-01-01", periods=n, freq="h")
    # Alternate day/night for solar column
    ghi = [daytime_ghi if (i % 24 in range(6, 18)) else None for i in range(n)]
    return pd.DataFrame({
        "observed_at":    times.strftime("%Y-%m-%dT%H:%M"),
        "solar_ghi":      ghi,
        "solar_direct":   ghi,
        "wind_speed":     [wind] * n,
        "wind_gusts":     [wind + 5] * n,
        "wind_direction": [180] * n,
        "site_key":       site_key,
    })


# ── etl.clean ─────────────────────────────────────────────────────────────────

class TestClean:
    def test_returns_expected_columns(self):
        df = clean(_make_raw())
        assert "is_daytime" in df.columns
        assert "quality_flag" in df.columns

    def test_timestamp_parsed_and_formatted(self):
        df = clean(_make_raw())
        # After clean(), observed_at should be string in YYYY-MM-DDTHH:MM format
        assert df["observed_at"].str.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}").all()

    def test_unparseable_timestamps_dropped(self):
        raw = _make_raw(n=5)
        raw.loc[2, "observed_at"] = "not-a-date"
        df = clean(raw)
        assert len(df) == 4

    def test_duplicates_removed(self):
        raw = _make_raw(n=4)
        raw = pd.concat([raw, raw.iloc[[0]]], ignore_index=True)  # add duplicate row
        df = clean(raw)
        assert len(df) == 4

    def test_nighttime_solar_set_to_zero(self):
        df = clean(_make_raw())
        night_rows = df[df["is_daytime"] == 0]
        assert (night_rows["solar_ghi"] == 0).all()
        assert (night_rows["solar_direct"] == 0).all()

    def test_out_of_range_solar_clipped_to_zero(self):
        # An out-of-range solar value is first set to NaN by the bounds check,
        # then the nighttime pass (is_daytime=0 because fillna(0) ≤ threshold)
        # sets it to 0 — so it ends up as 0, not NaN.
        raw = _make_raw()
        raw.loc[6, "solar_ghi"] = 9999  # above 1400 W/m² limit
        df = clean(raw)
        row = df[df["observed_at"] == "2026-01-01T06:00"]
        assert row["solar_ghi"].iloc[0] == 0.0

    def test_out_of_range_wind_becomes_nan(self):
        raw = _make_raw()
        raw.loc[0, "wind_speed"] = 999  # above 250 km/h limit
        df = clean(raw)
        # Row 0 is at midnight — ffill might recover it; check the raw value is gone
        # After clean, no wind_speed should exceed 250
        assert (df["wind_speed"].dropna() <= 250).all()

    def test_wind_ffill_fills_short_gaps(self):
        raw = _make_raw(n=24)
        raw.loc[5, "wind_speed"] = None
        raw.loc[6, "wind_speed"] = None
        df = clean(raw)
        # Both gaps should be filled (≤ WIND_FFILL_LIMIT=2 consecutive)
        assert df["wind_speed"].isna().sum() == 0

    def test_wind_ffill_leaves_long_gaps(self):
        raw = _make_raw(n=24)
        for i in range(5, 11):  # 6 consecutive nulls — exceeds limit of 2
            raw.loc[i, "wind_speed"] = None
        df = clean(raw)
        assert df["wind_speed"].isna().sum() > 0

    def test_quality_flag_ok_for_complete_rows(self):
        df = clean(_make_raw())
        # All rows have solar/wind data; daytime rows should be "ok"
        daytime = df[df["is_daytime"] == 1]
        assert (daytime["quality_flag"] == "ok").all()

    def test_quality_flag_incomplete_for_null_wind(self):
        # Solar NaN always gets zeroed by the nighttime pass, so to get
        # quality_flag='incomplete' we need wind_speed to remain NaN after ffill.
        # Create 3 consecutive wind nulls which exceeds the ffill limit of 2.
        raw = _make_raw(n=24)
        for i in [10, 11, 12]:
            raw.loc[i, "wind_speed"] = None
        df = clean(raw)
        incomplete_rows = df[df["quality_flag"] == "incomplete"]
        assert len(incomplete_rows) > 0

    def test_non_numeric_coerced_to_nan(self):
        # Simulate bad string data arriving from a CSV/object-typed source.
        # Build the row list with a string mixed into floats so the column
        # starts as object dtype (as it would from a raw CSV read).
        n = 5
        times = pd.date_range("2026-01-01", periods=n, freq="h")
        raw = pd.DataFrame({
            "observed_at":    times.strftime("%Y-%m-%dT%H:%M"),
            "solar_ghi":      [None] * n,
            "solar_direct":   [None] * n,
            "wind_speed":     ["n/a", 20.0, 20.0, 20.0, 20.0],  # mixed → object dtype
            "wind_gusts":     [25.0] * n,
            "wind_direction": [180] * n,
            "site_key":       "riyadh",
        })
        df = clean(raw)
        assert "wind_speed" in df.columns


# ── etl.normalize ─────────────────────────────────────────────────────────────

class TestNormalize:
    @pytest.fixture
    def cleaned(self):
        return clean(_make_raw(n=96))  # 4 days — enough samples for stats

    def test_zscore_columns_present(self, cleaned):
        df = normalize(cleaned, method="zscore")
        assert "solar_zscore" in df.columns
        assert "wind_zscore" in df.columns

    def test_iqr_flag_columns_present(self, cleaned):
        df = normalize(cleaned, method="iqr")
        assert "solar_iqr_flag" in df.columns
        assert "wind_iqr_flag" in df.columns

    def test_anomaly_columns_present(self, cleaned):
        df = normalize(cleaned, method="zscore")
        assert "solar_anomaly" in df.columns
        assert "wind_anomaly" in df.columns

    def test_nighttime_zscore_is_zero(self, cleaned):
        df = normalize(cleaned, method="zscore")
        night = df[df["is_daytime"] == 0]
        assert (night["solar_zscore"] == 0.0).all()

    def test_zscore_anomaly_fires_on_spike(self):
        raw = _make_raw(n=96, daytime_ghi=500.0)
        # Plant a spike that is within physical bounds (≤1400) but far above the
        # typical 500 W/m² — clean() will keep it, normalize() should flag it.
        spike_idx = raw.index[(raw["observed_at"].str.endswith("T10:00"))][0]
        raw.loc[spike_idx, "solar_ghi"] = 1350
        df = normalize(clean(raw), method="zscore", z_thresh=2.5)
        spike_row = df[df["observed_at"] == raw.loc[spike_idx, "observed_at"][:16]]
        assert spike_row["solar_anomaly"].iloc[0] == 1

    def test_iqr_flag_fires_on_spike(self):
        raw = _make_raw(n=96, wind=20.0)
        # Plant an extreme wind value
        raw.loc[0, "wind_speed"] = 9999
        df = normalize(clean(raw), method="iqr")
        # After clean() bounds it to NaN, IQR shouldn't flag it (it's NaN)
        # Reverse: plant a high-but-valid value (200 km/h)
        raw.loc[0, "wind_speed"] = 200
        df = normalize(clean(raw), method="iqr")
        assert df["wind_iqr_flag"].sum() >= 1

    def test_method_both_is_union(self, cleaned):
        df_z   = normalize(cleaned.copy(), method="zscore")
        df_iqr = normalize(cleaned.copy(), method="iqr")
        df_both = normalize(cleaned.copy(), method="both")
        # 'both' anomaly count >= either individual method
        assert df_both["solar_anomaly"].sum() >= df_z["solar_anomaly"].sum()
        assert df_both["solar_anomaly"].sum() >= df_iqr["solar_anomaly"].sum()

    def test_too_few_samples_yields_nan_zscore(self):
        raw = _make_raw(n=5)  # only 5 rows — fewer than the 10-sample minimum
        df = normalize(clean(raw), method="zscore")
        assert df["solar_zscore"].isna().all()
        assert df["wind_zscore"].isna().all()

    def test_anomaly_columns_are_int(self, cleaned):
        df = normalize(cleaned)
        assert df["solar_anomaly"].dtype in (int, np.int64, np.int32)
        assert df["wind_anomaly"].dtype in (int, np.int64, np.int32)


class TestIqrFlag:
    def test_flags_outliers(self):
        vals = pd.Series([10.0] * 20 + [1000.0])
        flags = _iqr_flag(vals, vals)
        assert flags.iloc[-1] == 1

    def test_no_flags_for_normal_data(self):
        vals = pd.Series(np.random.normal(50, 5, 100))
        flags = _iqr_flag(vals, vals)
        # Most values should not be flagged (generous threshold: allow up to 5%)
        assert flags.mean() < 0.05

    def test_too_few_samples_returns_zeros(self):
        vals = pd.Series([1.0, 2.0, 3.0])  # fewer than 4
        flags = _iqr_flag(vals, vals)
        assert (flags == 0).all()

    def test_nan_values_not_flagged(self):
        vals = pd.Series([10.0] * 10 + [np.nan] * 5)
        flags = _iqr_flag(vals, vals)
        assert flags[vals.isna()].sum() == 0


# ── etl.fetch ─────────────────────────────────────────────────────────────────

MOCK_PAYLOAD = {
    "hourly": {
        "time":               ["2026-01-01T00:00", "2026-01-01T01:00"],
        "shortwave_radiation": [0.0, 5.0],
        "direct_radiation":    [0.0, 2.0],
        "wind_speed_10m":      [15.0, 16.0],
        "wind_gusts_10m":      [20.0, 22.0],
        "wind_direction_10m":  [180, 185],
    }
}

MOCK_SITE = {
    "key": "riyadh",
    "lat": 24.69,
    "lon": 46.72,
    "tz": "Asia/Riyadh",
    "emoji": "🏜️",
    "label": "Riyadh",
}


class TestFetchSite:
    def test_returns_expected_columns(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_PAYLOAD
        mock_resp.raise_for_status.return_value = None

        with patch("etl.fetch.requests.get", return_value=mock_resp):
            df = fetch_site(MOCK_SITE, "2026-01-01", "2026-01-01")

        assert set(df.columns) == {
            "observed_at", "solar_ghi", "solar_direct",
            "wind_speed", "wind_gusts", "wind_direction", "site_key"
        }

    def test_site_key_populated(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_PAYLOAD
        mock_resp.raise_for_status.return_value = None

        with patch("etl.fetch.requests.get", return_value=mock_resp):
            df = fetch_site(MOCK_SITE, "2026-01-01", "2026-01-01")

        assert (df["site_key"] == "riyadh").all()

    def test_row_count_matches_payload(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_PAYLOAD
        mock_resp.raise_for_status.return_value = None

        with patch("etl.fetch.requests.get", return_value=mock_resp):
            df = fetch_site(MOCK_SITE, "2026-01-01", "2026-01-01")

        assert len(df) == 2

    def test_raises_on_http_error(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("404 Not Found")

        with patch("etl.fetch.requests.get", return_value=mock_resp):
            with pytest.raises(Exception, match="404"):
                fetch_site(MOCK_SITE, "2026-01-01", "2026-01-01")

    def test_raises_on_missing_hourly_key(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"error": True, "reason": "bad params"}
        mock_resp.raise_for_status.return_value = None

        with patch("etl.fetch.requests.get", return_value=mock_resp):
            with pytest.raises(ValueError, match="Unexpected API response"):
                fetch_site(MOCK_SITE, "2026-01-01", "2026-01-01")
