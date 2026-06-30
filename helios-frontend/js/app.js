const { useState, useEffect, useRef } = React;

// ── Constants ─────────────────────────────────────────────────────────────────
const LOCATIONS = {
  riyadh: {
    key: 'riyadh', label: 'Riyadh', region: 'Saudi Arabia', emoji: '🏜️',
    lat: 24.69, lon: 46.72, tz: 'Asia/Riyadh',
    color: '#F59E0B', colorDim: 'rgba(245,158,11,0.12)', colorBorder: 'rgba(245,158,11,0.3)',
  },
  wellington: {
    key: 'wellington', label: 'Wellington', region: 'New Zealand', emoji: '🌬️',
    lat: -41.29, lon: 174.78, tz: 'Pacific/Auckland',
    color: '#60A5FA', colorDim: 'rgba(96,165,250,0.12)', colorBorder: 'rgba(96,165,250,0.3)',
  },
  manila: {
    key: 'manila', label: 'Manila', region: 'Philippines', emoji: '🌧️',
    lat: 14.60, lon: 120.98, tz: 'Asia/Manila',
    color: '#34D399', colorDim: 'rgba(52,211,153,0.12)', colorBorder: 'rgba(52,211,153,0.3)',
  },
};

const PLOTLY_LAYOUT_BASE = {
  paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
  font: { family: 'Inter, system-ui', color: '#94A3B8', size: 11 },
  xaxis: { type: 'date', gridcolor: '#1E2A40', zeroline: false, tickfont: { family: 'JetBrains Mono', size: 10 }, tickformat: '%b %d' },
  yaxis: { gridcolor: '#1E2A40', zeroline: false, tickfont: { family: 'JetBrains Mono', size: 10 } },
  legend: { x: 0, y: 1.06, orientation: 'h', font: { size: 11 }, bgcolor: 'transparent' },
  hovermode: 'x unified',
  hoverlabel: { bgcolor: '#1A2035', bordercolor: '#2A3550', font: { family: 'Inter, system-ui', size: 12 } },
};

const PLOTLY_CONFIG = {
  displayModeBar: true,
  modeBarButtonsToRemove: ['select2d','lasso2d','autoScale2d'],
  displaylogo: false, responsive: true,
};

// ── Date helpers ──────────────────────────────────────────────────────────────
const toISO = d => d.toISOString().slice(0, 10);
function daysAgo(n)  { const d = new Date(); d.setDate(d.getDate() - n); return d; }
function addDays(dateStr, n) { const d = new Date(dateStr + 'T00:00:00'); d.setDate(d.getDate() + n); return toISO(d); }
const MAX_RANGE_DAYS = 30;

