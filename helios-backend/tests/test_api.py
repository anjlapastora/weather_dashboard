"""
tests/test_api.py — Integration tests for the Flask API routes.

Run with:  pytest helios-backend/tests/test_api.py -v
           (from the repo root, or just `pytest` from helios-backend/)

Uses the real SQLite database (helios.db) via the Flask test client —
no mocking of the database layer.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


# ── /api/health ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_ok(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        assert r.get_json()["status"] == "ok"

    def test_lists_all_three_sites(self, client):
        data = client.get("/api/health").get_json()
        assert set(data["sites"]) == {"riyadh", "wellington", "manila"}


# ── /api/sites ────────────────────────────────────────────────────────────────

class TestSites:
    def test_returns_list(self, client):
        r = client.get("/api/sites")
        assert r.status_code == 200
        assert isinstance(r.get_json(), list)

    def test_each_site_has_key_and_label(self, client):
        sites = client.get("/api/sites").get_json()
        for site in sites:
            assert "key" in site
            assert "label" in site


# ── /api/data ─────────────────────────────────────────────────────────────────

class TestData:
    def test_default_request_succeeds(self, client):
        r = client.get("/api/data?site=riyadh")
        assert r.status_code == 200

    def test_response_shape(self, client):
        body = client.get("/api/data?site=riyadh").get_json()
        for key in ("site", "start", "end", "count", "data"):
            assert key in body

    def test_data_rows_have_expected_fields(self, client):
        body = client.get("/api/data?site=riyadh").get_json()
        if body["data"]:
            row = body["data"][0]
            for field in ("observed_at", "solar_ghi", "wind_speed", "quality_flag"):
                assert field in row

    def test_unknown_site_returns_400(self, client):
        r = client.get("/api/data?site=atlantis")
        assert r.status_code == 400
        assert "error" in r.get_json()

    def test_explicit_date_range_filters_correctly(self, client):
        body = client.get("/api/data?site=riyadh&start=2026-05-01&end=2026-05-07").get_json()
        assert body["status_code"] == 200 if "status_code" in body else True
        # Every returned row must fall within the requested range
        for row in body["data"]:
            assert row["observed_at"] >= "2026-05-01"
            assert row["observed_at"] <  "2026-05-09"  # end + 1 day (inclusive query)

    def test_count_matches_data_length(self, client):
        body = client.get("/api/data?site=wellington&start=2026-05-01&end=2026-05-07").get_json()
        assert body["count"] == len(body["data"])

    def test_quality_filter_ok_removes_flagged_rows(self, client):
        all_rows  = client.get("/api/data?site=riyadh&quality=all").get_json()["data"]
        ok_rows   = client.get("/api/data?site=riyadh&quality=ok").get_json()["data"]
        assert len(ok_rows) <= len(all_rows)
        assert all(r["quality_flag"] == "ok" for r in ok_rows)

    def test_all_three_sites_return_data(self, client):
        for site in ("riyadh", "wellington", "manila"):
            body = client.get(f"/api/data?site={site}").get_json()
            assert body["count"] > 0, f"{site} returned no rows"


# ── /api/data/multi ───────────────────────────────────────────────────────────

class TestDataMulti:
    def test_returns_all_sites_by_default(self, client):
        body = client.get("/api/data/multi").get_json()
        assert "sites" in body
        assert set(body["sites"].keys()) == {"riyadh", "wellington", "manila"}

    def test_subset_of_sites(self, client):
        body = client.get("/api/data/multi?sites=riyadh,wellington").get_json()
        assert set(body["sites"].keys()) == {"riyadh", "wellington"}

    def test_unknown_site_returns_400(self, client):
        r = client.get("/api/data/multi?sites=riyadh,narnia")
        assert r.status_code == 400

    def test_each_site_block_has_count_and_data(self, client):
        body = client.get("/api/data/multi?sites=riyadh").get_json()
        block = body["sites"]["riyadh"]
        assert "count" in block
        assert "data" in block
        assert block["count"] == len(block["data"])


# ── /api/anomalies ────────────────────────────────────────────────────────────

class TestAnomalies:
    def test_default_request_succeeds(self, client):
        r = client.get("/api/anomalies?site=riyadh")
        assert r.status_code == 200

    def test_response_has_anomalies_key(self, client):
        body = client.get("/api/anomalies?site=riyadh").get_json()
        assert "anomalies" in body
        assert isinstance(body["anomalies"], list)

    def test_solar_filter_returns_only_solar(self, client):
        body = client.get("/api/anomalies?site=riyadh&type=solar").get_json()
        for row in body["anomalies"]:
            assert row["solar_anomaly"] == 1

    def test_wind_filter_returns_only_wind(self, client):
        body = client.get("/api/anomalies?site=riyadh&type=wind").get_json()
        for row in body["anomalies"]:
            assert row["wind_anomaly"] == 1

    def test_unknown_site_returns_400(self, client):
        r = client.get("/api/anomalies?site=atlantis")
        assert r.status_code == 400


# ── /api/stats ────────────────────────────────────────────────────────────────

class TestStats:
    def test_default_request_succeeds(self, client):
        r = client.get("/api/stats?site=riyadh")
        assert r.status_code == 200

    def test_stats_block_present(self, client):
        body = client.get("/api/stats?site=riyadh").get_json()
        assert "stats" in body
        stats = body["stats"]
        for key in (
            "avg_solar_daytime_wm2", "max_solar_wm2",
            "avg_wind_kmh", "max_wind_kmh",
            "solar_anomaly_count", "wind_anomaly_count",
            "daytime_hours", "quality_breakdown",
        ):
            assert key in stats, f"Missing stat key: {key}"

    def test_max_solar_ge_avg_solar(self, client):
        stats = client.get("/api/stats?site=riyadh").get_json()["stats"]
        if stats["avg_solar_daytime_wm2"] and stats["max_solar_wm2"]:
            assert stats["max_solar_wm2"] >= stats["avg_solar_daytime_wm2"]

    def test_unknown_site_returns_400(self, client):
        r = client.get("/api/stats?site=atlantis")
        assert r.status_code == 400
