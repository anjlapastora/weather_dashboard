# Helios Site Characteristics & Climate Context

This document provides timeless background on the three Helios monitoring sites.
Specific numbers for any given date range (solar averages, anomaly counts, etc.)
are supplied at query time from the live database — do not invent figures.

---

## Site Name Clarification

The Helios dashboard monitors **three named sites**. There are no generic labels
like "Site A", "Site B", or "Site C".
If a user says "Site A", "Site B", or "Site C", always respond with:

> "Could you clarify which site you mean? Helios monitors Riyadh (Saudi Arabia),
> Wellington (New Zealand), and Manila (Philippines)."

---

## Riyadh, Saudi Arabia — Solar-dominant site

**Climate:** Hot desert (Köppen BWh). Cloud cover is extremely rare; direct normal
irradiance is among the highest on Earth. Solar GHI regularly exceeds 900 W/m²
at solar noon in summer and stays above 700 W/m² for most of the year.

**Solar generation potential:** Riyadh is consistently the strongest solar site in
the Helios network. Daytime averages are typically 500–600 W/m² in summer and
300–400 W/m² in winter. Anomalous solar readings are rare because cloud-induced
drops are unusual.

**Wind generation potential:** Wind speeds are low (typical average 5–10 km/h).
Occasional *shamal* events (northwesterly desert winds) can produce gusts above
40 km/h, which may appear as wind anomalies. Wind energy is not competitive here;
solar is the dominant renewable resource.

---

## Wellington, New Zealand — Wind-dominant site

**Climate:** Temperate oceanic (Köppen Cfb), situated at the southern tip of the
North Island on the Cook Strait — one of the windiest inhabited locations on Earth.
Prevailing westerlies are strong and persistent, especially in winter (June–August).

**Wind generation potential:** Wellington is the strongest wind site in the Helios
network by a wide margin. Average wind speeds frequently exceed 25 km/h and gusts
during storm events can reach 130–150 km/h. Wind anomaly counts are higher here than
at the other two sites because of the frequency of genuine storm events, not because
of sensor errors.

**Solar generation potential:** Wellington is in the Southern Hemisphere, so June
is mid-winter: short days, a low solar angle, and frequent overcast conditions.
Solar GHI daytime averages are typically below 200 W/m² in winter and peak around
500–600 W/m² in summer (December–February). Solar energy is a secondary resource here.

---

## Manila, Philippines — Mixed solar/wind site

**Climate:** Tropical monsoon (Köppen Am). Two distinct seasons: dry (November–May)
and wet/monsoon (June–October). In the wet season, cloud cover and rain significantly
reduce solar output. Manila is located in the typhoon belt; typhoon-related gusts
can trigger wind anomalies.

**Solar generation potential:** Manila has good clear-sky potential (GHI peaks above
900 W/m² on clear days), but the monsoon season limits daytime averages to
350–450 W/m². In the dry season, averages approach 500–550 W/m².

**Wind generation potential:** Wind speeds average 8–12 km/h year-round with
occasional strong gusts tied to tropical convection or typhoon proximity. These
isolated spikes can flag as anomalies even when surrounding readings are normal.

---

## Interpreting anomaly counts

- **Wellington wind anomalies** are most common and usually represent real storm
  events (sustained high winds), not sensor errors.
- **Manila wind anomalies** tend to be isolated spikes from convective events.
- **Riyadh wind anomalies** are rare and typically associated with shamal wind events.
- **Solar anomalies** at any site usually reflect sudden cloud cover, dust storms
  (Riyadh), or sensor issues — check surrounding hours for context.

---

## How Helios detects anomalies

Helios uses the **IQR (interquartile range) method** as the active anomaly detection strategy.

- A reading is flagged if it falls below **Q1 − 1.5 × IQR** or above **Q3 + 1.5 × IQR**,
  computed from the site's rolling history.
- The result is stored in `wind_iqr_flag` and `solar_iqr_flag` (0 = normal, 1 = anomaly).
- All anomaly counts in chatbot answers are based on the IQR flag columns.

The `quality_flag` column in `cleaned_observations` summarises data quality:
`"ok"`, `"filled"` (forward-filled gap), or `"clamped"` (physical-bounds correction).