// ── API fetch — Flask backend ─────────────────────────────────────────────────
async function fetchSiteData(siteKey, startDate, endDate) {
  const url = `http://localhost:5000/api/data?site=${siteKey}&start=${startDate}&end=${endDate}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`API error ${res.status} for ${siteKey}`);
  const json = await res.json();

  if (!json.data || !Array.isArray(json.data)) {
    throw new Error(`Unexpected response shape for ${siteKey}`);
  }

  return json.data.map(r => ({
    time:         new Date(r.observed_at),
    timeStr:      r.observed_at,
    solar:        r.solar_ghi      ?? null,
    solarDirect:  r.solar_direct   ?? null,
    wind:         r.wind_speed     ?? null,
    gusts:        r.wind_gusts     ?? null,
    windDir:      r.wind_direction ?? null,
    solarAnomaly: r.solar_anomaly  === 1,
    windAnomaly:  r.wind_anomaly   === 1,
    isDaytime:    r.is_daytime     === 1,
    qualityFlag:  r.quality_flag   ?? 'ok',
  }));
}

// ── Statistics ────────────────────────────────────────────────────────────────
function calcStats(rows) {
  if (!rows || rows.length === 0) return null;

  const avg = arr => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : 0;
  const max = arr => arr.length ? Math.max(...arr) : 0;

  const solarDay = rows.filter(r => r.isDaytime && r.solar != null).map(r => r.solar);
  const allSolar = rows.filter(r => r.solar != null && r.solar > 0).map(r => r.solar);
  const windAll  = rows.filter(r => r.wind  != null && r.wind  > 0).map(r => r.wind);
  const gustAll  = rows.filter(r => r.gusts != null && r.gusts > 0).map(r => r.gusts);

  return {
    avgSolar:          avg(solarDay),
    maxSolar:          max(allSolar),
    avgWind:           avg(windAll),
    maxWind:           max(gustAll.length ? gustAll : windAll),
    solarAnomalyCount: rows.filter(r => r.solarAnomaly).length,
    windAnomalyCount:  rows.filter(r => r.windAnomaly).length,
  };
}

// ── KPI Card ──────────────────────────────────────────────────────────────────
function KpiCard({ site, stats, loading, primaryVar }) {
  const isSolar   = primaryVar === 'solar';
  const anomCount = stats ? (isSolar ? stats.solarAnomalyCount : stats.windAnomalyCount) : 0;

  return (
    <div className="kpi-card" style={{ borderTop: `2px solid ${site.color}` }}>
      <div className="kpi-header">
        <div>
          <div className="kpi-site-name" style={{ color: site.color }}>{site.emoji} {site.label}</div>
          <div style={{ fontSize: 10, color: '#4B5563', marginTop: 1 }}>{site.region}</div>
        </div>
        {anomCount > 0 && (
          <div className="kpi-flag">
            <div className="pulse-ring" style={{ background: '#EF4444' }} />
            <div className="kpi-badge">⚠ {anomCount} anomalies</div>
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ color: '#4B5563', fontSize: 12, padding: '8px 0' }}>Loading…</div>
      ) : stats ? (
        <div className="kpi-metrics">
          <div className="kpi-primary">
            <div className="kpi-value" style={{ color: site.color }}>
              {isSolar ? Math.round(stats.avgSolar) : stats.avgWind.toFixed(1)}
            </div>
            <div className="kpi-unit">{isSolar ? 'W/m² avg solar' : 'km/h avg wind'}</div>
          </div>
          <div className="kpi-secondary">
            {isSolar ? (
              <>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Peak Solar</div>
                  <div className="kpi-stat-val">{Math.round(stats.maxSolar)} W/m²</div>
                </div>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Avg Wind</div>
                  <div className="kpi-stat-val">{stats.avgWind.toFixed(1)} km/h</div>
                </div>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Max Gust</div>
                  <div className="kpi-stat-val">{Math.round(stats.maxWind)} km/h</div>
                </div>
              </>
            ) : (
              <>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Max Gust</div>
                  <div className="kpi-stat-val">{Math.round(stats.maxWind)} km/h</div>
                </div>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Avg Solar</div>
                  <div className="kpi-stat-val">{Math.round(stats.avgSolar)} W/m²</div>
                </div>
                <div className="kpi-stat">
                  <div className="kpi-stat-label">Peak Solar</div>
                  <div className="kpi-stat-val">{Math.round(stats.maxSolar)} W/m²</div>
                </div>
              </>
            )}
          </div>
        </div>
      ) : (
        <div style={{ color: '#4B5563', fontSize: 12, padding: '8px 0' }}>No data loaded</div>
      )}
    </div>
  );
}

// ── Time Series Chart ─────────────────────────────────────────────────────────
function TimeSeriesChart({ allData, activeSites, primaryVar, showAnomalies, showSecondary }) {
  const divRef = useRef(null);
  const isSolar = primaryVar === 'solar';

  useEffect(() => {
    if (!divRef.current) return;
    const el = divRef.current;
    const traces = [];

    activeSites.forEach(key => {
      const site = LOCATIONS[key];
      const rows = allData[key];
      if (!rows || rows.length === 0) return;

      const times     = rows.map(r => r.timeStr);
      const primary   = rows.map(r => isSolar ? r.solar : r.wind);
      const secondary = rows.map(r => isSolar ? r.wind  : r.solar);
      const primLabel = isSolar ? 'Solar GHI' : 'Wind Speed';
      const secLabel  = isSolar ? 'Wind'      : 'Solar GHI';

      traces.push({
        x: times, y: primary,
        type: 'scatter', mode: 'lines',
        name: site.label,
        line: { color: site.color, width: 1.5 },
        legendgroup: key,
        hovertemplate: `<b>${site.label}</b><br>%{x|%b %d %H:%M}<br>${primLabel}: <b>%{y:.1f}</b><extra></extra>`,
      });

      if (showAnomalies) {
        const anomRows = rows.filter(r => isSolar ? r.solarAnomaly : r.windAnomaly);
        if (anomRows.length > 0) {
          traces.push({
            x: anomRows.map(r => r.timeStr),
            y: anomRows.map(r => isSolar ? r.solar : r.wind),
            type: 'scatter', mode: 'markers',
            name: `${site.label} ⚠`,
            legendgroup: key, showlegend: false,
            marker: { color: '#EF4444', size: 7, symbol: 'x', line: { width: 1.5, color: '#fff' } },
            hovertemplate: `<b>⚠ Anomaly – ${site.label}</b><br>%{x|%b %d %H:%M}<br>${primLabel}: <b>%{y:.1f}</b><extra></extra>`,
          });
        }
      }

      if (showSecondary) {
        traces.push({
          x: times, y: secondary,
          type: 'scatter', mode: 'lines',
          name: `${site.label} — ${secLabel}`,
          legendgroup: key, showlegend: true,
          line: { color: site.color, width: 1.5, dash: 'dot' },
          yaxis: 'y2', opacity: 0.7,
          hovertemplate: `<b>${site.label}</b><br>%{x|%b %d %H:%M}<br>${secLabel}: <b>%{y:.1f}</b><extra></extra>`,
        });
      }
    });

    const layout = {
      ...PLOTLY_LAYOUT_BASE,
      height: 320,
      margin: { l: 56, r: showSecondary ? 60 : 16, t: 8, b: 40 },
      yaxis: {
        ...PLOTLY_LAYOUT_BASE.yaxis,
        title: { text: isSolar ? 'Solar GHI (W/m²)' : 'Wind Speed (km/h)', font: { size: 10 } },
      },
      ...(showSecondary ? {
        yaxis2: {
          overlaying: 'y', side: 'right',
          gridcolor: 'transparent', zeroline: false,
          tickfont: { family: 'JetBrains Mono', size: 9, color: '#94A3B8' },
          title: { text: isSolar ? 'Wind (km/h)' : 'Solar (W/m²)', font: { size: 9, color: '#94A3B8' } },
        },
      } : {}),
    };

    Plotly.react(el, traces, layout, PLOTLY_CONFIG);
  }, [allData, activeSites, primaryVar, showAnomalies, showSecondary]);

  return <div ref={divRef} style={{ width: '100%', height: 320 }} />;
}

// ── Wind Rose ─────────────────────────────────────────────────────────────────
function WindRose({ site, rows }) {
  const divRef = useRef(null);

  useEffect(() => {
    if (!divRef.current || !rows || rows.length === 0) return;

    const dirs = rows.filter(r => r.windDir != null).map(r => r.windDir);
    const numBins = 16;
    const binSize = 360 / numBins;
    const counts = new Array(numBins).fill(0);
    dirs.forEach(d => { counts[Math.round(d / binSize) % numBins]++; });

    const labels = ['N','NNE','NE','ENE','E','ESE','SE','SSE','S','SSW','SW','WSW','W','WNW','NW','NNW'];

    Plotly.react(divRef.current, [{
      type: 'barpolar',
      r:     [...counts, counts[0]],
      theta: [...labels, labels[0]],
      marker: { color: site.color, opacity: 0.85, line: { color: 'rgba(0,0,0,0.2)', width: 0.5 } },
    }], {
      polar: {
        bgcolor: 'transparent',
        angularaxis: {
          direction: 'clockwise', rotation: 90,
          tickfont: { size: 9, color: '#64748B', family: 'Inter' },
          gridcolor: '#1E2A40', linecolor: '#1E2A40',
        },
        radialaxis: { showticklabels: false, gridcolor: '#1E2A40', linecolor: 'transparent' },
      },
      paper_bgcolor: 'transparent', plot_bgcolor: 'transparent',
      margin: { l: 20, r: 20, t: 28, b: 10 },
      title: { text: `${site.emoji} ${site.label}`, font: { size: 11, color: site.color, family: 'Inter' }, x: 0.5 },
      showlegend: false,
    }, { ...PLOTLY_CONFIG, displayModeBar: false });
  }, [rows]);

  return <div ref={divRef} style={{ width: '100%', height: 200 }} />;
}

// ── Anomaly Table ─────────────────────────────────────────────────────────────
function AnomalyTable({ allData, activeSites, primaryVar }) {
  const isSolar = primaryVar === 'solar';

  const flagged = [];
  activeSites.forEach(key => {
    const site = LOCATIONS[key];
    const rows = allData[key];
    if (!rows) return;
    rows.filter(r => isSolar ? r.solarAnomaly : r.windAnomaly)
        .forEach(r => flagged.push({ site, ...r }));
  });
  flagged.sort((a, b) => b.time - a.time);

  const fmt = d => d.toLocaleString('en-US', {
    month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false,
  });

  const label = isSolar ? 'Solar' : 'Wind';

  return (
    <div id="tour-log" className="table-panel">
      <div className="panel-header">
        <div className="panel-title"><span>⚠</span> {label} Anomaly Log</div>
        {flagged.length > 0 && <div className="panel-count">{flagged.length} flagged hours</div>}
      </div>
      <div className="table-wrap">
        {flagged.length === 0 ? (
          <div className="empty-state">No {label.toLowerCase()} anomalies detected.</div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Site</th>
                <th>Timestamp</th>
                {isSolar ? (
                  <><th>Solar GHI</th><th>Wind</th></>
                ) : (
                  <><th>Wind Speed</th><th>Gusts</th></>
                )}
                <th>Flag</th>
              </tr>
            </thead>
            <tbody>
              {flagged.map((r, i) => (
                <tr key={i}>
                  <td className="td-site" style={{ color: r.site.color }}>{r.site.emoji} {r.site.label}</td>
                  <td>{fmt(r.time)}</td>
                  {isSolar ? (
                    <>
                      <td>{r.solar != null ? `${Math.round(r.solar)} W/m²` : '—'}</td>
                      <td>{r.wind  != null ? `${r.wind.toFixed(1)} km/h`   : '—'}</td>
                    </>
                  ) : (
                    <>
                      <td>{r.wind  != null ? `${r.wind.toFixed(1)} km/h`   : '—'}</td>
                      <td>{r.gusts != null ? `${Math.round(r.gusts)} km/h` : '—'}</td>
                    </>
                  )}
                  <td>
                    <div className="flag-cell">
                      {isSolar
                        ? <span className="flag-tag flag-solar">☀ Solar</span>
                        : <span className="flag-tag flag-wind">💨 Wind</span>
                      }
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

// ── Toggle ────────────────────────────────────────────────────────────────────
function Toggle({ on, onChange }) {
  return <div className={`toggle ${on ? 'on' : ''}`} onClick={() => onChange(!on)} />;
}

// ── Chatbot ───────────────────────────────────────────────────────────────────
const CHATBOT_API = 'http://localhost:8000';
const CHAT_SUGGESTIONS = ['What is Helios?', 'Explain anomaly detection', 'Tell me about Wellington', 'What is GHI?'];

function DashboardChatbot() {
  const { useState, useRef, useEffect } = React;
  const [open, setOpen]       = useState(false);
  const [messages, setMessages] = useState([{
    from: 'bot',
    text: "Hi! I'm the Helios AI assistant 🌞\nPowered by a local RAG pipeline (Ollama + ChromaDB).\nAsk me anything about this monitoring dashboard.",
  }]);
  const [input, setInput]     = useState('');
  const [loading, setLoading] = useState(false);
  const [online, setOnline]   = useState(true);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    fetch(`${CHATBOT_API}/health`, { signal: AbortSignal.timeout(3000) })
      .then(r => setOnline(r.ok))
      .catch(() => setOnline(false));
  }, [open]);

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);

  async function send(text) {
    const q = (text || input).trim();
    if (!q || loading) return;
    setInput('');
    setMessages(prev => [...prev, { from: 'user', text: q }]);
    setLoading(true);
    try {
      const resp = await fetch(`${CHATBOT_API}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: q }),
        signal: AbortSignal.timeout(60000),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}));
        throw new Error(err.detail || `HTTP ${resp.status}`);
      }
      const data = await resp.json();
      const sourceNote = data.sources?.length
        ? `\n\n📄 Sources: ${data.sources.join(', ')}`
        : '';
      setMessages(prev => [...prev, { from: 'bot', text: data.reply + sourceNote }]);
      setOnline(true);
    } catch (err) {
      const isTimeout = err.name === 'TimeoutError';
      setOnline(false);
      setMessages(prev => [...prev, {
        from: 'bot',
        text: isTimeout
          ? '⏱ The AI took too long to respond. The model may still be loading — try again in a moment.'
          : `⚠ Could not reach the chatbot service.\n\nMake sure it's running:\n  cd chatbot\n  uvicorn app:app --port 8000`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="chatbot-wrap">
      {open && (
        <div className="chatbot-panel">
          <div className="chatbot-header">
            <div className="chatbot-header-title">
              <div className="chatbot-header-dot" style={{ background: online ? '#22c55e' : '#ef4444', boxShadow: `0 0 6px ${online ? '#22c55e' : '#ef4444'}` }} />
              Helios AI Assistant
            </div>
            <button className="chatbot-close" onClick={() => setOpen(false)}>✕</button>
          </div>

          <div className="chatbot-messages">
            {messages.map((msg, i) => (
              <div key={i} className={`chatbot-msg chatbot-msg-${msg.from}`}>
                {msg.text}
              </div>
            ))}
            {loading && (
              <div className="chatbot-msg chatbot-msg-bot chatbot-typing">
                <span /><span /><span />
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {!loading && (
            <div className="chatbot-suggestions">
              {CHAT_SUGGESTIONS.map(s => (
                <button key={s} className="chatbot-chip" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          )}

          <div className="chatbot-input-row">
            <input
              className="chatbot-input"
              type="text"
              placeholder={loading ? 'Thinking…' : 'Ask the AI about the dashboard…'}
              value={input}
              disabled={loading}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }}
            />
            <button className="chatbot-send" onClick={() => send()} disabled={!input.trim() || loading}>↑</button>
          </div>
        </div>
      )}
      <button id="tour-chatbot" className="chatbot-fab" onClick={() => setOpen(o => !o)} title="Helios AI Assistant">
        {open ? '✕' : '💬'}
      </button>
    </div>
  );
}

// ── Walkthrough Tour ──────────────────────────────────────────────────────────
const TOUR_STEPS = [
  {
    id: null,
    title: 'Welcome to Helios 👋',
    body: 'This short walkthrough will show you how to use the Solar & Wind Monitoring Dashboard. You can skip it at any time and relaunch it by pressing the ? button in the top bar.',
    pos: 'center',
  },
  {
    id: 'tour-sites',
    title: 'Step 1 — Select Sites',
    body: 'Check or uncheck sites here to include them on the charts. You can view one, two, or all three at once. Each site keeps its own colour throughout the entire dashboard.',
    pos: 'right',
  },
  {
    id: 'tour-dates',
    title: 'Step 2 — Date Range',
    body: 'Set the period you want to explore. The maximum window is 30 days. The pickers are linked — extending one end automatically clamps the other so the window stays within limits.',
    pos: 'right',
  },
  {
    id: 'tour-anomaly',
    title: 'Step 3 — Anomaly Detection',
    body: 'The backend pipeline flags unusual readings using the IQR method (interquartile range). Toggle "Show anomaly markers" to overlay red diamonds on the chart wherever an anomaly was detected.',
    pos: 'right',
  },
  {
    id: 'tour-opts',
    title: 'Step 4 — Chart Options',
    body: 'Choose what the main chart shows: ☀ Solar GHI in W/m², or 💨 Wind Speed in km/h. Toggle the Secondary Overlay to add the other variable on a second axis — great for spotting solar-wind correlations.',
    pos: 'right',
  },
  {
    id: 'tour-refresh',
    title: 'Step 5 — Load Data',
    body: 'After choosing your sites and date range, click ↻ Refresh Data to fetch results from the backend. The button shows a spinner while loading. Data is fetched live from the Flask API.',
    pos: 'right',
  },
  {
    id: 'tour-kpis',
    title: 'Step 6 — Summary Cards',
    body: 'These cards show key statistics for the loaded period — average daytime solar irradiance, peak GHI, average wind speed, and the highest gust recorded. The coloured top border matches each site\'s chart line.',
    pos: 'bottom',
  },
  {
    id: 'tour-chart',
    title: 'Step 7 — Hourly Time Series',
    body: 'The main chart plots your selected variable hour-by-hour. Hover to inspect exact values. Click and drag to zoom into a period, then double-click to zoom back out. Red diamonds mark anomalous hours (when markers are on).',
    pos: 'top',
  },
  {
    id: 'tour-roses',
    title: 'Step 8 — Wind Rose',
    body: 'Wind roses show how often wind blows from each compass direction and how fast. Longer petals mean more frequent wind from that direction. Especially revealing for Wellington, which is dominated by strong Cook Strait westerlies.',
    pos: 'top',
  },
  {
    id: 'tour-log',
    title: 'Step 9 — Anomaly Log',
    body: 'Every hour flagged as anomalous by the IQR pipeline appears here as a table row. Columns show the site, exact timestamp, solar and wind values, and which variables were flagged. The header shows the total count.',
    pos: 'top',
  },
  {
    id: 'tour-chatbot',
    title: 'Step 10 — AI Assistant',
    body: 'Click this button to open the Helios AI chatbot. Ask it anything — "Which site had the highest solar last week?", "Were there wind anomalies recently?", or "Explain the anomaly method." Time-based questions use live database data.',
    pos: 'left',
  },
  {
    id: null,
    title: "You're all set! ✅",
    body: 'Select your sites, pick a date range, and click Refresh Data to get started. The ? button in the top bar will relaunch this tour whenever you need it.',
    pos: 'center',
  },
];

function WalkthroughTour({ onClose }) {
  const [step, setStep] = useState(0);
  const [rect, setRect] = useState(null);
  const current = TOUR_STEPS[step];
  const total = TOUR_STEPS.length;

  useEffect(() => {
    if (!current.id) { setRect(null); return; }
    function measure() {
      const el = document.getElementById(current.id);
      if (el) setRect(el.getBoundingClientRect());
    }
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [step]);

  function finish() {
    try { localStorage.setItem('helios_tour_seen', '1'); } catch (_) {}
    onClose();
  }
  const next = () => step < total - 1 ? setStep(s => s + 1) : finish();
  const back = () => setStep(s => s - 1);

  function cardStyle() {
    const W = 320, pad = 16;
    const vw = window.innerWidth, vh = window.innerHeight;
    if (!rect || current.pos === 'center') {
      return { top: '50%', left: '50%', transform: 'translate(-50%,-50%)' };
    }
    const { top, bottom, left, right } = rect;
    if (current.pos === 'right') {
      return {
        top: Math.min(Math.max(top, pad), vh - 300),
        left: Math.min(right + 16, vw - W - pad),
      };
    }
    if (current.pos === 'left') {
      return {
        top: Math.min(Math.max(top - 80, pad), vh - 300),
        left: Math.max(left - W - 16, pad),
      };
    }
    if (current.pos === 'bottom') {
      return {
        top: Math.min(bottom + 16, vh - 300),
        left: Math.min(Math.max(left, pad), vw - W - pad),
      };
    }
    return {
      top: Math.max(top - 260, pad),
      left: Math.min(Math.max(left, pad), vw - W - pad),
    };
  }

  const spotPad = 6;
  return (
    <div className="tour-overlay">
      <div className="tour-backdrop" onClick={() => {}} />

      {rect && (
        <div className="tour-spotlight" style={{
          top:    rect.top    - spotPad,
          left:   rect.left   - spotPad,
          width:  rect.width  + spotPad * 2,
          height: rect.height + spotPad * 2,
        }} />
      )}

      <div className="tour-card" style={cardStyle()}>
        {current.id && (
          <div className="tour-card-step">
            {step} of {total - 2}
          </div>
        )}
        <h3>{current.title}</h3>
        <p>{current.body}</p>
        <div className="tour-card-footer">
          <div className="tour-dots">
            {TOUR_STEPS.map((_, i) => (
              <div key={i} className={`tour-dot ${i === step ? 'active' : ''}`} />
            ))}
          </div>
          <button className="tour-btn" onClick={finish}>Skip</button>
          {step > 0 && (
            <button className="tour-btn" onClick={back}>Back</button>
          )}
          <button className="tour-btn primary" onClick={next}>
            {step === total - 1 ? 'Done' : 'Next →'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── App ───────────────────────────────────────────────────────────────────────
function App() {
  const [activeSites,   setActiveSites]   = useState(['riyadh', 'wellington', 'manila']);
  const [startDate,     setStartDate]     = useState(toISO(daysAgo(30)));
  const [endDate,       setEndDate]       = useState(toISO(new Date()));
  const [showAnomalies, setShowAnomalies] = useState(true);
  const [showSecondary, setShowSecondary] = useState(true);
  const [primaryVar,    setPrimaryVar]    = useState('solar');
  const [allData,       setAllData]       = useState({});
  const [loading,       setLoading]       = useState(false);
  const [error,         setError]         = useState(null);
  const [lastFetched,   setLastFetched]   = useState(null);
  const [showTour,      setShowTour]      = useState(() => {
    try { return !localStorage.getItem('helios_tour_seen'); } catch (_) { return true; }
  });

  const allStats = {};
  Object.keys(allData).forEach(key => {
    allStats[key] = calcStats(allData[key]);
  });

  async function loadData() {
    if (!activeSites.length) return;
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.all(
        activeSites.map(key =>
          fetchSiteData(key, startDate, endDate).then(rows => [key, rows])
        )
      );
      const map = {};
      results.forEach(([key, rows]) => { map[key] = rows; });
      setAllData(map);
      setLastFetched(new Date());
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadData(); }, []);

  function toggleSite(key) {
    setActiveSites(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  }

  const renderedSites = activeSites.filter(k => allData[k]);

  return (
    <div className="app">

      {/* ── Sidebar ── */}
      <div className="sidebar">
        <div className="sidebar-logo">
          <div className="logo-wordmark">Helio<span>s</span></div>
          <div className="logo-sub">Solar & Wind Monitor</div>
        </div>

        {/* Sites */}
        <div id="tour-sites" className="sidebar-section">
          <div className="sidebar-label">Sites</div>
          {Object.values(LOCATIONS).map(site => (
            <div
              key={site.key}
              className={`site-item ${activeSites.includes(site.key) ? 'active' : ''}`}
              onClick={() => toggleSite(site.key)}
            >
              <div className="site-check"
                style={activeSites.includes(site.key)
                  ? { background: site.color, borderColor: 'transparent' }
                  : {}}>
                {activeSites.includes(site.key) &&
                  <span style={{ color: '#000', fontSize: 9, fontWeight: 700 }}>✓</span>}
              </div>
              <div>
                <div className="site-name">{site.emoji} {site.label}</div>
                <div className="site-coords">{site.lat}, {site.lon}</div>
              </div>
              <div className="site-dot" style={{ background: site.color, marginLeft: 'auto' }} />
            </div>
          ))}
        </div>

        {/* Date Range */}
        <div id="tour-dates" className="sidebar-section">
          <div className="sidebar-label">Date Range</div>
          <div className="date-row">
            <div className="date-field">
              <label>Start</label>
              <input type="date" value={startDate}
                min={addDays(endDate, -MAX_RANGE_DAYS)}
                max={endDate}
                onChange={e => {
                  const s = e.target.value;
                  setStartDate(s);
                  const maxEnd = addDays(s, MAX_RANGE_DAYS);
                  const today = toISO(new Date());
                  if (endDate > maxEnd) setEndDate(maxEnd < today ? maxEnd : today);
                }} />
            </div>
            <div className="date-field">
              <label>End</label>
              <input type="date" value={endDate}
                min={startDate}
                max={[addDays(startDate, MAX_RANGE_DAYS), toISO(new Date())].sort()[0]}
                onChange={e => {
                  const en = e.target.value;
                  setEndDate(en);
                  const minStart = addDays(en, -MAX_RANGE_DAYS);
                  if (startDate < minStart) setStartDate(minStart);
                }} />
            </div>
          </div>
        </div>

        {/* Anomaly */}
        <div id="tour-anomaly" className="sidebar-section">
          <div className="sidebar-label">Anomaly Detection</div>
          <div style={{ fontSize: 11, color: 'var(--muted2)', marginBottom: 10, lineHeight: 1.6 }}>
            Method: <span style={{ color: 'var(--accent)', fontWeight: 600 }}>IQR</span>
            <br/>Flags values beyond 1.5× the interquartile range. Computed by the backend pipeline.
          </div>
          <div className="toggle-row">
            <span className="toggle-label">Show anomaly markers</span>
            <Toggle on={showAnomalies} onChange={setShowAnomalies} />
          </div>
        </div>

        {/* Chart Options */}
        <div id="tour-opts" className="sidebar-section">
          <div className="sidebar-label">Primary Variable</div>
          <div className="var-pills">
            <button
              className={`var-pill ${primaryVar === 'solar' ? 'active' : ''}`}
              onClick={() => setPrimaryVar('solar')}>☀ Solar</button>
            <button
              className={`var-pill ${primaryVar === 'wind' ? 'active' : ''}`}
              onClick={() => setPrimaryVar('wind')}>💨 Wind</button>
          </div>
          <div className="toggle-row" style={{ marginTop: 10 }}>
            <span className="toggle-label">Secondary overlay</span>
            <Toggle on={showSecondary} onChange={setShowSecondary} />
          </div>
        </div>

        {/* Refresh */}
        <div id="tour-refresh" style={{ padding: '12px 16px 16px' }}>
          <button
            className="fetch-btn"
            onClick={loadData}
            disabled={loading || !activeSites.length}
            style={{ width: '100%', justifyContent: 'center' }}>
            {loading
              ? <><div className="spinner" /> Fetching…</>
              : '↻ Refresh Data'}
          </button>
        </div>
      </div>

      {/* ── Main canvas ── */}
      <div className="main">

        {/* Top bar */}
        <div className="topbar">
          <div className="topbar-title">MONITORING DASHBOARD</div>
          {lastFetched && (
            <div className="topbar-range">{startDate} → {endDate}</div>
          )}
          <div className="topbar-chips">
            {activeSites.map(key => {
              const s = LOCATIONS[key];
              return (
                <div key={key} className="chip"
                  style={{ color: s.color, borderColor: s.colorBorder, background: s.colorDim }}>
                  <div className="chip-dot" style={{ background: s.color }} />
                  {s.label}
                </div>
              );
            })}
          </div>
          <button
            onClick={() => setShowTour(true)}
            title="Relaunch walkthrough"
            style={{
              marginLeft: 12, width: 28, height: 28, borderRadius: '50%',
              border: '1px solid #1F2937', background: 'transparent',
              color: '#6B7280', fontSize: 13, fontWeight: 700,
              cursor: 'pointer', display: 'flex', alignItems: 'center',
              justifyContent: 'center', flexShrink: 0,
              lineHeight: 1,
            }}>?</button>
        </div>

        {/* Scrollable canvas */}
        <div className="canvas">

          {error && (
            <div className="error-box">⚠ {error} — Is Flask running at localhost:5000?</div>
          )}

          {/* KPI cards */}
          <div id="tour-kpis" className="kpi-row">
            {Object.values(LOCATIONS).map(site => (
              <KpiCard
                key={site.key}
                site={site}
                stats={allData[site.key] ? allStats[site.key] : null}
                loading={loading && activeSites.includes(site.key)}
                primaryVar={primaryVar}
              />
            ))}
          </div>

          {/* Time series */}
          <div id="tour-chart" className="chart-panel">
            <div className="chart-header">
              <div className="chart-title">
                <div className="chart-title-icon" />
                Hourly Time Series
              </div>
              <div className="chart-legend">
                {renderedSites.map(key => (
                  <div key={key} className="legend-item">
                    <div className="legend-line" style={{ background: LOCATIONS[key].color }} />
                    {LOCATIONS[key].label}
                  </div>
                ))}
                {showAnomalies && renderedSites.length > 0 && (
                  <div className="legend-item">
                    <div className="legend-marker" style={{ background: '#EF4444' }} />
                    Anomaly
                  </div>
                )}
              </div>
            </div>
            <div className="chart-body">
              {loading ? (
                <div className="loading-overlay">
                  <div className="big-spinner" />
                  Loading data from backend…
                </div>
              ) : renderedSites.length > 0 ? (
                <TimeSeriesChart
                  allData={allData}
                  activeSites={renderedSites}
                  primaryVar={primaryVar}
                  showAnomalies={showAnomalies}
                  showSecondary={showSecondary}
                />
              ) : (
                <div className="loading-overlay" style={{ color: '#4B5563' }}>
                  Select sites and click Refresh Data
                </div>
              )}
            </div>
          </div>

          {/* Anomaly table + Wind roses */}
          <div className="bottom-row">
            <AnomalyTable allData={allData} activeSites={renderedSites} primaryVar={primaryVar} />

            <div id="tour-roses" className="roses-panel">
              <div className="panel-header">
                <div className="panel-title">🧭 Wind Direction Distribution</div>
              </div>
              <div className="roses-grid">
                {Object.values(LOCATIONS).map(site => (
                  <div key={site.key} className="rose-slot">
                    {allData[site.key] ? (
                      <WindRose site={site} rows={allData[site.key]} />
                    ) : (
                      <div style={{
                        height: 200, display: 'flex', alignItems: 'center',
                        justifyContent: 'center', color: '#4B5563', fontSize: 12,
                      }}>
                        {activeSites.includes(site.key) ? 'Loading…' : 'Not selected'}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>

        </div>{/* end .canvas */}

        {/* Status bar */}
        <div className="status-bar">
          <div className={`status-dot ${loading ? 'loading' : error ? 'error' : ''}`} />
          <div className="status-text">
            {loading
              ? 'Fetching data…'
              : error
              ? 'Connection error — check Flask is running'
              : lastFetched
              ? `Last updated ${lastFetched.toLocaleTimeString()}`
              : 'Ready'}
          </div>
          <div className="status-source">
            Data: <a href="https://open-meteo.com" target="_blank" rel="noreferrer">Open-Meteo Archive API</a>
            · CC BY 4.0 · No API key required
          </div>
        </div>

      </div>{/* end .main */}

      <DashboardChatbot />

      {showTour && <WalkthroughTour onClose={() => setShowTour(false)} />}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
