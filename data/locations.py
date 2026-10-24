"""Worldwide place search and validated coordinate locations."""
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from data.cache import fetch_text

GEOCODING_URL = 'https://geocoding-api.open-meteo.com/v1/search'


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    country: str = ''
    country_code: str = ''
    admin1: str = ''
    timezone: str = 'auto'

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError('A location name is required')
        if not math.isfinite(self.latitude) or not -90 <= self.latitude <= 90:
            raise ValueError('Latitude must be between -90 and 90')
        if not math.isfinite(self.longitude) or not -180 <= self.longitude <= 180:
            raise ValueError('Longitude must be between -180 and 180')
        if self.country_code and not re.fullmatch(r'[A-Z]{2}', self.country_code):
            raise ValueError('Country code must be two uppercase letters')

    @property
    def label(self):
        return ', '.join(dict.fromkeys(part for part in [self.name, self.admin1, self.country] if part))

    @property
    def key(self):
        return hashlib.sha256(f'{self.latitude:.6f},{self.longitude:.6f}'.encode()).hexdigest()[:16]


def countries():
    """Bundled GeoNames country/territory list; no network needed for picker."""
    return json.loads((Path(__file__).parent / 'countries.json').read_text(encoding='utf-8'))


def search_locations(query, country_code=None):
    query = query.strip()
    if len(query) < 2:
        raise ValueError('Enter at least two characters or use coordinates')
    params = dict(name=query, count=100, language='en', format='json')
    if country_code:
        country_code = country_code.upper()
        if not re.fullmatch(r'[A-Z]{2}', country_code):
            raise ValueError('Invalid country code')
        params['countryCode'] = country_code
    text, _, _ = fetch_text(GEOCODING_URL, params, max_age=30 * 86400)
    payload = json.loads(text)
    if payload.get('error'):
        raise ValueError(payload.get('reason', 'Location search failed'))
    results = []
    for item in payload.get('results', []):
        if country_code and item.get('country_code') != country_code:
            continue
        results.append(Location(name=item['name'], latitude=float(item['latitude']), longitude=float(item['longitude']), country=item.get('country', ''), country_code=item.get('country_code', ''), admin1=item.get('admin1', ''), timezone=item.get('timezone', 'auto')))
    return results
