# EarthWatch - ACM x TESC Hackathon

Worldwide climate intelligence: choose any country or territory, search for a
place, or enter coordinates anywhere on Earth. Explore local temperature and
precipitation anomalies with traceable sources and a historical baseline.

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

The default **Worldwide locations** view supports:

- A searchable list of 250 countries and territories and a worldwide place/postal-code search.
- Disambiguated results with administrative area, country and coordinates.
- Direct latitude/longitude entry for any point, including remote and unnamed places.
- Location-specific monthly air temperature and precipitation from ERA5 reanalysis.
- Observation years from 1960 through the current year; a preceding 30-year
  calendar-month baseline (at least 20 valid years) avoids using future data.
  Current-year data include published observations, allowing a seven-day source buffer;
  incomplete months remain unknown.
- Maps, observation/baseline charts, anomaly tables, and daily/monthly CSV downloads.
- Investigation of the selected location's actual measurements. Until Person 2's
  workflow is implemented, this returns a labelled deterministic statistical
  assessment, with no sample regional claims.

Choose a country, search for a place, select a match, and click **Load climate
data**. Use **Coordinates** for a point absent from the search index. Results
represent the selected grid cell, not an average over the entire country.
Coverage and missing observations depend on the data source. ERA5 precipitation
includes rain and snow; this product does not claim to predict every climate hazard.

**Pacific ocean indices** remains available as a specialist view. The existing
2017 Peru historical replay is one example dataset, not a geographic restriction.

## Data interfaces and sources

See [data/README.md](data/README.md) for ingestion/replay and
[data/GLOBAL.md](data/GLOBAL.md) for worldwide selection, weather, and analysis APIs.
Source: [Open-Meteo historical weather](https://open-meteo.com/en/docs/historical-weather-api)
using Copernicus ERA5. Place search: [Open-Meteo geocoding](https://open-meteo.com/en/docs/geocoding-api).
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
