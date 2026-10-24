"""NOAA tide-gauge water levels and nearby weather for coastal anomaly detection.

Owner: Person 3 (added for coastal events; Person 1 may take ownership). Observed water
levels and NOAA's own harmonic tide predictions come from the NOAA CO-OPS API; the
difference between them is the non-tidal residual (water the astronomical tide does
not explain). Wind and pressure come from Open-Meteo. Nothing here is estimated or
filled in: a missing value stays missing and a failed request raises.
"""

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

import pandas as pd

from data.cache import fetch_text

DATA_URL = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
META_URL = "https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station}/{kind}.json"
STATION_PAGE = "https://tidesandcurrents.noaa.gov/waterlevels.html?id={station}"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_PAGE = "https://open-meteo.com/en/docs"
FEET_TO_METERS = 0.3048
LEVEL_MAX_AGE_SECONDS = 900
METADATA_MAX_AGE_SECONDS = 7 * 86400
MAX_WINDOW_DAYS = 31

# NOAA CO-OPS tide gauges monitored for coastal water-level anomalies.
STATIONS: dict[str, str] = {
    "9410170": "San Diego, CA",
    "9414290": "San Francisco, CA",
    "9447130": "Seattle, WA",
    "1612340": "Honolulu, HI",
    "8723214": "Virginia Key (Miami), FL",
    "8518750": "The Battery (New York), NY",
    "8443970": "Boston, MA",
    "8771450": "Galveston Pier 21, TX",
    "8665530": "Charleston, SC",
}


# One station's observed and predicted water levels over a window, with provenance.
@dataclass(frozen=True)
class StationLevels:
    station: str
    name: str
    latitude: float
    longitude: float
    levels: pd.DataFrame  # columns: time (UTC), observed_m, predicted_m, residual_m
    minor_flood_m: float | None  # NOAA minor high-tide-flooding threshold, m above MHHW
    source: str
    retrieved_at: str
    stale: bool


# Returns the human-readable NOAA page for a station's water levels.
def station_page(station: str) -> str:
    return STATION_PAGE.format(station=station)


# Fetches JSON through the shared cache and raises a readable error on API errors.
def _get_json(url: str, params: dict | None, max_age: int) -> tuple[dict, str, bool]:
    text, retrieved_at, stale = fetch_text(url, params, max_age=max_age)
    payload = json.loads(text)
    if isinstance(payload, dict) and "error" in payload:
        message = payload["error"].get("message") if isinstance(payload["error"], dict) else payload["error"]
        raise ValueError(f"NOAA returned an error: {message}")
    return payload, retrieved_at, stale


# Returns NOAA's minor high-tide-flooding threshold in metres above MHHW, or None.
def minor_flood_threshold(station: str) -> float | None:
    floods, _, _ = _get_json(META_URL.format(station=station, kind="floodlevels"), None, METADATA_MAX_AGE_SECONDS)
    datums, _, _ = _get_json(
        META_URL.format(station=station, kind="datums"), {"units": "metric"}, METADATA_MAX_AGE_SECONDS
    )
    minor_feet = floods.get("nos_minor") or floods.get("nws_minor")
    mhhw = next((item.get("value") for item in datums.get("datums", []) if item.get("name") == "MHHW"), None)
    if minor_feet is None or mhhw is None:
        return None
    return round(float(minor_feet) * FEET_TO_METERS - float(mhhw), 3)


# Builds the CO-OPS request parameters for one product over a UTC window.
def _window_params(station: str, product: str, start: datetime, end: datetime) -> dict:
    return {
        "station": station, "product": product, "datum": "MHHW", "units": "metric",
        "time_zone": "gmt", "format": "json", "application": "EarthWatch",
        "begin_date": start.strftime("%Y%m%d %H:%M"), "end_date": end.strftime("%Y%m%d %H:%M"),
    }


# Converts CO-OPS rows into a time-indexed numeric series, dropping blank values.
def _series(rows: list[dict], column: str) -> pd.Series:
    frame = pd.DataFrame(rows or [], columns=["t", "v"])
    frame["v"] = pd.to_numeric(frame["v"], errors="coerce")
    frame = frame.dropna(subset=["v"])
    times = pd.to_datetime(frame["t"], utc=True)
    return pd.Series(frame["v"].to_numpy(), index=times, name=column)


# Fetches observed and predicted water levels (metres above MHHW) for a UTC window.
def get_station_levels(station: str, start: datetime, end: datetime) -> StationLevels:
    if station not in STATIONS:
        raise ValueError(f"Unsupported NOAA station: {station!r}.")
    if end <= start or (end - start) > timedelta(days=MAX_WINDOW_DAYS):
        raise ValueError(f"Window must be positive and at most {MAX_WINDOW_DAYS} days.")
    observed, retrieved_at, stale = _get_json(
        DATA_URL, _window_params(station, "water_level", start, end), LEVEL_MAX_AGE_SECONDS
    )
    predicted, _, predicted_stale = _get_json(
        DATA_URL, _window_params(station, "predictions", start, end), LEVEL_MAX_AGE_SECONDS
    )
    observed_series = _series(observed.get("data"), "observed_m")
    if observed_series.empty:
        raise ValueError(f"NOAA has no observed water levels for station {station} in this window.")
    levels = pd.concat([observed_series, _series(predicted.get("predictions"), "predicted_m")], axis=1)
    levels = levels.dropna(subset=["observed_m"]).sort_index()
    levels["residual_m"] = (levels["observed_m"] - levels["predicted_m"]).round(3)
    levels = levels.rename_axis("time").reset_index()
    metadata = observed.get("metadata", {})
    return StationLevels(
        station=station, name=STATIONS[station],
        latitude=round(float(metadata["lat"]), 4), longitude=round(float(metadata["lon"]), 4),
        levels=levels, minor_flood_m=minor_flood_threshold(station),
        source=station_page(station), retrieved_at=retrieved_at, stale=stale or predicted_stale,
    )


# Fetches the last `hours` of water levels ending now.
def get_recent_levels(station: str, hours: int = 72, now: datetime | None = None) -> StationLevels:
    end = (now or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    return get_station_levels(station, end - timedelta(hours=hours), end)


# Fetches hourly wind and sea-level pressure near a station for a date range (Open-Meteo model).
def get_coastal_weather(latitude: float, longitude: float, start: date, end: date) -> tuple[pd.DataFrame, str, bool]:
    params = {
        "latitude": latitude, "longitude": longitude, "timezone": "GMT",
        "start_date": start.isoformat(), "end_date": end.isoformat(),
        "hourly": "wind_speed_10m,wind_direction_10m,pressure_msl",
        "wind_speed_unit": "kmh",
    }
    payload, retrieved_at, stale = _get_json(WEATHER_URL, params, LEVEL_MAX_AGE_SECONDS)
    hourly = payload.get("hourly") or {}
    frame = pd.DataFrame({
        "time": pd.to_datetime(hourly.get("time", []), utc=True),
        "wind_speed_kmh": pd.to_numeric(pd.Series(hourly.get("wind_speed_10m", []), dtype="float64")),
        "wind_direction_deg": pd.to_numeric(pd.Series(hourly.get("wind_direction_10m", []), dtype="float64")),
        "pressure_msl_hpa": pd.to_numeric(pd.Series(hourly.get("pressure_msl", []), dtype="float64")),
    })
    return frame, retrieved_at, stale
