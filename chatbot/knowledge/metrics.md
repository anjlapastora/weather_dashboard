# Solar and Wind Metrics

## Solar Irradiance

### Global Horizontal Irradiance (GHI)

GHI is the total solar power per unit area received on a horizontal surface. It is the sum of:
- **Direct Normal Irradiance (DNI)**: direct sunlight hitting the surface perpendicular to the sun's rays, projected onto horizontal
- **Diffuse Horizontal Irradiance (DHI)**: scattered sky radiation (from clouds, aerosols, atmosphere)

**Unit**: Watts per square metre (W/m²)

**Typical values**:
- Nighttime: 0 W/m²
- Overcast day: 50–200 W/m²
- Partly cloudy: 200–600 W/m²
- Clear sunny day: 600–1,100 W/m²
- Physical maximum (extraterrestrial): ~1,361 W/m² (solar constant)
- Database cap in Helios: 1,400 W/m² (beyond this = instrument error, cleaned to NaN)

### Solar Direct (solar_direct)

The direct component of solar radiation on a horizontal surface. Usually lower than GHI on clear days because it excludes diffuse sky radiation. Stored alongside GHI in Helios.

### Daytime detection

Helios marks a row as daytime (`is_daytime = 1`) when the raw GHI reading exceeds **10 W/m²** (the `DAYTIME_THRESHOLD` in `config.py`). Nighttime rows have `solar_ghi` and `solar_direct` set to **0** (not null) after cleaning.

### KPI — Average Solar

Displayed on each site's KPI card. Computed as the mean of `solar_ghi` for **daytime hours only** in the selected date range. Nighttime zeros are excluded so the average reflects actual irradiance potential.

### KPI — Max Solar

The single highest `solar_ghi` value recorded across the selected period (all hours, since nighttime max is 0 and daytime max is the figure of interest).

---

## Wind

### Wind Speed (wind_speed)

Sustained horizontal wind speed measured at **10 metres above ground level**.

**Unit**: Kilometres per hour (km/h)

**Typical values**:
- Calm: < 5 km/h
- Light breeze: 6–20 km/h
- Moderate: 20–40 km/h
- Strong/gale: 40–75 km/h
- Storm: 75–120 km/h
- Database cap in Helios: 250 km/h (beyond this = instrument error, cleaned to NaN)

### Wind Gusts (wind_gusts)

Short-duration peak wind speed, typically 20–40% higher than the sustained speed. Stored as `wind_gusts` in the database.

### Wind Direction (wind_direction)

Direction the wind is coming *from*, measured in degrees clockwise from north (0° = N, 90° = E, 180° = S, 270° = W).

### KPI — Average Wind

Mean `wind_speed` across **all hours** (day and night) in the selected date range.

### Data forward-filling

Helios forward-fills up to **2 consecutive** missing wind speed values using the most recent valid reading. Gaps longer than 2 hours are left as NaN and the row receives `quality_flag = 'incomplete'`.

---

## Quality Flags

Each cleaned observation carries a `quality_flag` string:

| Flag | Meaning |
|------|---------|
| `ok` | Both solar and wind values are present and within physical bounds |
| `incomplete` | One or more key fields (solar_ghi, wind_speed) is NaN after cleaning |

The dashboard's `/api/data` endpoint accepts a `quality=ok` parameter to filter out incomplete rows.
