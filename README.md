# Helios Backend — Setup & Run Guide

Flask REST API + SQLite + ETL pipeline for solar radiation and wind speed data.

---

## 1. Prerequisites

- Python 3.10 or higher
- pip

Check your versions:
```bash
python3 --version
pip3 --version
```

---

## 2. Project Structure

```
helios-backend/
├── app.py              ← Flask entry point + APScheduler
├── config.py           ← All settings (sites, thresholds, paths)
├── requirements.txt
│
├── db/
│   ├── schema.py       ← CREATE TABLE + seed sites
│   └── queries.py      ← All SQLite read/write helpers
│
├── etl/
│   ├── fetch.py        ← Open-Meteo API call
│   ├── clean.py        ← Null handling, dedup, physical bounds
│   ├── normalize.py    ← Z-score, IQR, anomaly flags
│   └── pipeline.py     ← Orchestrator (fetch → clean → normalize → save)
│
├── api/
│   └── routes.py       ← All Flask /api/* endpoints
│
└── logs/
    └── helios.log      ← Auto-created on first run
```

---

## 3. Installation

```bash
# Clone or download the project
cd helios-backend

# Create a virtual environment (strongly recommended)
python3 -m venv venv
source venv/bin/activate       # macOS / Linux
venv\Scripts\activate          # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## 4. First-Time Setup

### Step 1 — Initialise the database

Creates `db/helios.db` and all tables. Safe to re-run.

```bash
python -m db.schema
```

Expected output:
```
✓ Database initialised at /your/path/helios-backend/db/helios.db
```

### Step 2 — Run the ETL pipeline (fetch + clean + save)

Pulls the last 30 days of data for all three sites from Open-Meteo.

```bash
# All sites (recommended for first run)
python -m etl.pipeline

# One site only
python -m etl.pipeline --site riyadh

# Custom date range
python -m etl.pipeline --start 2026-05-01 --end 2026-05-31

# Different anomaly method
python -m etl.pipeline --method iqr
python -m etl.pipeline --method zscore --z 3.0
```

Expected output (per site):
```
=======================================================
  Pipeline: 🏜️ Riyadh  |  2026-05-29 → 2026-06-28
=======================================================

[1/4] Fetching from Open-Meteo…
      720 hourly rows received
[2/4] Saving raw observations…
      720 rows written (duplicates skipped)
[3/4] Cleaning…
  [clean] 720 → 720 rows (0 dropped, 0 incomplete)
[4/4] Normalizing & flagging anomalies…
  [normalize] Flagged 12 solar anomalies, 8 wind anomalies
      720 rows written to cleaned_observations

✓ Done: {'site': 'riyadh', 'rows_fetched': 720, ...}
```

### Step 3 — Start the Flask API

```bash
python app.py
```

Expected output:
```
Initialising database…
✓ Database initialised at .../helios.db
Scheduler started — pipeline runs daily at 02:00
Starting Helios on http://0.0.0.0:5000
```

---

## 5. API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/sites` | All monitoring sites |
| GET | `/api/data?site=riyadh&start=...&end=...` | Cleaned time-series |
| GET | `/api/data/multi?sites=riyadh,manila` | Multiple sites at once |
| GET | `/api/anomalies?site=riyadh` | Anomaly-flagged rows |
| GET | `/api/stats?site=riyadh` | Summary statistics |
| GET | `/api/pipeline/runs` | ETL audit log |
| POST | `/api/pipeline/trigger` | Manual pipeline trigger |

### Example requests

```bash
# Health check
curl http://localhost:5000/api/health

# 30-day data for Riyadh
curl "http://localhost:5000/api/data?site=riyadh&start=2026-05-29&end=2026-06-28"

# All sites in one request
curl "http://localhost:5000/api/data/multi?sites=riyadh,wellington,manila"

# Anomalies for Wellington
curl "http://localhost:5000/api/anomalies?site=wellington&type=wind"

# Summary stats
curl "http://localhost:5000/api/stats?site=manila"

# Manually trigger pipeline via API
curl -X POST http://localhost:5000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{"site": "riyadh", "method": "zscore", "z_thresh": 2.5}'

# Trigger all sites
curl -X POST http://localhost:5000/api/pipeline/trigger \
  -H "Content-Type: application/json" \
  -d '{}'
```

---

## 6. Connecting to the React Frontend

In `helios_dashboard.html`, replace the direct Open-Meteo fetch with your backend:

```js
// Before
const res = await fetch(`https://archive-api.open-meteo.com/v1/archive?...`);

// After
const res = await fetch(
  `http://localhost:5000/api/data?site=${siteKey}&start=${start}&end=${end}`
);
const json = await res.json();
const rows = json.data;   // array of cleaned observation objects
```

CORS is pre-configured in the backend so the React app can call it from any port.

---

## 7. Scheduled Pipeline

The backend auto-runs the pipeline every day at **2:00 AM** (server time) via APScheduler.
To change the schedule, edit `config.py`:

```python
PIPELINE_CRON_HOUR   = 2    # 0–23
PIPELINE_CRON_MINUTE = 0    # 0–59
PIPELINE_DAYS_BACK   = 30   # days of history per run
```

To use a system cron job instead (e.g. on a server without the scheduler):

```bash
# crontab -e
0 2 * * * cd /path/to/helios-backend && \
  /path/to/venv/bin/python -m etl.pipeline >> logs/cron.log 2>&1
```

---

## 8. Development Mode

```bash
FLASK_DEBUG=true python app.py
```

This enables hot-reload and disables the scheduler (to avoid double-runs).

---

## 9. Inspecting the Database

```bash
# Open the SQLite shell
sqlite3 db/helios.db

-- Row counts
SELECT 'raw',     COUNT(*) FROM raw_observations
UNION ALL
SELECT 'cleaned', COUNT(*) FROM cleaned_observations;

-- Recent anomalies
SELECT s.label, c.observed_at, c.solar_ghi, c.wind_speed
FROM cleaned_observations c
JOIN sites s ON s.id = c.site_id
WHERE c.solar_anomaly = 1 OR c.wind_anomaly = 1
ORDER BY c.observed_at DESC
LIMIT 20;

-- Pipeline run history
SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT 5;

.exit
```

---

## 10. Troubleshooting

| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: flask` | Activate your venv: `source venv/bin/activate` |
| `No such table: sites` | Run `python -m db.schema` first |
| `Empty data from API` | Check date range — archive ends yesterday |
| CORS error in browser | Confirm Flask is running and `flask-cors` is installed |
| Port 5000 already in use | Change `FLASK_PORT` in `config.py` or kill the existing process |
