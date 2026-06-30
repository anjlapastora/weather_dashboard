# Helios — Solar & Wind Monitor

A production-grade dashboard for monitoring hourly solar radiation and wind speed
across three climatically distinct sites, built with React + Plotly.js.

---

## Quick Start (zero dependencies)

The dashboard is a **single HTML file** that runs directly in any modern browser
with no build step, no Node.js, and no API key.

```bash
# Option 1 — just open it
open index.html

# Option 2 — serve it locally (avoids any CORS edge cases)
npx serve .            # Node.js
python3 -m http.server # Python
php -S localhost:8000  # PHP
```

Then visit `http://localhost:3000` (or whichever port is shown).

---

## Production Build (Vite + React)

When you're ready to deploy or bundle for production:

### 1. Prerequisites
```bash
node --version   # ≥ 18 required
npm --version    # ≥ 9 required
```

### 2. Scaffold a Vite project
```bash
npm create vite@latest helios -- --template react
cd helios
```

### 3. Install dependencies
```bash
npm install
npm install plotly.js-dist-min react-plotly.js
```

### 4. Copy source files
Copy `index.html` content into `src/App.jsx`, splitting the components into
their own files under `src/components/`:
```
src/
  components/
    KpiCard.jsx
    TimeSeriesChart.jsx
    WindRose.jsx
    AnomalyTable.jsx
    Sidebar.jsx
  utils/
    api.js          ← fetchSiteData()
    anomaly.js      ← detectAnomalies()
    stats.js        ← calcStats()
  constants.js      ← LOCATIONS, PLOTLY config
  App.jsx
  main.jsx
  index.css
```

### 5. Run dev server
```bash
npm run dev
```

### 6. Build for production
```bash
npm run build       # outputs to dist/
npm run preview     # preview the production build locally
```

### 7. Deploy
The `dist/` folder is a static site — host it anywhere:

| Platform    | Command / Steps |
|-------------|----------------|
| **Vercel**  | `npx vercel --prod` |
| **Netlify** | Drag `dist/` into netlify.com/drop |
| **GitHub Pages** | `npm run build` → push `dist/` to `gh-pages` branch |
| **Nginx**   | Copy `dist/` to `/var/www/html` |

---

## Dashboard Features

| Feature | Detail |
|---------|--------|
| **Sites** | Riyadh 🏜️ · Wellington 🌬️ · Manila 🌧️ (all togglable) |
| **Date range** | Any window within Open-Meteo's archive (back to ~2022) |
| **Time-series** | Plotly multi-trace with zoom, pan, hover tooltips |
| **Secondary overlay** | Dotted trace on right Y-axis for the other variable |
| **Anomaly detection** | Z-Score (adjustable σ threshold) or IQR method |
| **Anomaly markers** | Red ✕ markers on chart + full log table |
| **KPI cards** | Avg/peak solar, avg/max wind, anomaly count with pulse alert |
| **Wind roses** | Polar bar charts showing directional distribution |
| **Status bar** | Live fetch state + last-updated timestamp |

---

## Data Source

Open-Meteo Historical Archive API — free, no authentication required.

```
https://archive-api.open-meteo.com/v1/archive
  ?latitude=24.69
  &longitude=46.72
  &start_date=YYYY-MM-DD
  &end_date=YYYY-MM-DD
  &hourly=shortwave_radiation,direct_radiation,
          wind_speed_10m,wind_gusts_10m,wind_direction_10m
  &timezone=Asia/Riyadh
  &wind_speed_unit=kmh
```

Variables used:

| API Variable | Label | Unit |
|---|---|---|
| `shortwave_radiation` | Solar GHI | W/m² |
| `direct_radiation` | Direct Solar | W/m² |
| `wind_speed_10m` | Wind Speed | km/h |
| `wind_gusts_10m` | Wind Gusts | km/h |
| `wind_direction_10m` | Wind Direction | ° |

---

## Customizing Sites

Edit the `LOCATIONS` object at the top of the script:

```js
const LOCATIONS = {
  your_site: {
    key: 'your_site',
    label: 'City Name',
    region: 'Country',
    emoji: '🌍',
    lat: 0.00, lon: 0.00,
    tz: 'UTC',          // IANA timezone string
    color: '#FF6B6B',   // hex color for charts
    colorDim: 'rgba(255,107,107,0.12)',
    colorBorder: 'rgba(255,107,107,0.3)',
  },
};
```

---

## Extending to a Full React App

To add more features in the Vite version:

```bash
# State management (if data gets complex)
npm install zustand

# Date picker component
npm install react-datepicker

# CSV/XLSX export
npm install xlsx

# Persistent caching
npm install @tanstack/react-query
```

The `react-query` library is especially useful here — replace the manual
`fetch` calls with `useQuery` hooks and you get caching, background refetch,
and loading states for free.

---

## License

Data: Open-Meteo CC BY 4.0. Code: MIT.
