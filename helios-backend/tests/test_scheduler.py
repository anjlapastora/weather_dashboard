"""
tests/test_scheduler.py — Tests for Celery task definitions and Beat schedule.

These tests run without a live Redis broker by using Celery's eager mode
(CELERY_TASK_ALWAYS_EAGER=True), which executes tasks synchronously inline.
"""

import pytest
from unittest.mock import patch, MagicMock
from datetime import date, timedelta

# Import tasks to register them with the Celery app before any test runs
import tasks  # noqa: F401


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def eager_celery():
    """Run all Celery tasks synchronously (no broker needed)."""
    from celery_app import celery
    celery.conf.update(
        task_always_eager=True,
        task_eager_propagates=True,
    )
    yield
    celery.conf.update(
        task_always_eager=False,
        task_eager_propagates=False,
    )


@pytest.fixture
def mock_run_all():
    """Patch the pipeline function at its source so the lazy import picks it up."""
    summaries = [
        {"site": "riyadh",     "status": "success", "rows_fetched": 24},
        {"site": "wellington", "status": "success", "rows_fetched": 24},
        {"site": "manila",     "status": "success", "rows_fetched": 24},
    ]
    with patch("etl.pipeline.run_all", return_value=summaries) as m:
        yield m


@pytest.fixture
def mock_run_site():
    """Patch the pipeline function at its source so the lazy import picks it up."""
    summary = {"site": "riyadh", "status": "success", "rows_fetched": 24}
    with patch("etl.pipeline.run_site", return_value=summary) as m:
        yield m


# ── Beat schedule ─────────────────────────────────────────────────────────────

class TestBeatSchedule:
    def test_daily_pipeline_task_registered(self):
        from celery_app import celery
        assert "daily-etl-pipeline" in celery.conf.beat_schedule

    def test_daily_pipeline_points_to_correct_task(self):
        from celery_app import celery
        entry = celery.conf.beat_schedule["daily-etl-pipeline"]
        assert entry["task"] == "tasks.run_daily_pipeline"

    def test_schedule_is_midnight(self):
        from celery_app import celery
        from celery.schedules import crontab
        entry  = celery.conf.beat_schedule["daily-etl-pipeline"]
        sched  = entry["schedule"]
        assert isinstance(sched, crontab)
        assert 0 in sched.hour
        assert 0 in sched.minute

    def test_celery_timezone_is_utc(self):
        from celery_app import celery
        assert celery.conf.timezone == "UTC"

    def test_celery_broker_url_configured(self):
        from celery_app import celery
        assert "redis://" in celery.conf.broker_url


# ── run_daily_pipeline task ───────────────────────────────────────────────────

class TestRunDailyPipelineTask:
    def test_task_is_registered(self):
        from celery_app import celery
        assert "tasks.run_daily_pipeline" in celery.tasks

    def test_task_returns_summaries(self, mock_run_all):
        from tasks import run_daily_pipeline
        result = run_daily_pipeline.delay()
        assert result.successful()
        summaries = result.get()
        assert isinstance(summaries, list)
        assert len(summaries) == 3

    def test_task_calls_run_all(self, mock_run_all):
        from tasks import run_daily_pipeline
        run_daily_pipeline.delay()
        mock_run_all.assert_called_once()

    def test_task_date_range_ends_yesterday(self, mock_run_all):
        from tasks import run_daily_pipeline
        run_daily_pipeline.delay()
        _, kwargs = mock_run_all.call_args
        args = mock_run_all.call_args[0]
        end_arg = args[1]
        expected_end = str(date.today() - timedelta(days=1))
        assert end_arg == expected_end

    def test_task_retries_on_failure(self):
        # Eager mode retries synchronously; after max_retries it raises
        # MaxRetriesExceededError (not RuntimeError), so match on Exception.
        from tasks import run_daily_pipeline
        with patch("etl.pipeline.run_all", side_effect=RuntimeError("network error")):
            with pytest.raises(Exception):
                run_daily_pipeline.delay().get()

    def test_task_max_retries_is_3(self):
        from tasks import run_daily_pipeline
        assert run_daily_pipeline.max_retries == 3


# ── run_site_pipeline task ────────────────────────────────────────────────────

class TestRunSitePipelineTask:
    def test_task_is_registered(self):
        from celery_app import celery
        assert "tasks.run_site_pipeline" in celery.tasks

    def test_task_returns_summary(self, mock_run_site):
        from tasks import run_site_pipeline
        result = run_site_pipeline.delay("riyadh", "2026-06-01", "2026-06-30")
        assert result.successful()
        summary = result.get()
        assert summary["site"] == "riyadh"
        assert summary["status"] == "success"

    def test_task_passes_correct_args(self, mock_run_site):
        from tasks import run_site_pipeline
        run_site_pipeline.delay("wellington", "2026-06-01", "2026-06-07")
        mock_run_site.assert_called_once_with("wellington", "2026-06-01", "2026-06-07")


# ── API endpoint: /pipeline/trigger ──────────────────────────────────────────

class TestPipelineTriggerEndpoint:
    @pytest.fixture
    def client(self):
        import sys, os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from app import create_app
        app = create_app()
        app.config["TESTING"] = True
        with app.test_client() as c:
            yield c

    def test_trigger_all_returns_202(self, client, mock_run_all):
        resp = client.post("/api/pipeline/trigger",
                           json={},
                           content_type="application/json")
        assert resp.status_code == 202

    def test_trigger_returns_task_id(self, client, mock_run_all):
        resp = client.post("/api/pipeline/trigger", json={})
        data = resp.get_json()
        assert "task_id" in data
        assert data["status"] == "queued"

    def test_trigger_site_queues_site_task(self, client, mock_run_site):
        resp = client.post("/api/pipeline/trigger",
                           json={"site": "riyadh",
                                 "start": "2026-06-01",
                                 "end": "2026-06-07"})
        assert resp.status_code == 202
        data = resp.get_json()
        assert data["site"] == "riyadh"

    def test_trigger_all_queues_daily_task(self, client, mock_run_all):
        resp = client.post("/api/pipeline/trigger", json={})
        data = resp.get_json()
        assert data["site"] == "all"

    def test_task_status_endpoint_returns_result(self, client, mock_run_all):
        trigger = client.post("/api/pipeline/trigger", json={})
        task_id = trigger.get_json()["task_id"]

        # Mock AsyncResult so the status check doesn't need a live Redis connection
        mock_ar = MagicMock()
        mock_ar.id     = task_id
        mock_ar.status = "SUCCESS"
        mock_ar.ready.return_value      = True
        mock_ar.successful.return_value = True
        mock_ar.result                  = [{"site": "all", "status": "success"}]

        with patch("celery.result.AsyncResult", return_value=mock_ar):
            status = client.get(f"/api/pipeline/task/{task_id}")

        assert status.status_code == 200
        data = status.get_json()
        assert data["task_id"] == task_id
        assert "status" in data
