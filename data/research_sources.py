"""Official weather and NASA satellite imagery adapters."""
from datetime import datetime, timezone, timedelta
from io import BytesIO
import hashlib
import json
import math
import os
from pathlib import Path

import requests

from data.cache import fetch_text
from data.station_weather import get_station_observation

USER_AGENT = 'EarthWatch/0.1 (https://github.com/MasonMakes07/ACM-x-TESC-Hackathon)'
MET_URL = 'https://api.met.no/weatherapi/locationforecast/2.0/compact'
GIBS_URL = 'https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi'
SATELLITE_LAYERS = ('MODIS_Terra_CorrectedReflectance_TrueColor', 'MODIS_Aqua_CorrectedReflectance_TrueColor')


def _now():
    return datetime.now(timezone.utc)


def _json(url, params=None):
    text, stamp, stale = fetch_text(url, params, max_age=300, allow_stale=False)
    if stale:
        raise ValueError('Expired research response')
    return json.loads(text), stamp


def national_weather(location):
    """Official national agency data: station/alerts are distinct from forecasts."""
    result = dict(status='ok', requested_coordinates=[location.latitude, location.longitude], sources=[], unavailable=[])
    if location.country_code == 'US' or (not location.country_code and 24 <= location.latitude <= 72 and -170 <= location.longitude <= -66):
        station = get_station_observation(location)
        result['station'] = station
        if station['status'] == 'ok':
            result['sources'].append(dict(name='NOAA NWS '+station['station']+' station observation', url=station['source'], kind='measurement', retrieved_at=station['retrieved_at']))
        else:
            result['unavailable'].append(station['reason'])
        try:
            url = 'https://api.weather.gov/alerts/active'
            raw, stamp = _json(url, {'point':f'{location.latitude},{location.longitude}'})
            if not isinstance(raw.get('features'),list):
                raise ValueError('Invalid NWS alerts response')
            alerts = []
            for feature in raw['features']:
                props = feature['properties']
                expires = datetime.fromisoformat(props['expires'].replace('Z','+00:00')) if props.get('expires') else None
                if expires and expires <= _now():
                    continue
                alerts.append({key:props.get(key) for key in ['event','severity','certainty','sent','effective','onset','expires','headline','description','instruction']})
            result['alerts'] = alerts[:10]
            result['sources'].append(dict(name='NOAA NWS active alerts for selected point',url=requests.Request('GET',url,params={'point':f'{location.latitude},{location.longitude}'}).prepare().url,kind='official_report',retrieved_at=stamp))
        except Exception:
            result['unavailable'].append('NOAA NWS active alerts could not be retrieved; do not infer that there are no alerts.')
    try:
        raw, stamp = _json(MET_URL, {'lat':round(location.latitude,4),'lon':round(location.longitude,4)})
        metadata = raw['properties']['meta']
        issued = datetime.fromisoformat(metadata['updated_at'].replace('Z','+00:00'))
        if not -300 <= (_now()-issued).total_seconds() <= 86400:
            raise ValueError('MET Norway forecast is out of date')
        units = metadata['units']
        if units['air_temperature'] != 'celsius' or units['wind_speed'] != 'm/s':
            raise ValueError('Unexpected national forecast units')
        rows=[]
        for item in raw['properties']['timeseries']:
            valid = datetime.fromisoformat(item['time'].replace('Z','+00:00'))
            if not _now()-timedelta(hours=1) <= valid <= _now()+timedelta(hours=12):
                continue
            details=item['data']['instant']['details']
            temperature, wind = details['air_temperature'],details['wind_speed']
            if not all(isinstance(value,(float,int)) and math.isfinite(value) for value in [temperature,wind]) or wind < 0:
                raise ValueError('Invalid forecast measurements')
            rows.append(dict(valid_at=item['time'],temperature_degC=temperature,wind_speed_kmh=round(wind*3.6,2),data_kind='Forecast'))
        if not rows:
            raise ValueError('No recent MET Norway forecast')
        result['forecast'] = dict(source='MET Norway Locationforecast',issued_at=metadata['updated_at'],retrieved_at=stamp,rows=rows)
        result['sources'].append(dict(name='MET Norway Locationforecast',url=requests.Request('GET',MET_URL,params={'lat':round(location.latitude,4),'lon':round(location.longitude,4)}).prepare().url,kind='reference',retrieved_at=stamp))
    except Exception:
        result['unavailable'].append('MET Norway forecast unavailable.')
    if not result['sources']:
        result['status']='unavailable'
    result['caveat']='MET Norway values are forecasts, not station observations. NWS alerts are official reports. Neither implies a country-wide measurement.'
    return result


def satellite_imagery(location, scene_date):
    """Download actual Terra/Aqua MODIS PNGs; blank tiles are not evidence."""
    from PIL import Image
    day = datetime.fromisoformat(scene_date).date()
    if day > _now().date() or day < _now().date()-timedelta(days=7):
        raise ValueError('Select a satellite scene within the last seven days, not the future')
    lat = max(-89.5,min(89.5,location.latitude))
    lon = max(-179.5,min(179.5,location.longitude))
    bounds=[lon-0.5,lat-0.5,lon+0.5,lat+0.5]
    root=Path(os.getenv('EARTHWATCH_CACHE_DIR','.cache/earthwatch'))/'satellites'
    images=[]
    for layer in SATELLITE_LAYERS:
        params=dict(SERVICE='WMS',REQUEST='GetMap',VERSION='1.1.1',LAYERS=layer,STYLES='',FORMAT='image/png',TRANSPARENT='TRUE',SRS='EPSG:4326',BBOX=','.join(map(str,bounds)),WIDTH=256,HEIGHT=256,TIME=day.isoformat())
        url=requests.Request('GET',GIBS_URL,params=params).prepare().url
        try:
            path=root/(hashlib.sha256(url.encode()).hexdigest()+'.png')
            if path.exists() and (_now().timestamp()-path.stat().st_mtime)<3600:
                content=path.read_bytes()
                retrieved=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat()
            else:
                response=requests.get(url,headers={'User-Agent':USER_AGENT},timeout=(10,30))
                response.raise_for_status()
                content=response.content
                retrieved=_now().isoformat()
            if len(content)>5_000_000:
                raise ValueError('Satellite image is too large')
            if not content.startswith(b'\x89PNG\r\n\x1a\n') or len(content)>5_000_000:
                raise ValueError('Satellite server returned no valid PNG')
            image=Image.open(BytesIO(content)).convert('RGBA')
            if image.getchannel('A').getbbox() is None:
                continue
            root.mkdir(parents=True,exist_ok=True)
            if not path.exists() or path.read_bytes()!=content:
                path.write_bytes(content)
            else:
                path.touch()
            images.append(dict(source='NASA GIBS '+layer,scene_date=day.isoformat(),retrieved_at=retrieved,url=url,local_path=str(path.resolve()),bbox=bounds,layer=layer,data_kind='Satellite true-color imagery',interpretation='Imagery has not been interpreted or converted to weather measurements.'))
        except Exception:
            continue
    return dict(status='ok' if images else 'unavailable',requested_coordinates=[location.latitude,location.longitude],images=images,
                reason=None if images else 'No nonblank satellite scene was available. Try an earlier date; availability depends on overpass and processing.',
                caveat='Daily satellite scenes are not current station temperatures or proof of present conditions. Cloud, overpass, polar night, and processing latency affect coverage.')
