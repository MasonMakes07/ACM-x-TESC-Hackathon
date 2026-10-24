# Worldwide data API

## Today's live weather

```python
from data.live_weather import get_live_weather
from data.locations import Location

weather = get_live_weather(Location('San Diego', 32.7336, -117.1831), refresh=True)
# .current, .current_time, .retrieved_at, .timezone, .hourly, .interval_seconds
```

Live data come from `https://api.open-meteo.com/v1/forecast`, using current and
hourly fields for the selected coordinates. Current temperature/apparent temperature
are in degC, relative humidity in %, wind in km/h, and precipitation in mm over
the response's current interval (usually 15 minutes). Hourly precipitation covers
the preceding hour. Current conditions are model estimates; future hourly values
are forecasts. This API is not the delayed historical ERA5 archive and does not
provide station-observed ground truth.

Requests use Unix timestamps converted to the returned IANA timezone, including
daylight-saving transitions. Only the selected location's local today is returned.
Current timestamps must be from today, no more than 90 minutes old or 15 minutes
ahead. Retrieval timestamps must be within ten minutes. Missing values remain
unavailable; malformed units/ranges, duplicate times, and empty current data fail.
There is a five-minute cache; `refresh=True` bypasses it. Network failures never
use an expired response for live weather. The dashboard refreshes every five
minutes while active, supports manual refresh, and exports current/hourly CSVs.
Changing location hides old conditions. An error clears displayed conditions.

The translator entry point is `load_live_weather(location, refresh=False)`.
The **Live weather** view is the default; **Climate history** retains the
existing monthly baseline calculations. Today's estimates and partial-day forecasts
are not inserted into complete-month ERA5 anomaly calculations.

Source definitions: https://open-meteo.com/en/docs

### Independent station checks and live bots

`translator.load_station_weather(location, refresh=False)` uses the NOAA NWS
points/stations APIs to find a station within 50 km with a temperature reading
no older than 90 minutes. Temperatures are validated in Celsius; wind and rain
units are converted explicitly. Missing precipitation remains unknown, not zero.
`compare_station(weather, station)` only compares temperatures from the same local
day and no more than 60 minutes apart. Source timestamps and station distance
remain visible; a difference over 3 degC gets a dashboard warning, not a claim
that either source is necessarily wrong. NWS coverage is US-specific; other
locations keep live model estimates and explicitly state station unavailability.

`translator.investigate_live_weather(weather, station, on_progress)` builds a
current-weather record, not a monthly anomaly, and runs the real Grok workflow.
`agents.live_tools.LiveWeatherToolbox` binds `get_current_weather` to the selected
coordinates and the same fresh snapshot as the dashboard. The Sentinel checks
the value; Investigator and Impact get the live-only tool; Skeptic/Reviser check
the draft. Wrong coordinates, expired data, and historical tool substitutions
are rejected. The ledger records model estimates as references and NWS readings
as measurements. Current conditions on the first day of a month are not expanded
to the end of that month. The result's confidence describes the interpretation,
not a station thermometer's accuracy. API failures show errors instead of sample
reports. API keys remain local and are never included in tool results.

NWS source definitions: https://www.weather.gov/documentation/services-web-api

## Historical climate

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
receives that record. The Grok workflow uses real controlled tools and validates
structured evidence; it requires configured xAI credentials and credits. Changing
location/year hides previous results and assessments.

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
