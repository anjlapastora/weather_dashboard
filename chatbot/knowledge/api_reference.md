# API Reference

## Flask Data API (port 5000)

The Flask backend serves cleaned sensor data from the SQLite database.

### GET /api/health

Health check. No parameters.

**Response**:
```json
{ "status": "ok", "sites": ["riyadh", "wellington", "manila"] }
```

---

### GET /api/sites

Returns all monitoring sites stored in the database.

**Response**: Array of site objects with fields: `id`, `key`, `label`, `region`, `lat`, `lon`, `tz`.

---

### GET /api/data

Cleaned hourly time-series for one site.

**Query parameters**:
- `site` (string) — site key: `riyadh`, `wellington`, or `manila`. Default: `riyadh`
- `start` (string) — YYYY-MM-DD. Default: 30 days ago
- `end` (string) — YYYY-MM-DD. Default: yesterday
- `quality` (string) — `ok` (only complete rows) or `all` (include incomplete). Default: `all`

**Response**:
```json
{
  "site": "riyadh",
  "start": "2026-05-30",
  "end": "2026-06-28",
  "count": 696,
  "data": [
    {
      "id": 1,
      "site_id": 1,
      "observed_at": "2026-05-30T00:00",
      "solar_ghi": 0.0,
      "solar_direct": 0.0,
      "wind_speed": 14.2,
      "wind_gusts": 20.1,
      "wind_direction": 315,
      "solar_zscore": 0.0,
      "wind_zscore": -0.3,
      "solar_iqr_flag": 0,
      "wind_iqr_flag": 0,
      "solar_anomaly": 0,
      "wind_anomaly": 0,
      "is_daytime": 0,
      "quality_flag": "ok"
    }
  ]
}
```

---

### GET /api/data/multi

Cleaned data for multiple sites in one request.

**Query parameters**:
- `sites` (string) — comma-separated site keys. Default: all three sites
- `start`, `end` — same as `/api/data`

**Response**:
```json
{
  "start": "2026-05-30",
  "end": "2026-06-28",
  "sites": {
    "riyadh":    { "count": 696, "data": [...] },
    "wellington": { "count": 696, "data": [...] },
    "manila":    { "count": 696, "data": [...] }
  }
}
```

---

### GET /api/anomalies

Anomaly-flagged rows for one site.

**Query parameters**:
- `site` — site key. Default: `riyadh`
- `type` — `solar`, `wind`, or `all`. Default: `all`
- `start`, `end` — date range

**Response**: Same envelope as `/api/data` but with `anomalies` key instead of `data`.

---

### GET /api/stats

Summary statistics for one site over a date range.

**Response**:
```json
{
  "site": "riyadh",
  "count": 696,
  "stats": {
    "avg_solar_daytime_wm2": 612.4,
    "max_solar_wm2": 1047.2,
    "avg_wind_kmh": 18.6,
    "max_wind_kmh": 72.1,
    "solar_anomaly_count": 14,
    "wind_anomaly_count": 8,
    "daytime_hours": 373,
    "quality_breakdown": { "ok": 690, "incomplete": 6 }
  }
}
```

---

### POST /api/pipeline/trigger

Manually run the ETL pipeline (synchronous).

**Request body** (all optional):
```json
{
  "site": "riyadh",
  "start": "2026-06-01",
  "end": "2026-06-28",
  "method": "iqr",
  "z_thresh": 2.5
}
```

Omit `site` to run all three sites.

---

### GET /api/pipeline/runs

Recent ETL pipeline audit log (last 20 runs by default).

---

## Chatbot RAG API (port 8000)

The FastAPI chatbot service provides AI-powered Q&A about the dashboard.

### GET /health

Health check for the chatbot service.

**Response**:
```json
{ "status": "ok", "model": "llama3.2", "indexed_docs": 42 }
```

---

### POST /chat

Send a message and receive an AI response grounded in the dashboard knowledge base.

**Request body**:
```json
{ "message": "What anomaly detection method does Helios use?" }
```

**Response**:
```json
{
  "reply": "Helios uses the IQR (Interquartile Range) method by default...",
  "sources": ["anomaly_detection.md", "overview.md"]
}
```

---

### POST /rebuild

Rebuild the ChromaDB vector index from the knowledge documents. Useful after adding or editing knowledge files.

**Response**:
```json
{ "status": "ok", "message": "Index rebuilt from 6 documents" }
```
