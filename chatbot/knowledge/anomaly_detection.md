# Anomaly Detection

## Purpose

Anomalies in solar and wind data indicate unusual conditions — sensor malfunctions, extreme weather events, data transmission errors, or genuinely rare meteorological phenomena. Helios flags these automatically so users can investigate further.

## Methods available

Helios implements two statistical methods, controlled by the `DEFAULT_METHOD` setting in `config.py`.

### 1. IQR (Interquartile Range) — default

**How it works**:
1. Compute Q1 (25th percentile) and Q3 (75th percentile) from the reference distribution
2. Compute IQR = Q3 − Q1
3. Flag any value outside `[Q1 − 1.5×IQR, Q3 + 1.5×IQR]`

**Advantages**: Robust to extreme outliers when computing bounds (unlike mean-based methods); no Gaussian distribution assumption.

**For solar**: Only **daytime** hours are used to compute the IQR bounds. Using nighttime zeros would make the lower bound negative (meaningless for irradiance).

**For wind**: All hours are used — wind blows day and night.

### 2. Z-Score

**How it works**:
1. Compute mean (μ) and standard deviation (σ) from the reference distribution
2. Compute Z = (value − μ) / σ
3. Flag values where |Z| > threshold (default: `DEFAULT_Z_THRESHOLD = 2.5`)

**Advantages**: Simple, interpretable (e.g. "this reading is 3 standard deviations above normal").

**Limitation**: Sensitive to extreme outliers when computing μ and σ.

**For solar Z-score**: Again computed on **daytime hours only**; nighttime rows are assigned Z = 0 (not anomalous).

### 3. Both (union)

When `method = 'both'`, a row is flagged as anomalous if **either** IQR or Z-score flags it. This is the most sensitive setting.

## Columns produced

| Column | Type | Description |
|--------|------|-------------|
| `solar_zscore` | float | Z-score of solar_ghi (0 for nighttime) |
| `wind_zscore` | float | Z-score of wind_speed |
| `solar_iqr_flag` | int (0/1) | 1 if solar_ghi is an IQR outlier |
| `wind_iqr_flag` | int (0/1) | 1 if wind_speed is an IQR outlier |
| `solar_anomaly` | int (0/1) | Final anomaly flag for solar (method-dependent) |
| `wind_anomaly` | int (0/1) | Final anomaly flag for wind (method-dependent) |

## Visualisation on the dashboard

- **Time Series Chart**: Anomalous hours are shown as red diamond (◆) markers overlaid on the relevant trace.
- **Anomaly Table**: A table below the chart lists every flagged row with its timestamp, GHI value, wind speed, and which variable was flagged.
- **Toggle**: The "Show anomaly markers" toggle in the sidebar hides/shows the red markers without removing the underlying data.

## Edge cases handled

| Situation | Behaviour |
|-----------|-----------|
| Fewer than 10 daytime solar samples | `solar_zscore` set to NaN; IQR returns all zeros |
| Fewer than 10 wind samples | `wind_zscore` set to NaN; IQR returns all zeros |
| Fewer than 4 samples for IQR | IQR returns all zeros |
| NaN values | Never flagged — NaN ≠ outlier, it is missing data |
| Physical-bounds violations | Cleaned to NaN *before* anomaly detection; they never appear as anomalies |

## Practical interpretation

- A **solar anomaly** in the middle of the day at Riyadh could indicate a sudden dust storm (GHI drop), a sensor issue, or an unusual cloud incursion.
- A **wind anomaly** at Wellington is more common and often corresponds to Cook Strait gale events.
- A **wind anomaly** at Manila during June–November often coincides with tropical cyclone activity.



