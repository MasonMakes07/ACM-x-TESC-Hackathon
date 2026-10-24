"""Owner: Person 1. Open-Meteo ERA5 daily precipitation, not station gauges."""
import json
from datetime import date
import pandas as pd
from analysis.validation import validate_series
from data.cache import fetch_text

SOURCE = 'https://archive-api.open-meteo.com/v1/archive'
LOCATIONS = {'Piura': (-5.1945, -80.6328), 'Tumbes': (-3.5669, -80.4515)}


def get_rainfall_history(location, start_date, end_date):
    from data.locations import Location
    if isinstance(location, Location):
        from data.weather_sources import get_weather_history
        frame = get_weather_history(location, start_date, end_date)
        frame = frame.drop(columns=['temperature']).rename(columns={'precipitation':'value'})
        frame['unit'] = 'mm/day'
        return frame
    if location not in LOCATIONS:
        raise ValueError(f'Unsupported rainfall location: {location}')
    start, end = date.fromisoformat(str(start_date)), date.fromisoformat(str(end_date))
    if start > end or end >= date.today():
        raise ValueError('Expected a historical date range in chronological order')
    lat, lon = LOCATIONS[location]
    params = dict(latitude=lat, longitude=lon, start_date=str(start), end_date=str(end), daily='precipitation_sum', timezone='America/Lima', models='era5', precipitation_unit='mm')
    text, stamp, stale = fetch_text(SOURCE, params)
    payload = json.loads(text)
    if payload.get('daily_units', {}).get('precipitation_sum') != 'mm':
        raise ValueError('Unexpected rainfall units')
    daily = payload['daily']
    frame = validate_series(pd.DataFrame({'date': daily['time'], 'value': daily['precipitation_sum']}))
    expected = pd.date_range(start, end)
    if len(frame) != len(expected) or not (frame['date'].to_numpy() == expected.to_numpy()).all():
        raise ValueError('Rainfall response does not cover requested dates')
    if (frame['value'].dropna() < 0).any():
        raise ValueError('Negative precipitation is invalid')
    frame['region'] = location
    frame['unit'] = 'mm/day'
    frame['source'] = SOURCE
    frame['latitude'], frame['longitude'] = lat, lon
    frame['retrieved_at'], frame['cache_stale'] = stamp, stale
    frame['measurement_kind'] = 'ERA5 reanalysis precipitation'
    return frame
