"""
tests/test_dashboard_e2e.py — End-to-end browser tests for helios_dashboard.html.

Requires:
  - Playwright:  pip install playwright && python -m playwright install chromium
  - Flask backend running at localhost:5000  (python helios-backend/app.py)

Run with:
  pytest helios-backend/tests/test_dashboard_e2e.py -v
  (from the repo root, or just `pytest` from helios-backend/)

The suite spins up its own HTTP server for the static file and starts/stops the
Flask app as a subprocess fixture — no manual server management needed.
"""

import sys
import os
import subprocess
import socket
import time
import threading
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import date, timedelta

import pytest

REPO_ROOT     = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FILES_DIR     = os.path.join(REPO_ROOT, "files")
BACKEND_DIR   = os.path.join(REPO_ROOT, "helios-backend")
STATIC_PORT   = 8780
FLASK_PORT    = 5000
DASHBOARD_URL = f"http://localhost:{STATIC_PORT}/helios_dashboard.html"

MAX_RANGE_DAYS = 30  # must match the constant in the dashboard JS


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


@pytest.fixture(scope="session")
def static_server():
    """Serve files/ directory over HTTP so CDN scripts load correctly."""
    handler = SimpleHTTPRequestHandler
    handler.log_message = lambda *_: None  # suppress per-request noise
    httpd = HTTPServer(("", STATIC_PORT), handler)

    original_dir = os.getcwd()
    os.chdir(os.path.abspath(FILES_DIR))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield
    httpd.shutdown()
    os.chdir(original_dir)


@pytest.fixture(scope="session")
def flask_server():
    """Start the Flask backend as a subprocess if it isn't already running."""
    if _port_open("localhost", FLASK_PORT):
        yield  # already running externally
        return

    venv_python = os.path.join(REPO_ROOT, "venv", "bin", "python")
    python = venv_python if os.path.exists(venv_python) else sys.executable
    proc = subprocess.Popen(
        [python, "app.py"],
        cwd=os.path.abspath(BACKEND_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if _port_open("localhost", FLASK_PORT):
            break
        time.sleep(0.5)
    else:
        proc.terminate()
        pytest.skip("Flask backend failed to start within 10 seconds")

    yield
    proc.terminate()


@pytest.fixture(scope="session")
def browser_context(static_server, flask_server):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        yield context
        context.close()
        browser.close()


@pytest.fixture
def page(browser_context):
    """Page loaded to the dashboard; waits for date inputs to appear."""
    p = browser_context.new_page()
    p.goto(DASHBOARD_URL, wait_until="domcontentloaded")
    p.wait_for_selector('input[type="date"]', timeout=20_000)
    yield p
    p.close()


@pytest.fixture
def loaded_page(browser_context):
    """Page loaded to the dashboard; waits for the Plotly chart to render."""
    p = browser_context.new_page()
    p.goto(DASHBOARD_URL, wait_until="domcontentloaded")
    # .js-plotly-plot appears only after Plotly.react() succeeds (data loaded)
    p.wait_for_selector(".js-plotly-plot", timeout=30_000)
    yield p
    p.close()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _iso(d: date) -> str:
    return d.isoformat()


def _get_dates(page):
    """Return (start_str, end_str) from the two date inputs."""
    inputs = page.locator('input[type="date"]')
    return inputs.nth(0).input_value(), inputs.nth(1).input_value()


def _set_date(page, nth: int, value: str):
    """Set a date input by index (0=start, 1=end) and fire the change event."""
    loc = page.locator('input[type="date"]').nth(nth)
    loc.fill(value)
    loc.dispatch_event("change")


# ── Date-range clamp tests ────────────────────────────────────────────────────

class TestDateRangeClamp:
    def test_initial_range_is_within_30_days(self, page):
        start, end = _get_dates(page)
        delta = (date.fromisoformat(end) - date.fromisoformat(start)).days
        # daysAgo(30) → yesterday spans 29 days (30 days of data, inclusive on both ends)
        assert 0 < delta <= MAX_RANGE_DAYS

    def test_moving_start_forward_clamps_end(self, page):
        """Push start 10 days forward; the gap must still be ≤ 30 days."""
        start, end = _get_dates(page)
        current_end = date.fromisoformat(end)
        new_start   = current_end - timedelta(days=10)

        _set_date(page, 0, _iso(new_start))
        page.wait_for_timeout(400)

        start2, end2 = _get_dates(page)
        delta = (date.fromisoformat(end2) - date.fromisoformat(start2)).days
        assert delta <= MAX_RANGE_DAYS

    def test_moving_start_back_beyond_30_days_clamps_end(self, page):
        """Move start 40 days before the current end; end must clamp to start+30."""
        start, end = _get_dates(page)
        current_end = date.fromisoformat(end)
        new_start   = current_end - timedelta(days=40)

        _set_date(page, 0, _iso(new_start))
        page.wait_for_timeout(400)

        start2, end2 = _get_dates(page)
        delta = (date.fromisoformat(end2) - date.fromisoformat(start2)).days
        assert delta <= MAX_RANGE_DAYS

    def test_moving_end_back_beyond_30_days_clamps_start(self, page):
        """Move end so the gap would exceed 30 days; start should advance."""
        start, end = _get_dates(page)
        current_start = date.fromisoformat(start)
        new_end = current_start + timedelta(days=40)
        yesterday = date.today() - timedelta(days=1)
        new_end = min(new_end, yesterday)

        _set_date(page, 1, _iso(new_end))
        page.wait_for_timeout(400)

        start2, end2 = _get_dates(page)
        delta = (date.fromisoformat(end2) - date.fromisoformat(start2)).days
        assert delta <= MAX_RANGE_DAYS

    def test_range_exactly_30_days_is_accepted(self, page):
        """A gap of exactly 30 days must not trigger any clamping."""
        yesterday = date.today() - timedelta(days=1)
        start_30  = yesterday - timedelta(days=MAX_RANGE_DAYS)

        _set_date(page, 0, _iso(start_30))
        page.wait_for_timeout(200)
        _set_date(page, 1, _iso(yesterday))
        page.wait_for_timeout(400)

        start2, end2 = _get_dates(page)
        assert start2 == _iso(start_30), f"Start clamped unexpectedly: {start2}"
        assert end2   == _iso(yesterday), f"End clamped unexpectedly: {end2}"


# ── Chart render tests ────────────────────────────────────────────────────────

class TestChartRenders:
    def test_time_series_chart_visible(self, loaded_page):
        chart_div = loaded_page.query_selector(".chart-panel .js-plotly-plot")
        assert chart_div is not None, "Plotly chart div not found"
        box = chart_div.bounding_box()
        assert box is not None and box["height"] > 100

    def test_time_series_has_svg(self, loaded_page):
        svg = loaded_page.query_selector(".chart-panel svg.main-svg")
        assert svg is not None, "Plotly main-svg not rendered"

    def test_kpi_cards_render_with_data(self, loaded_page):
        cards = loaded_page.query_selector_all(".kpi-card")
        assert len(cards) >= 3
        values = [c.query_selector(".kpi-value") for c in cards]
        texts  = [v.inner_text() for v in values if v]
        assert any(t.strip() not in ("0", "—", "") for t in texts)

    def test_chart_panel_not_clipped(self, loaded_page):
        """chart-panel must be tall enough to show the full 320 px Plotly SVG."""
        panel = loaded_page.query_selector(".chart-panel")
        assert panel is not None
        box = panel.bounding_box()
        assert box["height"] >= 320, (
            f"chart-panel height {box['height']}px is too short — chart may be clipped"
        )
