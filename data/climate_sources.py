"""Owner: Person 1. NOAA CPC monthly OI SST, published 1991-2020 anomalies."""
from io import StringIO
import pandas as pd
from analysis.validation import validate_series
from data.cache import fetch_text

SOURCE = 'https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices'
BASELINE = '1991-2020'
REGIONS = {'Nino 1+2': (2, 3), 'Nino 3.4': (8, 9)}


def parse_sst(text, region):
    if region not in REGIONS:
        raise ValueError(f'Unsupported SST region: {region}')
    if not text.splitlines() or text.splitlines()[0].split() != ['YR', 'MON', 'NINO1+2', 'ANOM', 'NINO3', 'ANOM', 'NINO4', 'ANOM', 'NINO3.4', 'ANOM']:
        raise ValueError('Unexpected NOAA SST header')
    raw = pd.read_csv(StringIO(text), sep=r'\s+', skiprows=1, header=None)
    if raw.empty or raw.shape[1] != 10:
        raise ValueError('Unexpected NOAA SST table')
    actual, anomaly = REGIONS[region]
    dates = pd.to_datetime(dict(year=raw[0], month=raw[1], day=1))
    frame = pd.DataFrame(dict(date=dates, value=raw[anomaly], sst=raw[actual]))
    for column in ['value', 'sst']:
        frame[column] = pd.to_numeric(frame[column], errors='raise').mask(lambda x: x <= -99)
    frame['region'] = region
    frame['unit'] = 'degC'
    frame['baseline_period'] = BASELINE
    frame['source'] = SOURCE
    frame['measurement_kind'] = 'published SST anomaly'
    return validate_series(frame)


def get_sst_series(region: str) -> pd.DataFrame:
    if region not in REGIONS:
        raise ValueError(f'Unsupported SST region: {region}')
    text, stamp, stale = fetch_text(SOURCE)
    frame = parse_sst(text, region)
    frame['retrieved_at'] = stamp
    frame['cache_stale'] = stale
    return frame
