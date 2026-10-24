# Worldwide data API

The worldwide scope supersedes the original Peru-only focus. The original
`get_sst_series(region)` intentionally remains restricted to NOAA's actual index
regions; those indices cannot describe arbitrary countries. Worldwide monitoring
instead uses air temperature and precipitation at selected coordinates.

```python
from data.locations import Location, countries, search_locations
from data.weather_sources import get_weather_history
from data.rainfall_sources import get_rainfall_history
from analysis.global_climate import analyze_location

matches = search_locations('Nairobi', country_code='KE')
place = matches[0]  # UI presents all matches for explicit selection
# Or choose an arbitrary point; no geocoding required:
place = Location('Remote site', latitude=-1.3, longitude=36.8)
weather = get_weather_history(place, '2025-01-01', '2025-12-31')
rain = get_rainfall_history(place, '2025-01-01', '2025-12-31')
climate = analyze_location(place, 2025)
# climate.location, .daily, .monthly, .anomalies, .baseline_period
```

`countries()` uses a bundled GeoNames list (250 current countries and territories,
including XK). `search_locations` accepts any place/postal-code query, optionally
filtered by country code. Search is limited to 100 matches per query; narrower
queries and the coordinate option cover ambiguous or unindexed places. Coordinates
accept the full finite latitude [-90,90] / longitude [-180,180] range. Unicode
names are retained. Keys are derived from coordinates, so duplicate place names
in different regions never share records.

Global data use ERA5 on the nearest grid cell with the location timezone (or
automatic coordinate lookup), rather than the original hardcoded Peru timezone.
Weather frames contain `date`, `temperature` (degC), `precipitation` (mm/day),
`region`, `country_code`, requested and returned grid coordinates, `timezone`,
`source`, `retrieved_at`, `cache_stale`, and `measurement_kind`. Missing values
remain unknown. Invalid units, date gaps, duplicates, and negative precipitation
fail validation. The legacy rainfall function still accepts Piura/Tumbes strings
for existing replay callers; worldwide callers pass an explicitly selected Location.

`analyze_location` accepts an observation year from 1960 through the current year and
computes complete-month mean air temperature and precipitation totals. Current-year
retrieval ends seven days before today to account for publication delays; incomplete
months remain unknown. In early January, choose the prior year until current-year
data are available. Baseline:
the preceding 30 years, truncated at 1940 for early years. Anomalies and sample-SD
z scores compare the same calendar month at that point. At least 20 valid years
are required. |z| >=2 is an internal investigation heuristic, not an official
warning. Zero variance yields inconclusive detection. Missing monthly measurements
remain NaN in the table and have no fabricated AnomalyRecord. Monthly exports
retain the baseline and location/source provenance. The daily export contains
only the requested observation year; baseline statistics are in the monthly export.

`translator.search_world_locations`, `load_location_climate`, and
`investigate_location` connect this to the dashboard. Investigation looks up the
record only inside the selected location/year result. The existing agent workflow
receives that record. While it is a stub, global results use real deterministic
statistics and clearly state that limitation; they never reuse the Peru sample
assessment. Changing location/year hides previous results and assessments.

Country selection narrows place search; it does not imply national aggregation.
Geocoding is an index and cannot list every unnamed point, so coordinate selection
is always available. Reanalysis is gridded/model-derived, not a station reading.
A location's precipitation anomaly does not establish flooding, and Pacific ENSO
signals alone do not establish local effects worldwide.

Source documentation:
- https://open-meteo.com/en/docs/historical-weather-api
- https://open-meteo.com/en/docs/geocoding-api
- https://download.geonames.org/export/dump/countryInfo.txt

GeoNames country names/codes were downloaded on 2026-10-24. Historic dissolved AN
and CS entries are excluded. Attribution: GeoNames CC BY 4.0. Weather attribution:
Open-Meteo / Copernicus ERA5, CC BY 4.0. No additional dependencies were introduced.
