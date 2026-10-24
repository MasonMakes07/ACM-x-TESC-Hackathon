"""Global ERA5 temperature and precipitation at any validated coordinates."""
from datetime import date
import json
import pandas as pd
from analysis.validation import validate_series
from data.cache import fetch_text
from data.locations import Location

SOURCE = 'https://archive-api.open-meteo.com/v1/archive'


def get_weather_history(location, start_date, end_date):
    if not isinstance(location, Location):
        raise ValueError('Select a location or supply validated coordinates')
    start, end = date.fromisoformat(str(start_date)), date.fromisoformat(str(end_date))
    if start < date(1940, 1, 1) or start > end or end >= date.today():
        raise ValueError('Choose historical dates from 1940 onward')
    params = dict(latitude=location.latitude, longitude=location.longitude, start_date=str(start), end_date=str(end), daily='temperature_2m_mean,precipitation_sum', temperature_unit='celsius', precipitation_unit='mm', timezone=location.timezone, models='era5', cell_selection='nearest')
    text, stamp, stale = fetch_text(SOURCE, params)
    payload = json.loads(text)
    if payload.get('error'):
        raise ValueError(payload.get('reason', 'Weather source failed'))
    units = payload.get('daily_units', {})
    if units.get('temperature_2m_mean') != '\u00b0C' or units.get('precipitation_sum') != 'mm':
        raise ValueError('Unexpected weather measurement units')
    raw = payload['daily']
    frame = pd.DataFrame({'date': raw['time'], 'temperature':raw['temperature_2m_mean'], 'precipitation':raw['precipitation_sum']})
    frame['date'] = pd.to_datetime(frame['date'], errors='raise')
    frame = frame.sort_values('date').reset_index(drop=True)
    for column in ['temperature', 'precipitation']:
        checked = validate_series(frame[['date', column]].rename(columns={column:'value'}))
        frame['date'], frame[column] = checked['date'], checked['value']
    expected = pd.date_range(start, end)
    if len(frame) != len(expected) or not (frame['date'].to_numpy() == expected.to_numpy()).all():
        raise ValueError('Weather source returned incomplete date coverage')
    if frame['precipitation'].dropna().lt(0).any():
        raise ValueError('Negative precipitation is invalid')
    frame['region'], frame['country_code'] = location.label, location.country_code
    frame['latitude'], frame['longitude'] = location.latitude, location.longitude
    frame['grid_latitude'], frame['grid_longitude'] = payload.get('latitude'), payload.get('longitude')
    frame['timezone'] = payload.get('timezone', location.timezone)
    frame['source'], frame['retrieved_at'], frame['cache_stale'] = SOURCE, stamp, stale
    frame['measurement_kind'] = 'ERA5 reanalysis'
    return frame
