# EarthWatch - ACM x TESC Hackathon

Worldwide climate intelligence: choose any country or territory, search for a
place, or enter coordinates anywhere on Earth. Explore local temperature and
precipitation anomalies with traceable sources and a historical baseline.

## Global seasonal risk watchlist

The default **Global risk watchlist** monitors potential floods, droughts, heat
waves, wildfire conditions, and heavy rainfall over the next **1–3 full calendar
months**. Eight representative points across the Americas, Europe, Africa, Asia,
and Australia are provided as watch candidates, not pre-existing hazard predictions.
Add named coordinates anywhere on Earth, or export/import your watched areas.
Watchlists and scan results remain in the current Streamlit session.

Choose areas and a window, then click **Scan selected areas with Grok**. Each area
uses retrieved **ECMWF SEAS5 monthly ensemble-mean anomalies via Open-Meteo** for
temperature, precipitation, surface soil moisture, and runoff. The Seasonal Scout,
Impact Analyst, and Seasonal Skeptic bots draft and review an outlook using the
same evidence. Each of the three stages calls the configured Grok model. Existing
`XAI_API_KEY`, `XAI_MODEL`, and xAI credits are required. No paid calls run on page load.

The watchlist supports hazard/level filters, a world map, per-area explanations,
monitoring triggers, confidence, limitations, source values, agent activity, and
JSON report downloads. Reviews persist across reruns. Failed refreshes preserve
old reports as explicitly noncurrent; unavailable source data or invalid agent
output never becomes a sample prediction. Results need refreshing after six hours
or a change to the selected outlook window. A scan fetch can reuse source data
cached for up to six hours; the source retrieval timestamp is displayed.
The world overview uses bundled public-domain Natural Earth boundaries, so it
does not depend on external basemap tiles. Select a marker to open its area outlook.

These forecasts describe seasonal area conditions relative to the **model
climatology**. They are not bias-corrected and do not establish exact event dates,
calibrated disaster probabilities, drought onset, flood extent, or wildfire ignition.
Code checks evidence references and necessary directional indicators, not forecast
skill: this is not a validated or calibrated hazard-prediction model. Climate change
is relevant background context; individual event attribution is not performed.
Use official warnings and shorter-range local forecasts for operational decisions.

