"""Owner: Person 1. Reproducible replay of the 2017 coastal Pacific event.

Run: python -m data.replay --refresh (requires network), then without --refresh.
"""
import argparse
import json
from pathlib import Path
import pandas as pd
from data.climate_sources import REGIONS, get_sst_series
from data.rainfall_sources import LOCATIONS, get_rainfall_history
from analysis.anomaly_detection import detect_series
from analysis.rainfall_analysis import rainfall_metrics

ROOT = Path(__file__).parent / 'historical'


def refresh_dataset():
    ROOT.mkdir(exist_ok=True)
    manifest = {'scenario': '2017 coastal Pacific warming', 'baseline': '1982-2011 rainfall; NOAA 1991-2020 SST', 'files': []}
    for region in REGIONS:
        frame = get_sst_series(region)
        frame = frame.loc[frame['date'].between('2016-01-01', '2017-12-31')]
        name = region.replace(' ', '_').replace('+', '_') + '.csv'
        frame.to_csv(ROOT / name, index=False)
        manifest['files'].append(name)
    for location in LOCATIONS:
        frame = get_rainfall_history(location, '1982-01-01', '2017-12-31')
        name = location + '.csv'
        frame.to_csv(ROOT / name, index=False)
        manifest['files'].append(name)
    (ROOT / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def replay(region='Nino 1+2', start_date='2017-01-01', end_date='2017-12-31'):
    """Yield chronological frames and same AnomalyRecord type as live detection."""
    if region not in REGIONS:
        raise ValueError('Unsupported replay region')
    start, end = pd.Timestamp(start_date), pd.Timestamp(end_date)
    if start > end:
        raise ValueError('Reversed replay dates')
    name = region.replace(' ', '_').replace('+', '_') + '.csv'
    frame = pd.read_csv(ROOT / name, parse_dates=['date'])
    selected = frame.loc[frame['date'].between(start, end)]
    if selected.empty:
        raise ValueError('No replay observations in selected period')
    for day in selected['date']:
        history = frame.loc[frame['date'] <= day].copy()
        yield {'date': day, 'series': history, 'anomaly': detect_series(history)}


def replay_rainfall(location='Piura'):
    if location not in LOCATIONS:
        raise ValueError('Unsupported rainfall location')
    frame = pd.read_csv(ROOT / (location + '.csv'), parse_dates=['date'])
    daily, monthly = rainfall_metrics(frame)
    return daily, monthly


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    if args.refresh:
        refresh_dataset()
    for step in replay():
        print(step['anomaly'].model_dump_json())
