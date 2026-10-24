# Person 1: climate data interface

Owner: Person 1. All code uses the existing requirements.txt. No API key required.

## Teammate calls

```python
from data.climate_sources import get_sst_series
from analysis.anomaly_detection import detect_anomalies, calculate_anomaly
from data.rainfall_sources import get_rainfall_history
from analysis.rainfall_analysis import rainfall_metrics, detect_rainfall
from data.replay import replay, replay_rainfall

sst = get_sst_series('Nino 1+2')  # also supports 'Nino 3.4'
records = detect_anomalies()     # latest record for each ocean region
rain = get_rainfall_history('Piura', '1982-01-01', '2017-12-31')
daily, monthly = rainfall_metrics(rain)
rain_signal = detect_rainfall(rain)
for step in replay('Nino 1+2', '2017-01-01', '2017-12-31'):
    chart_frame, record = step['series'], step['anomaly']
```

Observation frames always contain `date`, numeric `value`, `region`, `unit`,
`source`, `retrieved_at` (UTC) and `cache_stale`. Missing values remain NaN;
no interpolation or invented values. SST also includes absolute `sst` and
`baseline_period`. Rain includes requested coordinates and measurement type.
`date` is an observation month (first of month) for SST, or local calendar day
(America/Lima) for rainfall. CSV snapshots retain these same fields.

SST `value` is NOAA's published monthly OI anomaly in degrees Celsius, relative
to 1991-2020, not absolute temperature. It is never recentered or treated as ONI.
Default investigation threshold is absolute departure >=1 degC, with three
consecutive same-sign threshold exceedances marked persistent. Both parameters
are configurable through `detect_series`. This is an internal heuristic, not an
official ENSO declaration. Latest missing SST raises an error because the shared
AnomalyRecord schema cannot represent a missing numeric value. Records include
monitoring status even when no investigation threshold is crossed.

For raw monthly measurements, `calculate_anomaly(series, baseline)` computes
X minus the matching calendar-month mean and sample-standard-deviation z score.
It requires at least 20 nonmissing years for each calendar month. Zero variance
produces an undefined (NaN) z score. Do not pass published NOAA anomalies to it.

Rainfall is ERA5 reanalysis precipitation (rain + snow), not direct rain-gauge
measurements. Locations: Piura (-5.1945, -80.6328) and Tumbes (-3.5669, -80.4515).
`rainfall_metrics` returns daily seven-day sums in mm and empirical percentiles,
plus monthly totals, baseline mean, SD, anomaly and z score. A missing day makes
affected seven-day sums and monthly totals unknown. Percentiles compare windows
ending in the same calendar month against 1982-2011, require 20 represented
years, and use the fraction of reference values <= the observed value (ties
included). This seasonal heuristic has overlapping windows, not independent
samples. `detect_rainfall` flags percentile >=95 by default, using that fixed
baseline. A precipitation signal alone does not establish flood occurrence.

## Replay and chart data

The committed `data/historical/` dataset is real downloaded data, separate from
the team's fake `sample_data/`. Scenario: 2017 coastal Pacific warming. SST
covers 2016-2017; rainfall covers 1982-2017 so the baseline precedes the event.
`replay()` yields the same AnomalyRecord model as live detection and chart-ready
frames truncated at each replay observation, with no future SST observations.
`replay_rainfall()` returns the daily and monthly chart frames without network.
Monthly baseline calculations use only 1982-2011. These helpers let Person 3
wire historical controls without changing the existing live entry signatures.

```powershell
.venv\Scripts\python.exe -m data.replay            # offline replay
.venv\Scripts\python.exe -m data.replay --refresh  # replace snapshots from sources
.venv\Scripts\python.exe -m pytest -q
```

Downloads have finite timeouts and retries. Cached responses live under
`.cache/earthwatch` (override EARTHWATCH_CACHE_DIR), fresh for one day. A network
failure may use an existing cached response with `cache_stale=True`; it never
substitutes historical demo data into the live pipeline. Uncached network errors,
malformed responses, unknown locations, invalid units/dates, and absent baseline
data fail explicitly. Live observation dates must be shown: latest published
monthly data may lag today's date, even when fetched recently.

## Sources

- NOAA data: https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices
- Baseline and region definitions: https://www.cpc.ncep.noaa.gov/data/indices/Readme.index.shtml
- Open-Meteo ERA5 API and attribution (CC BY 4.0): https://open-meteo.com/en/docs/historical-weather-api
- Rain attribution: Weather data by Open-Meteo, using Copernicus ERA5 reanalysis.

Snapshots are retrospective downloads and can reflect source revisions. Retrieval
timestamps describe the downloaded version, not what was available in 2017.
Source URLs, model, coordinates, units, dates, and retrieval times accompany the
observations. The manifest lists the data files; no synthetic observations or
LLM estimates are used.
