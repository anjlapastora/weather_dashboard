Open-Meteo API
      │
      ▼
 Python ETL Pipeline  ←── runs on schedule or on-demand
  ├── Fetch (requests)
  ├── Clean  (handle nulls, duplicates, bad timestamps)
  ├── Normalize (z-score, unit standardization)
  ├── Flag outliers (IQR / z-score)
  └── Write to SQLite
           │
           ▼
      SQLite Database
      ├── sites
      ├── raw_observations
      └── cleaned_observations
           │
           ▼
     Flask REST API  ←── serves your React/Streamlit frontend
      ├── GET /api/sites
      ├── GET /api/data?site=riyadh&start=...&end=...
      └── GET /api/anomalies?site=...