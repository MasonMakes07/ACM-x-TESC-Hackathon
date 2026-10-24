"""Compare current temperature/wind and completed-hour rain with ERA5 history."""
from datetime import date, datetime, timedelta, timezone
import json
import math
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests

from data.cache import fetch_text
from data.live_weather import get_live_weather
from schemas.weather_comparison import WeatherComparison, WeatherMetric

ARCHIVE = 'https://archive-api.open-meteo.com/v1/archive'
FIELDS = {'temperature_2m': ('temperature', '°C'), 'precipitation': ('precipitation', 'mm'),
          'wind_speed_10m': ('wind', 'km/h')}
START, END = '1991-01-01', '2020-12-31'


def _season_days(timestamp):
    anchor = date(2000, timestamp.month, timestamp.day)
    return {((anchor + timedelta(days=offset)).month, (anchor + timedelta(days=offset)).day)
            for offset in range(-7, 8)}


def historical_hours(location, zone_name, *, loader=fetch_text):
    params = dict(latitude=location.latitude, longitude=location.longitude,
                  start_date=START, end_date=END, hourly=','.join(FIELDS), models='era5',
                  timezone=zone_name, timeformat='unixtime', temperature_unit='celsius',
                  wind_speed_unit='kmh', precipitation_unit='mm', cell_selection='nearest')
    raw, stamp, stale = loader(ARCHIVE, params, max_age=31536000, allow_stale=False)
    if stale:
        raise ValueError('Historical source returned an expired cache.')
    payload = json.loads(raw)
    if payload.get('error'):
        raise ValueError('Historical weather source unavailable.')
    for coord, requested in [('latitude', location.latitude), ('longitude', location.longitude)]:
        actual = payload.get(coord)
        difference = abs(actual - requested) if isinstance(actual, (int, float)) else math.inf
        if coord == 'longitude' and math.isfinite(difference):
            difference = min(difference % 360, 360 - difference % 360)
        if not math.isfinite(difference) or difference > 1:
            raise ValueError('Historical source returned a different area.')
    for field, (_, unit) in FIELDS.items():
        if payload.get('hourly_units', {}).get(field) != unit:
            raise ValueError('Historical weather units do not match.')
    hourly = payload['hourly']
    dates = pd.to_datetime(hourly['time'], unit='s', utc=True).tz_convert(ZoneInfo(zone_name))
    if dates.hasnans or dates.has_duplicates or not dates.is_monotonic_increasing:
        raise ValueError('Invalid historical timestamps.')
    frame = pd.DataFrame({'time': dates})
    for field, (name, _) in FIELDS.items():
        values = hourly[field]
        if len(values) != len(dates) or any(isinstance(value, bool) for value in values):
            raise ValueError('Invalid historical values.')
        numbers = pd.to_numeric(pd.Series(values), errors='raise')
        if np.isinf(numbers).any() or (name != 'temperature' and numbers.dropna().lt(0).any()):
            raise ValueError('Invalid historical value range.')
        frame[name] = numbers
    frame = frame.loc[frame.time.dt.year.between(1991, 2020)].copy()
    frame['day'] = frame.time.dt.date
    frame['hour'] = frame.time.dt.hour
    # A repeated DST hour must not give that date twice the statistical weight.
    frame = frame.drop_duplicates(['day', 'hour'])
    source = requests.Request('GET', ARCHIVE, params=params).prepare().url
    return frame, source, datetime.fromisoformat(stamp)


def compare_metric(variable, current, timestamp, history):
    unit = {'temperature': '°C', 'precipitation': 'mm/hour', 'wind': 'km/h'}[variable]
    samples, years = [], 0
    if history is not None:
        days = _season_days(timestamp)
        same = history.loc[(history.hour == timestamp.hour)
                           & history.day.map(lambda value: (value.month, value.day) in days)]
        valid = same.loc[same[variable].notna()]
        samples = valid[variable].astype(float).tolist()
        years = valid.time.dt.year.nunique()
    adequate = years >= 20 and len(samples) >= 200
    mean = float(np.mean(samples)) if adequate else None
    lo, hi = (float(np.quantile(samples, q)) for q in (0.05, 0.95)) if adequate else (None, None)
    difference = current - mean if current is not None and mean is not None else None
    status, unusual = 'Within historical screening range', False
    if current is None:
        status = 'Current value unavailable'
    elif not adequate:
        status = 'Insufficient historical coverage'
    elif variable == 'temperature' and current > hi and difference >= 3:
        status, unusual = 'Unusually warm', True
    elif variable == 'temperature' and current < lo and difference <= -3:
        status, unusual = 'Unusually cold', True
    elif variable == 'wind' and current > hi and difference >= 10:
        status, unusual = 'Unusually windy', True
    elif variable == 'precipitation' and current > hi and difference >= 1 and current >= 1:
        status, unusual = 'Unusually wet hour', True
    return WeatherMetric(variable=variable, unit=unit, current=current,
                         historical_mean=mean, difference=difference, p05=lo, p95=hi,
                         sample_count=len(samples), year_count=int(years), samples=samples,
                         status=status, unusual=unusual, reading_time=timestamp)


def compare_current(location, *, refresh=False):
    weather = get_live_weather(location, refresh=refresh)
    if weather.location != location:
        raise ValueError('Current snapshot belongs to a different place.')
    now = datetime.now(timezone.utc)
    if weather.current_time.tzinfo is None or weather.retrieved_at.tzinfo is None:
        raise ValueError('Current snapshot needs timezone-aware timestamps.')
    if not -900 <= (now-weather.current_time).total_seconds() <= 5400 or not -60 <= (now-weather.retrieved_at).total_seconds() <= 600:
        raise ValueError('Current snapshot is expired; refresh it.')
    if weather.current_time.year <= 2020:
        raise ValueError('Live conditions must be after the historical reference period.')
    failure, source, stamp = None, None, None
    try:
        history, source, stamp = historical_hours(location, weather.timezone)
    except Exception:
        history = None
        failure = 'The historical baseline is unavailable. Current conditions and general precautions are shown; no historical anomaly can be established.'
    # Rainfall uses the latest completed model hour, not the 15-minute current interval.
    past = weather.hourly.loc[(weather.hourly.date <= weather.current_time)
                              & (weather.hourly.data_kind == 'Model estimate')]
    past = past.sort_values('date')
    rain_time = past.date.iloc[-1].to_pydatetime() if not past.empty else weather.current_time
    rain = past.precipitation.iloc[-1] if not past.empty else None
    rain = None if rain is None or pd.isna(rain) else float(rain)
    if (weather.current_time-rain_time).total_seconds() > 3600:
        rain = None
    values = {'temperature': (weather.current.get('temperature_2m'), weather.current_time),
              'wind': (weather.current.get('wind_speed_10m'), weather.current_time),
              'precipitation': (rain, rain_time)}
    metrics = [compare_metric(name, value, timestamp, history) for name, (value, timestamp) in values.items()]
    return WeatherComparison(location_key=location.key, location_label=location.label,
                             latitude=location.latitude, longitude=location.longitude,
                             conditions_time=weather.current_time, retrieved_at=weather.retrieved_at,
                             timezone=weather.timezone, current_source=weather.source,
                             baseline_source=source, baseline_retrieved_at=stamp,
                             baseline_error=failure, metrics=metrics)
