"""Today's model-based weather, separate from delayed ERA5 climate history."""
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from zoneinfo import ZoneInfo

import pandas as pd

from data.cache import fetch_text
from data.locations import Location

SOURCE = 'https://api.open-meteo.com/v1/forecast'
FIELDS = {
    'temperature_2m': '\u00b0C',
    'apparent_temperature': '\u00b0C',
    'relative_humidity_2m': '%',
    'precipitation': 'mm',
    'wind_speed_10m': 'km/h',
}


@dataclass
class LiveWeather:
    location: Location
    current: dict
    hourly: pd.DataFrame
    current_time: datetime
    retrieved_at: datetime
    timezone: str
    interval_seconds: int
    source: str = SOURCE


def _now():
    return datetime.now(timezone.utc)


def _number(value, field):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f'Invalid live weather value for {field}')
    if field in {'precipitation', 'wind_speed_10m'} and value < 0:
        raise ValueError(f'Negative {field}')
    if field == 'relative_humidity_2m' and not 0 <= value <= 100:
        raise ValueError('Invalid relative humidity')
    return float(value)


def get_live_weather(location, *, refresh=False):
    """Return current conditions and today's hourly estimates/forecast, local time.

    Five-minute HTTP cache; expired cache is never used on network failures.
    Current values are weather-model estimates, not station observations.
    """
    if not isinstance(location, Location):
        raise ValueError('Select a location first')
    params = dict(
        latitude=location.latitude, longitude=location.longitude,
        current=','.join(FIELDS), hourly=','.join(FIELDS),
        temperature_unit='celsius', wind_speed_unit='kmh', precipitation_unit='mm',
        timezone=location.timezone, timeformat='unixtime', forecast_days=1,
        cell_selection='nearest',
    )
    text, stamp, stale = fetch_text(
        SOURCE, params, max_age=0 if refresh else 300, allow_stale=False,
    )
    if stale:
        raise ValueError('Stale weather cannot be shown as live')
    payload = json.loads(text)
    if payload.get('error'):
        raise ValueError(payload.get('reason', 'Live weather source failed'))
    local_zone = ZoneInfo(payload['timezone'])
    now = _now().astimezone(local_zone)
    retrieved = datetime.fromisoformat(stamp)
    if retrieved.tzinfo is None or not -60 <= (now - retrieved).total_seconds() <= 600:
        raise ValueError('Live weather retrieval is not recent')
    current = payload['current']
    current_time = datetime.fromtimestamp(current['time'], timezone.utc).astimezone(local_zone)
    age = (now - current_time).total_seconds()
    if current_time.date() != now.date() or not -900 <= age <= 5400:
        raise ValueError('The source did not return recent conditions for today')
    interval = current['interval']
    if isinstance(interval, bool) or not isinstance(interval, int) or not 0 < interval <= 3600:
        raise ValueError('Unexpected current precipitation interval')
    for section in ['current_units', 'hourly_units']:
        if any(payload.get(section, {}).get(key) != unit for key, unit in FIELDS.items()):
            raise ValueError('Unexpected live weather units')
    values = {key: _number(current[key], key) for key in FIELDS}
    if all(value is None for value in values.values()):
        raise ValueError('No current weather values are available')
    hourly = payload['hourly']
    dates = pd.to_datetime(hourly['time'], unit='s', utc=True).tz_convert(local_zone)
    if dates.hasnans or dates.has_duplicates:
        raise ValueError('Invalid hourly weather timestamps')
    frame = pd.DataFrame({'date': dates})
    for field in FIELDS:
        frame[field] = [_number(value, field) for value in hourly[field]]
    frame = frame.loc[frame['date'].dt.date == now.date()].sort_values('date').reset_index(drop=True)
    if frame.empty:
        raise ValueError('No hourly data for today')
    frame['data_kind'] = frame['date'].map(lambda day: 'Forecast' if day > now else 'Model estimate')
    frame['region'], frame['source'] = location.label, SOURCE
    frame['latitude'], frame['longitude'] = location.latitude, location.longitude
    frame['grid_latitude'], frame['grid_longitude'] = payload.get('latitude'), payload.get('longitude')
    frame['timezone'], frame['retrieved_at'] = payload['timezone'], stamp
    frame['temperature_unit'], frame['precipitation_unit'] = 'degC', 'mm/hour'
    frame['wind_speed_unit'], frame['relative_humidity_unit'] = 'km/h', '%'
    return LiveWeather(location, values, frame, current_time, retrieved, payload['timezone'], interval)