Sources: [Open-Meteo Seasonal Forecast API](https://open-meteo.com/en/docs/seasonal-forecast-api),
[ECMWF seasonal forecast guidance](https://confluence.ecmwf.int/pages/viewpage.action?pageId=181111118),
and [IPCC AR6 climate extremes assessment](https://www.ipcc.ch/report/ar6/wg1/chapter/chapter-11/).

## Setup

```powershell
uv venv --python 3.12 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.venv\Scripts\streamlit.exe run app.py
.venv\Scripts\python.exe -m pytest -q
```

Alternatively, create a Python virtual environment with `python -m venv .venv`
and install `requirements.txt` with pip. Future Grok integration uses the settings
in `.env.example`; the climate data and statistical assessments need no API key.

## Worldwide monitoring

The **Worldwide locations** view supports:

- **Live weather**: today's current temperature, feels-like temperature, humidity,
  wind, precipitation, and local hourly weather for the selected point. Click
  **Load today's weather**; refresh manually or leave the page open for five-minute
  updates. Current values are model estimates and future hourly values are forecasts.
- Independent **NOAA NWS station observations** for US locations when a reporting
  station within 50 km has fresh data. San Diego is checked against KSAN airport.
  The app displays both timestamps and any temperature difference; it does not
  average the sources or promise that a model estimate is an exact observation.
- A searchable list of 250 countries and territories and a worldwide place/postal-code search.
- Disambiguated results with administrative area, country and coordinates.
- Direct latitude/longitude entry for any point, including remote and unnamed places.
- Location-specific monthly air temperature and precipitation from ERA5 reanalysis.
- Observation years from 1960 through the current year; a preceding 30-year
  calendar-month baseline (at least 20 valid years) avoids using future data.
  Current-year data include published observations, allowing a seven-day source buffer;
  incomplete months remain unknown.
- Maps, observation/baseline charts, anomaly tables, and daily/monthly CSV downloads.
- **Investigate today's weather with Grok** runs the Sentinel, Investigator,
  Impact, Skeptic/Reviser, and Action bots against the displayed live snapshot.
  Live investigations cannot substitute historical weather or another location.
  Grok requires `XAI_API_KEY`, `XAI_MODEL`, and available xAI credits in local `.env`.
- Live bot research tools also retrieve **NOAA/NWS official alerts**, **MET Norway
  global forecasts**, and **NASA GIBS Terra/Aqua satellite imagery**. Scene dates,
  issue times and source links stay attached. Satellite imagery is shown with
  the assessment; it is not automatically interpreted as weather measurements.


Choose a country, search for a place, select a match, and click **Load today's
weather**. For baseline comparisons, switch to **Climate history**, select a year,
and click **Load climate data**. Use **Coordinates** for a point absent from the search index. Results
represent the selected grid cell, not an average over the entire country.
Coverage and missing observations depend on the data source. ERA5 precipitation
includes rain and snow; this product does not claim to predict every climate hazard.

**Pacific ocean indices** remains available as a specialist view. The existing
2017 Peru historical replay is one example dataset, not a geographic restriction.

## Data interfaces and sources

See [data/README.md](data/README.md) for ingestion/replay and
[data/GLOBAL.md](data/GLOBAL.md) for worldwide selection, weather, and analysis APIs.
Source: [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api)
using Copernicus ERA5 for climate history;
[Open-Meteo weather API](https://open-meteo.com/en/docs) for today's conditions.
Independent US observations: [NOAA NWS API](https://www.weather.gov/documentation/services-web-api).
Additional official forecast: [MET Norway](https://api.met.no/weatherapi/locationforecast/2.0/documentation).
Satellite imagery: [NASA GIBS](https://nasa-gibs.github.io/gibs-api-docs/access-basics/).
The live source uses a five-minute cache, rejects expired responses on failures,
and shows the conditions timestamp and retrieval time in the selected timezone.
Place search: [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api).
Country/territory names: [GeoNames](https://download.geonames.org/export/dump/countryInfo.txt).
Weather and GeoNames attribution: CC BY 4.0. Country names/codes follow that source.

## Team integration

Person 1 owns `data/` and `analysis/`; Person 2 owns `agents/`; Person 3 owns
`app.py`, `translator.py`, and `dashboard/`. The worldwide expansion connects all
three interfaces and keeps the original Pacific entry points compatible. The
shared AnomalyRecord and Assessment schemas are unchanged. Agent implementations
must use the selected record's region, coordinates, date and source, rather than
assuming Peru or interpreting Pacific indices as local SST everywhere.

Full original plan: [plan.md](plan.md), with its worldwide scope update first.

## Current weather anomalies (default view)

Scan watched locations, then click a globe marker to open current temperature,
wind, or completed-hour rain against the 1991–2020 ERA5 distribution. Add cities
through search or enter coordinates. Comparisons match the local hour and a
15-day seasonal window, require 20 years/200 valid samples, and expose source
links and missing-history states. Fahrenheit and Celsius are supported.
The San Diego 100°F/67°F example is illustrative, never a seeded live reading.

**Explain causes & safety actions** asks the configured Grok model to interpret
that exact snapshot, state testable possible causes, and recommend sourced
precautions. It requires xAI credentials and credits. Scanning weather does not
call Grok. Snapshots expire from the current globe after ten minutes from
retrieval or 90 minutes from the conditions timestamp; refresh manually.
The watchlist is selected-point coverage, not a continuous global alert service.


### NOAA global hazard globe

The default **Global hazard events** view loads NOAA CPC's published week-2/3
KML polygons for cyclone formation, above/below-median rainfall, and above/below-normal
temperatures. Click a footprint or choose an event to inspect its probability,
valid dates, source links, and Grok explanation. Colors identify forecast type.

Grok Hazard Scout and Grok Evidence Reviewer use `XAI_API_KEY` and `XAI_MODEL`
from `.env`. Reviews run in background batches and persist in `.cache/earthwatch/`.
The open globe checks for source updates every 30 minutes. New source evidence
invalidates previous reviews; unchanged editions reuse them. **Update events with
Grok** checks immediately and retries failed reviews. Updates run while the app is
open, not as a system-wide scheduled service. NOAA coverage is primarily tropical;
these forecasts are not current observations, confirmed disasters, or local warnings.

The globe also includes a labeled **San Diego heat wave · early October 2026**
marker. Click it or **San Diego heat wave · open report** to read observations,
reported impacts, local weather drivers, and the evidence for El Niño's broader
influence. This dated retrospective remains available if NOAA or Grok is offline.
The downloadable report is also in `reports/san_diego_heat_october_2026.md`.
**Review San Diego report with Grok** runs a reporter and attribution reviewer on
the cited evidence. An invalid xAI key is reported explicitly; the app retains
the sourced report without substituting generated damage or attribution claims.
