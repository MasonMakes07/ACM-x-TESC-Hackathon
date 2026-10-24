"""Download and validate NOAA CPC's published week-2/3 GTH KML layers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import math
import re
import xml.etree.ElementTree as ET

import requests

from schemas.global_hazards import HazardEvent, HazardFeed, HazardGeometry

SOURCE = 'https://www.cpc.ncep.noaa.gov/products/precip/CWlink/ghaz/index.php'
BASE = SOURCE.rsplit('/', 1)[0] + '/'
LAYERS = tuple(f'W{week}_{hazard}' for week in (2, 3) for hazard in ('TC', 'WET', 'DRY', 'WARM', 'COLD'))
NS = {'k': 'http://www.opengis.net/kml/2.2'}
DATE = r'(\d{1,2}/\d{1,2}/\d{2,4})'


class SourceError(ValueError):
    """An unavailable or inconsistent official publication."""


class _Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


def plain_text(html):
    parser = _Text()
    parser.feed(html)
    return ' '.join(parser.parts)


def parse_date(value):
    return datetime.strptime(value, '%m/%d/%Y' if len(value.rsplit('/', 1)[1]) == 4 else '%m/%d/%y').date()


def parse_page(html):
    text = plain_text(html)
    match = re.search(r'Last Updated\s*-?\s*' + DATE, text)
    if not match:
        raise SourceError('NOAA did not publish a readable issue date.')
    issued = parse_date(match[1])
    discussion = text.split('GTH Outlook Discussion', 1)
    if len(discussion) != 2:
        raise SourceError('NOAA outlook discussion is missing.')
    discussion = discussion[1].split('Product Release Information', 1)[0].strip()
    if len(discussion) < 80:
        raise SourceError('NOAA outlook discussion is incomplete.')
    return issued, discussion


def _ring(node):
    if node is None or not node.text:
        raise SourceError('A NOAA polygon has no coordinates.')
    ring = []
    for token in node.text.split():
        values = token.split(',')
        if len(values) < 2:
            raise SourceError('Malformed NOAA coordinates.')
        lon, lat = float(values[0]), float(values[1])
        if not math.isfinite(lon) or not math.isfinite(lat):
            raise SourceError('Non-finite NOAA coordinates.')
        # Some KML writers produce tiny floating-point overshoots at +/-180.
        if abs(lon) <= 180.000001:
            lon = max(-180.0, min(180.0, lon))
        ring.append((lon, lat))
    if ring and ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def _focus(geometry):
    """A representative map focus, with circular longitude for dateline regions."""
    ring = max((p[0] for p in geometry.coordinates), key=len)[:-1]
    longitude = math.degrees(math.atan2(sum(math.sin(math.radians(p[0])) for p in ring),
                                      sum(math.cos(math.radians(p[0])) for p in ring)))
    latitude = sum(p[1] for p in ring) / len(ring)
    return latitude, longitude


def parse_kml(xml, layer, expected_issue):
    if len(xml) > 12_000_000 or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise SourceError('Unexpected KML document.')
    root = ET.fromstring(xml)
    name = root.findtext('.//k:Document/k:name', default='', namespaces=NS)
    metadata = re.search(r'Issued:\s*' + DATE + r'\s+Valid:\s*' + DATE + r'\s*-\s*' + DATE, name)
    if not metadata:
        raise SourceError(f'{layer}: missing issue or validity dates.')
    issued, start, end = (parse_date(value) for value in metadata.groups())
    week, hazard = int(layer[1]), layer[3:]
    if issued != expected_issue or f'Week-{week}:' not in name:
        raise SourceError(f'{layer}: publication dates do not match the current NOAA edition.')
    events = []
    for index, placemark in enumerate(root.findall('.//k:Placemark', NS)):
        description = plain_text(placemark.findtext('k:description', default='', namespaces=NS))
        probability = re.search(r'\bprob\s+(\d+)\b', description, re.I)
        if not probability:
            for field in placemark.findall('.//k:Data', NS) + placemark.findall('.//k:SimpleData', NS):
                if field.get('name', '').lower() == 'prob':
                    probability = re.search(r'(\d+)', field.findtext('k:value', default=field.text or '', namespaces=NS))
        if not probability:
            raise SourceError(f'{layer}: a polygon has no published probability.')
        polygons = []
        for polygon in placemark.findall('.//k:Polygon', NS):
            outer = _ring(polygon.find('k:outerBoundaryIs/k:LinearRing/k:coordinates', NS))
            holes = [_ring(node) for node in polygon.findall('k:innerBoundaryIs/k:LinearRing/k:coordinates', NS)]
            polygons.append([outer, *holes])
        geometry = HazardGeometry(coordinates=polygons)
        lat, lon = _focus(geometry)
        digest = sha256(json.dumps([layer, issued.isoformat(), start.isoformat(), end.isoformat(), int(probability[1]),
                                    geometry.model_dump()], sort_keys=True).encode()).hexdigest()[:20]
        events.append(HazardEvent(event_id=f'gth-{digest}', hazard=hazard, week=week,
            probability=int(probability[1]), issued=issued, valid_start=start, valid_end=end,
            source_url=BASE + f'kmzs/{layer}.kml', source_feature=placemark.get('id', str(index)),
            geometry=geometry, latitude=lat, longitude=lon))
    if not events and 'NO HAZARDS POSTED' not in name.upper():
        raise SourceError(f'{layer}: empty document without a no-hazards declaration.')
    return events


def _download(url):
    response = requests.get(url, timeout=(10, 40), headers={'User-Agent': 'EarthWatch/1.0 NOAA hazard viewer'})
    response.raise_for_status()
    if len(response.content) > 12_000_000:
        raise SourceError('NOAA document is unexpectedly large.')
    return response.text


def load_noaa_hazards(*, download=_download):
    issued, discussion = parse_page(download(SOURCE))
    events, loaded, warnings = [], [], []
    with ThreadPoolExecutor(max_workers=5) as pool:
        pending = {pool.submit(download, BASE + f'kmzs/{layer}.kml'): layer for layer in LAYERS}
        for future in as_completed(pending):
            layer = pending[future]
            try:
                records = parse_kml(future.result(), layer, issued)
            except (OSError, ValueError, ET.ParseError) as error:
                warnings.append(f'{layer} unavailable: {type(error).__name__}. Coverage is incomplete.')
            else:
                events.extend(records)
                loaded.append(layer)
    if not loaded:
        raise SourceError('None of the NOAA hazard layers could be verified. Try refreshing shortly.')
    # Exact duplicate geometry is one event; fragmented source polygons remain separate.
    events = sorted({event.event_id: event for event in events}.values(), key=lambda e: (e.week, e.hazard, -e.probability, e.event_id))
    fingerprint = sha256(json.dumps([issued.isoformat(), discussion, [e.event_id for e in events]], sort_keys=True).encode()).hexdigest()
    return HazardFeed(issued=issued, retrieved_at=datetime.now(timezone.utc), discussion=discussion,
                      source_url=SOURCE, events=events, layers_loaded=sorted(loaded), warnings=sorted(warnings), fingerprint=fingerprint)
