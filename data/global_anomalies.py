"""Worldwide anomaly feeds: Climate Reanalyzer (UMaine) and NASA Earth Observatory."""
from dataclasses import dataclass
from datetime import date, timedelta
from html import unescape
import json
import re

import pandas as pd
import requests

from data.cache import fetch_text

WORLD_T2 = 'https://climatereanalyzer.org/clim/t2_daily/json/era5_world_t2_day.json'
WORLD_T2_PAGE = 'https://climatereanalyzer.org/clim/t2_daily/'
TODAYS_WEATHER = 'https://climatereanalyzer.org/wx/todays-weather/'
MAPS = TODAYS_WEATHER + 'maps/gfs_{region}_{variable}_d1.png'
BASELINE = '1991-2020'
NASA_LST_PAGE = 'https://science.nasa.gov/earth/earth-observatory/global-maps/land-surface-temperature-anomaly/'
NASA_LST_VIDEO = 'https://assets.science.nasa.gov/content/dam/science/esd/eo/gmap/MOD_LSTAD_M.mp4'
NASA_LST_STILL = 'https://assets.science.nasa.gov/content/dam/science/esd/eo/gmap/MOD_LSTAD_M_feature.jpeg/jcr:content/renditions/cq5dam.web.1280.1280.jpeg'
HEADERS = {'User-Agent': 'EarthWatch/0.1 (https://github.com/MasonMakes07/ACM-x-TESC-Hackathon)'}

MAP_VARIABLES = {
    'Air temperature anomaly (2 m)': 't2anom',
    'Sea surface temperature anomaly': 'sstanom',
    'Sea-level pressure anomaly (σ)': 'mslp-anomsd',
    'Atmospheric moisture anomaly (σ)': 'pwtr-anomsd',
    'Jet-level height anomaly (500 hPa, σ)': 'gph500-anomsd',
    'Precipitation & pressure': 'prcp-mslp',
}
MAP_REGIONS = {
    'Whole world': 'world-wt',
    'Northern Hemisphere': 'nh-sat1',
    'Europe & Africa': 'euroafr-sat',
    'Asia': 'asia-sat',
    'South America': 'samer-sat',
    'Australia & New Zealand': 'ausnz-sat',
    'Pacific': 'pacific-sat',
    'Arctic': 'npole-sat',
    'Antarctic': 'spole-sat',
}


@dataclass(frozen=True)
class Story:
    title: str
    summary: str
    published: str
    url: str
    image: str | None


def map_url(variable, region):
    if variable not in MAP_VARIABLES.values() or region not in MAP_REGIONS.values():
        raise ValueError('Unsupported Climate Reanalyzer map.')
    return MAPS.format(region=region, variable=variable)


def fetch_image(url):
    response = requests.get(url, headers=HEADERS, timeout=(10, 30))
    response.raise_for_status()
    if not response.headers.get('content-type', '').startswith('image/'):
        raise ValueError('Map source did not return an image.')
    return response.content


def parse_world_t2(text):
    """Daily world-mean 2 m air temperature (ERA5) as long rows with a 1991-2020 anomaly.

    Each series has 366 day-of-year slots; non-leap years leave the last slot empty.
    """
    series = {item['name']: item['data'] for item in json.loads(text)}
    if BASELINE not in series:
        raise ValueError('World temperature feed is missing its 1991-2020 climatology.')
    normal = series[BASELINE]
    rows = []
    for name, values in series.items():
        if not name.isdigit() or len(values) != 366:
            continue
        year = int(name)
        for index, value in enumerate(values):
            day = date(year, 1, 1) + timedelta(days=index)
            if value is None or day.year != year or normal[index] is None:
                continue
            rows.append((day, year, index, float(value), float(value) - float(normal[index])))
    frame = pd.DataFrame(rows, columns=['date', 'year', 'day_index', 'temperature', 'anomaly'])
    if frame.empty:
        raise ValueError('World temperature feed contained no observations.')
    frame['date'] = pd.to_datetime(frame['date'])
    return frame.sort_values('date').reset_index(drop=True)


def world_temperature():
    text, stamp, stale = fetch_text(WORLD_T2, max_age=6 * 3600)
    return parse_world_t2(text), stamp, stale


def summarize(frame):
    latest = frame.iloc[-1]
    same_day = frame[frame['day_index'] == latest['day_index']].sort_values('temperature', ascending=False)
    rank = int((same_day['temperature'] > latest['temperature']).sum()) + 1
    record = same_day.iloc[0]
    recent = frame[frame['date'] > latest['date'] - pd.Timedelta(days=30)]
    year = frame[frame['year'] == latest['year']]
    return dict(date=latest['date'].date(), temperature=latest['temperature'], anomaly=latest['anomaly'],
                anomaly_30d=recent['anomaly'].mean(), anomaly_ytd=year['anomaly'].mean(),
                rank=rank, years=len(same_day), record_year=int(record['year']),
                record_temperature=record['temperature'])


def _clean(value):
    return re.sub(r'\s+', ' ', unescape(re.sub(r'<[^>]+>', '', value or ''))).strip()


def parse_stories(page):
    """Recent Earth stories linked from the NASA global map page: newest highlights, then related articles."""
    stories, seen = [], set()
    image = r'src="(https://assets\.science\.nasa\.gov/[^"]+\.(?:jpe?g|png)[^"]*)"'
    highlight = re.compile(r'<a href="(?P<url>https://science\.nasa\.gov/earth/[^"]+)" class="hds-content-card[^"]*"[^>]*>(?P<body>.*?)</a>', re.S)
    related = re.compile(
        r'<a href="(?P<url>https://science\.nasa\.gov/earth/[^"]+)" class="hds-content-item-heading">\s*'
        r'<div[^>]*>(?P<title>.*?)</div>\s*</a>\s*(?:<p[^>]*>(?P<summary>.*?)</p>)?\s*'
        r'(?:<div class="label[^"]*">(?P<date>.*?)</div>)?', re.S)

    def add(url, title, summary, published, picture):
        if url in seen or '/global-maps/' in url or not title:
            return
        seen.add(url)
        stories.append(Story(title, summary, published, url, unescape(picture) if picture else None))

    for match in highlight.finditer(page):
        body = re.sub(r'<svg.*?</svg>', '', match['body'], flags=re.S)
        title = re.search(r'<h3[^>]*>(.*?)</h3>', body, re.S)
        spans = [_clean(s) for s in re.findall(r'<span>(.*?)</span>', body, re.S)]
        pictures = re.findall(image, body)
        add(match['url'], _clean(title[1]) if title else '', '', spans[-1] if spans else '',
            pictures[0] if pictures else None)
    for match in related.finditer(page):
        pictures = re.findall(image, page[max(0, match.start() - 4000):match.start()])
        add(match['url'], _clean(match['title']), _clean(match['summary']), _clean(match['date']),
            pictures[-1] if pictures else None)
    return stories


def nasa_stories():
    text, stamp, stale = fetch_text(NASA_LST_PAGE, max_age=12 * 3600)
    return parse_stories(text), stamp, stale
