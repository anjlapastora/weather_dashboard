# Dashboard UI Guide

## Layout

The dashboard is divided into three vertical sections:

```
┌─────────────┬──────────────────────────────────────────────────┐
│             │  Top bar (logo + date range badge)               │
│   Sidebar   ├──────────────────────────────────────────────────┤
│  (260 px)   │  Canvas (scrollable)                             │
│             │   ├─ KPI row (3 cards)                           │
│             │   ├─ Time Series chart                           │
│             │   ├─ Bottom row                                  │
│             │      ├─ Anomaly table                            │
│             │      └─ Wind Roses                               │
└─────────────┴──────────────────────────────────────────────────┘
              Status bar (last update, data source)
```

---

## Sidebar

### Site selector

Three toggleable site buttons: Riyadh, Wellington, Manila. Click to activate or deactivate. Active sites appear in their colour accent; inactive sites are greyed out. All three are active by default.

Only active sites fetch data and appear in charts and KPI cards.

### Date Range

Two date inputs: **Start** and **End**. Rules:
- Maximum allowed range: **30 days** (enforced by the UI — see below)
- End date cannot be after yesterday (data archive ends at yesterday)
- Start date cannot be after End date

**30-day clamp**: If you pick a Start date that would make the range exceed 30 days, End automatically clamps forward to Start + 30 days (capped at yesterday). Conversely, moving End back clamps Start forward to End − 30 days.

To apply a new date range, click **"Fetch Data"** (the button appears after you change dates). The dashboard re-fetches all active sites.

### Anomaly Detection

A toggle to show or hide anomaly markers on the time series chart. When enabled, red ◆ markers appear on anomalous data points.

---

## KPI Cards

One card per monitoring site, showing three metrics for the selected date range:

| Metric | Calculation |
|--------|------------|
| Avg Solar | Mean daytime GHI (W/m²) — nighttime zeros excluded |
| Max Solar | Highest single GHI reading (W/m²) |
| Avg Wind | Mean wind speed (km/h) — all hours |

Cards show "—" when data for a site is still loading or the site is inactive.

---

## Hourly Time Series Chart

An interactive Plotly chart with dual Y-axes:

- **Left axis**: Solar GHI (W/m²) — solid lines
- **Right axis**: Wind speed (km/h) — secondary lines (one per active site)
- **Red ◆ markers**: Anomalous hours (when "Show anomaly markers" is on)
- **Hover**: Shows all values for every active site at the hovered timestamp

### Interacting with the chart

- **Hover**: Unified tooltip shows all values at the hovered time
- **Click legend item**: Toggle individual traces on/off
- **Box-select or lasso**: Zoom into a time window
- **Double-click chart**: Reset zoom
- **Scroll/pinch**: Zoom in/out on the time axis

---

## Anomaly Table

A scrollable table below the chart listing every anomaly-flagged row across all active sites in the selected date range. Columns: site, timestamp, solar GHI, wind speed, which variable was flagged.

Rows are sorted by timestamp descending (most recent first).

---

## Wind Rose Charts

Three wind rose charts, one per site (Riyadh, Wellington, Manila), always showing all three sites regardless of the sidebar selection.

Each rose visualises:
- **Direction**: 16 compass directions — each petal points to where the wind came *from*
- **Petal length**: Frequency — how often wind came from that direction
- **Colour bands**: Speed bins (calm, light, moderate, strong, gale)

Interpretation tips:
- A long petal in a direction = prevailing wind from that direction
- Wellington's roses typically show strong southerly dominance
- Riyadh often shows north-northwest (shamal) patterns

---

## Chatbot Assistant

A floating 💬 button in the bottom-right corner opens the Helios AI Assistant. It connects to the local RAG chatbot service on port 8000 and can answer questions about the dashboard, sites, data, and anomaly detection in natural language.

If the chatbot service is not running, the assistant will display a connection error message. Start it with `uvicorn app:app --port 8000` from the `chatbot/` directory.

---

## Status Bar

Runs along the bottom of the main panel:
- **Green dot**: data loaded successfully
- **Animated dot**: fetching in progress
- **Red dot**: connection error (Flask backend unreachable)
- **Timestamp**: when the last fetch completed
- **Data attribution**: Open-Meteo Archive API, CC BY 4.0
