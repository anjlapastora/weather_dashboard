# Helios Data Insights — Recent Observations

This document contains answers grounded in actual database readings as of the week ending 2026-06-30.
Use it to answer questions about recent performance, anomalies, and site comparisons.

---

## Site Name Clarification

The Helios dashboard monitors **three named sites**. There are no generic "Site A / B / C" labels.
If a user says "Site A", "Site B", or "Site C", always ask which site they mean before answering:

> "Could you clarify which site you mean? Helios monitors Riyadh (Saudi Arabia),
> Wellington (New Zealand), and Manila (Philippines)."

---

## Q: Which site had the highest average solar radiation last week?

**Period:** 2026-06-23 to 2026-06-30 (daytime hours only)

| Site       | Avg Solar GHI (daytime) | Peak Solar GHI |
|------------|------------------------|----------------|
| **Riyadh**     | **544 W/m²** ← highest | 977 W/m²       |
| Manila     | 430 W/m²               | 879 W/m²       |
| Wellington | 96 W/m²                | 360 W/m²       |

**Answer:** Riyadh had the highest average solar radiation last week at 544 W/m² (daytime average),
peaking at 977 W/m². This is consistent with its desert climate and high solar angle in June.
Manila recorded 430 W/m² average but is constrained by tropical cloud cover and monsoon season.
Wellington recorded only 96 W/m² — expected for a Southern Hemisphere winter site in late June
with fewer daylight hours and lower solar angle.

---

## Q: Were there any anomalous wind speed readings in the last 7 days?

**Period:** 2026-06-23 to 2026-06-30

### Wellington — 10 wind anomalies (significant storm event)

A sustained high-wind event occurred on **2026-06-26** from 03:00 to 20:00 NZST.

| Timestamp        | Wind Speed | Gusts    | Z-score |
|------------------|-----------|----------|---------|
| 2026-06-26 03:00 | 66.4 km/h | 131.0 km/h | 2.63  |
| 2026-06-26 10:00 | 67.0 km/h | 132.1 km/h | 2.67  |
| 2026-06-26 12:00 | 70.0 km/h | 132.5 km/h | 2.86  |
| 2026-06-26 13:00 | 72.2 km/h | 142.6 km/h | 3.00  |
| 2026-06-26 14:00 | 69.7 km/h | 141.1 km/h | 2.84  |
| 2026-06-26 15:00 | 71.7 km/h | 140.8 km/h | 2.97  |
| 2026-06-26 16:00 | 74.0 km/h | 144.7 km/h | 3.12  |
| 2026-06-26 17:00 | 70.3 km/h | 146.2 km/h | 2.88  |
| 2026-06-26 18:00 | 68.2 km/h | 138.6 km/h | 2.74  |
| 2026-06-26 20:00 | 67.0 km/h | 131.8 km/h | 2.67  |

Peak gust: **146.2 km/h** at 17:00. This 10-hour window represents a significant storm consistent
with Wellington's exposed Cook Strait position. All readings were flagged by both IQR and Z-score methods.

### Manila — 1 wind anomaly

| Timestamp        | Wind Speed | Gusts   | Z-score |
|------------------|-----------|---------|---------|
| 2026-06-25 14:00 | 24.3 km/h | 58.3 km/h | 3.04 |

A single spike on the afternoon of June 25, likely associated with convective activity during
Manila's wet season. Gust of 58.3 km/h is notable but isolated.

### Riyadh — 1 wind anomaly

| Timestamp        | Wind Speed | Gusts   | Z-score |
|------------------|-----------|---------|---------|
| 2026-06-27 17:00 | 17.0 km/h | 42.8 km/h | 2.80 |

One anomalous reading on June 27 at 17:00 local time, consistent with late-afternoon shamal
(northwesterly desert wind). Isolated event with no surrounding elevated readings.

---

## Q: Compare generation potential across all three sites for the past month

**Period:** 2026-05-31 to 2026-06-30

| Site       | Avg Solar GHI (daytime) | Peak Solar | Avg Wind | Max Gust  | Wind Anomalies |
|------------|------------------------|------------|----------|-----------|----------------|
| **Riyadh**     | **541 W/m²**       | 984 W/m²   | 7.5 km/h | 45.7 km/h | 2              |
| **Manila**     | 452 W/m²           | 946 W/m²   | 9.0 km/h | 61.9 km/h | 2              |
| **Wellington** | 168 W/m²           | 403 W/m²   | 26.9 km/h | 146.2 km/h | 10            |

### Solar generation potential

- **Riyadh** is the strongest solar site by a wide margin — 541 W/m² daytime average over 30 days,
  consistent with its arid desert climate and near-zero cloud cover. No solar anomalies detected.
- **Manila** is a viable solar site at 452 W/m² average, though June marks the start of its rainy
  season. Peak GHI of 946 W/m² shows excellent clear-sky potential on good days.
- **Wellington** has the weakest solar output at 168 W/m² — June is mid-winter in New Zealand,
  with short days, low solar angle, and frequent overcast conditions. Solar generation potential
  is significantly reduced compared to the other two sites.

### Wind generation potential

- **Wellington** dominates wind energy potential with an average of 26.9 km/h and a monthly
  maximum gust of 146.2 km/h. However, the 10 wind anomalies indicate extreme events that would
  require turbine cut-out procedures. Wellington's Cook Strait location makes it one of the
  windiest inhabited areas on Earth.
- **Manila** averages 9.0 km/h — moderate wind, with occasional strong gusts (61.9 km/h max)
  tied to typhoon-season convection. Consistent but not exceptional for utility-scale wind.
- **Riyadh** averages 7.5 km/h — low wind speed, occasional shamal events. Wind energy is
  not competitive here; solar is the dominant renewable resource.

### Summary recommendation

| Site       | Best For         | Notes                                         |
|------------|-----------------|-----------------------------------------------|
| Riyadh     | Solar (primary) | Highest irradiance, low wind, arid stability  |
| Manila     | Solar + backup  | Good solar with seasonal variation            |
| Wellington | Wind (primary)  | World-class wind resource, limited solar      |
