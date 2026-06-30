# Helios Dashboard — Overview

## What is Helios?

Helios is a solar and wind monitoring dashboard that tracks energy-relevant weather conditions across three global sites in near real-time. It was built to demonstrate an end-to-end data engineering pipeline: automated ingestion, cleaning, anomaly detection, and interactive visualization.

The dashboard is a single-page React application served as a static HTML file. It connects to a local Flask REST API that reads from a SQLite database populated by a nightly ETL pipeline.

## Key capabilities

- Hourly solar irradiance (GHI) and wind speed data for three sites
- Automated anomaly detection using the IQR method
- Interactive time series chart with per-site overlays
- Wind rose charts showing directional wind distribution
- KPI summary cards (average/peak solar and wind values)
- Date range picker limited to 30 days for performance
- Anomaly table listing every flagged observation

## Technology stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 (in-browser via CDN + Babel standalone) |
| Charts | Plotly.js 2.32 |
| Backend API | Flask 3 + Flask-CORS |
| Database | SQLite (file: helios.db) |
| ETL scheduler | APScheduler (daily at 02:00) |
| Data source | Open-Meteo Archive API |
| Chatbot | FastAPI + LangChain + ChromaDB + Ollama |

## How the data flows

1. **Fetch** — `etl/fetch.py` calls the Open-Meteo Archive API for each site and returns a raw DataFrame of hourly observations.
2. **Clean** — `etl/clean.py` removes duplicates, enforces physical bounds (solar ≤ 1400 W/m², wind ≤ 250 km/h), forward-fills short wind gaps, and sets the `quality_flag`.
3. **Normalize** — `etl/normalize.py` computes Z-scores and IQR outlier flags, producing `solar_anomaly` and `wind_anomaly` columns.
4. **Store** — Results are upserted into `raw_observations` and `cleaned_observations` tables in SQLite.
5. **Serve** — The Flask API exposes the cleaned data to the frontend via REST endpoints.
6. **Visualise** — The React frontend fetches all three sites on load and renders charts, KPI cards, and the anomaly table.

## Ports at a glance

| Service | Default port |
|---------|-------------|
| Flask data API | 5000 |
| Chatbot RAG API | 8000 |
| Static file server (dev) | any free port |
