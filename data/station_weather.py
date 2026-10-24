"""Independent, recent US station observations from the official NWS API."""
from datetime import datetime, timezone
import json
import math
import requests

from data.cache import fetch_text

ROOT = 'https://api.weather.gov'


def _now():
    return datetime.now(timezone.utc)


def _get(url, refresh=False):
    text, retrieved, stale = fetch_text(url, max_age=0 if refresh else 300, allow_stale=False)
    if stale:
        raise ValueError('Station response is stale')
    return json.loads(text), retrieved


def _distance(lat, lon, other_lat, other_lon):
    lat, lon, other_lat, other_lon = map(math.radians, [lat, lon, other_lat, other_lon])
    hav = math.sin((other_lat-lat)/2)**2 + math.cos(lat)*math.cos(other_lat)*math.sin((other_lon-lon)/2)**2
    return 6371 * 2 * math.asin(min(1, math.sqrt(hav)))


def _quantity(properties, name, allowed):
    item = properties.get(name) or {}
    value = item.get('value')
    if value is None:
        return None
    if isinstance(value,bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError('Invalid station value')
    unit = item.get('unitCode')
    if unit not in allowed:
        raise ValueError(f'Unexpected station units for {name}')
    if name in {'windSpeed','precipitationLastHour'} and value < 0:
        raise ValueError('Negative station wind or precipitation')
    if name == 'relativeHumidity' and not 0 <= value <= 100:
        raise ValueError('Invalid station humidity')
    if item.get('qualityControl') == 'X':
        raise ValueError('Station quality control rejected this value')
    return float(value) * allowed[unit]


def get_station_observation(location, *, refresh=False):
    """Find a nearby reporting station; fail explicitly rather than use old data."""
    try:
        point, _ = _get(f'{ROOT}/points/{location.latitude:.4f},{location.longitude:.4f}', refresh)
        stations_url = point['properties']['observationStations']
        if not stations_url.startswith(ROOT + '/'):
            raise ValueError('Unexpected station directory URL')
        directory, _ = _get(stations_url)
        candidates = []
        for feature in directory['features']:
            lon, lat = feature['geometry']['coordinates'][:2]
            distance = _distance(location.latitude, location.longitude, lat, lon)
            station = feature['properties']['stationIdentifier']
            if distance <= 50 and station.isalnum():
                candidates.append((distance, station, feature['properties'].get('name', station)))
        for distance, station, name in sorted(candidates)[:5]:
            url = f'{ROOT}/stations/{station}/observations/latest'
            try:
                payload, retrieved = _get(url, refresh)
                props = payload['properties']
                stamp = datetime.fromisoformat(props['timestamp'].replace('Z', '+00:00'))
                age = (_now() - stamp).total_seconds()
                if not -300 <= age <= 5400:
                    continue
                temperature = _quantity(props, 'temperature', {'wmoUnit:degC':1})
                if temperature is None:
                    continue
                return dict(status='ok', station=station, name=name, distance_km=round(distance,2),
                            observed_at=stamp.isoformat(), retrieved_at=retrieved, source=url,
                            temperature_degC=temperature,
                            relative_humidity_pct=_quantity(props, 'relativeHumidity', {'wmoUnit:percent':1}),
                            wind_speed_kmh=_quantity(props, 'windSpeed', {'wmoUnit:km_h-1':1,'wmoUnit:m_s-1':3.6}),
                            precipitation_last_hour_mm=_quantity(props, 'precipitationLastHour', {'wmoUnit:mm':1,'wmoUnit:m':1000}),
                            description=props.get('textDescription'), data_kind='Station observation')
            except (ValueError, KeyError, TypeError, requests.RequestException):
                continue
        return dict(status='unavailable', reason='No station within 50 km has a temperature observation less than 90 minutes old.')
    except Exception:
        return dict(status='unavailable', reason='An independent NWS station observation is unavailable for this location right now.')


def compare_station(weather, station):
    if station.get('status') != 'ok':
        return dict(status='unavailable', reason=station.get('reason'))
    observed = datetime.fromisoformat(station['observed_at'])
    difference_minutes = abs((weather.current_time-observed).total_seconds()) / 60
    if difference_minutes > 60 or observed.astimezone(weather.current_time.tzinfo).date() != weather.current_time.date():
        return dict(status='not_time_aligned', separation_minutes=round(difference_minutes,2))
    temperature = weather.current['temperature_2m']
    if temperature is None:
        return dict(status='unavailable', reason='Current model temperature is missing.')
    delta = temperature-station['temperature_degC']
    return dict(status='compared', model_minus_station_degC=round(delta,2), separation_minutes=round(difference_minutes,2),
                note='Different timestamps and spatial coverage; this comparison does not prove forecast accuracy.')
