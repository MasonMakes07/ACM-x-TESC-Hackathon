"""Owner: Person 1. Scientific, ingestion, cache and replay regression tests."""
import json
import numpy as np
import pandas as pd
import pytest
import requests
from analysis.anomaly_detection import calculate_anomaly, detect_series, detect_anomalies
from analysis.rainfall_analysis import rainfall_metrics, detect_rainfall
from analysis.validation import validate_series
from data.climate_sources import parse_sst, get_sst_series
from data.replay import replay, replay_rainfall, ROOT
from data.rainfall_sources import get_rainfall_history
from data import cache

HEADER = 'YR MON NINO1+2 ANOM NINO3 ANOM NINO4 ANOM NINO3.4 ANOM\n'


def sst(values, dates=None):
    dates = dates if dates is not None else pd.date_range('2017-01-01', periods=len(values), freq='MS')
    return pd.DataFrame(dict(date=dates, value=values, region='Nino 1+2', unit='degC', baseline_period='1991-2020', source='NOAA'))


@pytest.mark.parametrize('values,status', [([0.1, 0.2, 0.3], 'monitoring'), ([1, 1.2, 2], 'detected'), ([-1, -1.2, -2], 'detected')])
def test_sst_status(values, status):
    record = detect_series(sst(values))
    assert record.status == status
    assert record.value == values[-1]
    assert ('persistence=True' in record.detection_method) == (status == 'detected')


def test_gaps_and_opposite_sign_break_persistence():
    for frame in [sst([2, -2, 2]), sst([2, 2, 2], pd.to_datetime(['2017-01-01', '2017-03-01', '2017-04-01']))]:
        assert 'persistence=False' in detect_series(frame).detection_method


def test_missing_latest_is_error_not_fabricated_value():
    with pytest.raises(ValueError, match='Missing latest'):
        detect_series(sst([2, np.nan]))


def test_noaa_columns_and_no_double_subtraction():
    text = HEADER + '2017 3 28.0 1.83 27.0 0.1 28.0 0.2 27.0 -0.03\n'
    assert parse_sst(text, 'Nino 1+2').iloc[0]['value'] == 1.83
    assert parse_sst(text, 'Nino 3.4').iloc[0]['value'] == -0.03
    assert parse_sst(text.replace('1.83', '-999.9'), 'Nino 1+2')['value'].isna().all()


@pytest.mark.parametrize('text', ['<html>error</html>', HEADER, HEADER + '2017 13 28 1 27 1 28 1 27 1'])
def test_bad_noaa_payload(text):
    with pytest.raises((ValueError, pd.errors.EmptyDataError)):
        parse_sst(text, 'Nino 1+2')


@pytest.mark.parametrize('frame', [pd.DataFrame({'date':['bad'], 'value':[1]}), sst([1, 2], ['2017-01-01', '2017-01-01']), sst([np.inf])])
def test_invalid_observations(frame):
    with pytest.raises(ValueError):
        validate_series(frame)


def test_monthly_baseline_and_standardization():
    baseline = pd.DataFrame({'date':pd.date_range('1982-01-01', periods=360, freq='MS')})
    baseline['value'] = baseline['date'].dt.month * 100 + baseline['date'].dt.year - 1982
    observed = pd.DataFrame({'date':['2017-01-01', '2017-02-01'], 'value':[140, 240]})
    result = calculate_anomaly(observed, baseline)
    assert result['anomaly'].tolist() == [25.5, 25.5]
    assert result['z_score'].iloc[0] == pytest.approx(25.5 / np.std(np.arange(30), ddof=1))


def test_insufficient_and_zero_variance_baseline():
    baseline = sst([1] * 24, pd.date_range('2000-01-01', periods=24, freq='MS'))
    assert calculate_anomaly(sst([2]), baseline)['anomaly'].isna().all()
    assert calculate_anomaly(sst([2]), baseline, min_years=2)['z_score'].isna().all()


def rain():
    frame = pd.DataFrame({'date':pd.date_range('1982-01-01', '2017-12-31')})
    frame['value'] = np.where(frame['date'].dt.month == 1, 10.0, 1.0)
    frame['region'], frame['source'] = 'Piura', 'Open-Meteo'
    return frame


def test_rain_totals_missing_days_and_seasonality():
    frame = rain()
    frame.loc[frame['date'] == '2017-01-15', 'value'] = np.nan
    daily, monthly = rainfall_metrics(frame)
    assert daily.loc[daily['date'] == '2017-01-14', 'rolling_7day_mm'].iloc[0] == 70
    assert daily.loc[daily['date'] == '2017-01-16', 'rolling_7day_mm'].isna().all()
    assert monthly.loc[monthly['date'] == '2017-01-01', 'value'].isna().all()
    frame = frame.loc[frame['date'] != '2017-01-15']
    assert rainfall_metrics(frame)[1].loc[lambda x: x['date'] == '2017-01-01', 'value'].isna().all()


def test_extreme_rainfall_detection():
    frame = rain()
    frame.loc[frame['date'] >= '2017-12-25', 'value'] = 100
    record = detect_rainfall(frame)
    assert record.value == 700
    assert record.status == 'detected'
    assert record.region == 'Piura'


def test_rainfall_source_validation(monkeypatch):
    from data import rainfall_sources
    payload = dict(daily_units={'precipitation_sum':'mm'}, daily={'time':['2017-01-01', '2017-01-02'], 'precipitation_sum':[1.0, None]})
    monkeypatch.setattr(rainfall_sources, 'fetch_text', lambda *a, **k: (json.dumps(payload), '2017-02-01T00:00:00+00:00', False))
    frame = get_rainfall_history('Piura', '2017-01-01', '2017-01-02')
    assert frame['value'].isna().sum() == 1
    payload['daily_units']['precipitation_sum'] = 'inch'
    with pytest.raises(ValueError, match='units'):
        get_rainfall_history('Piura', '2017-01-01', '2017-01-02')


def test_cache_reuse_stale_and_failure(tmp_path, monkeypatch):
    monkeypatch.setenv('EARTHWATCH_CACHE_DIR', str(tmp_path))
    class Response:
        text = 'observations'
        def raise_for_status(self): pass
    monkeypatch.setattr(requests.Session, 'get', lambda *a, **k: Response())
    assert cache.fetch_text('https://example.test')[0] == 'observations'
    def fail(*a, **k): raise requests.ConnectionError('offline')
    monkeypatch.setattr(requests.Session, 'get', fail)
    assert cache.fetch_text('https://example.test')[2] is False
    assert cache.fetch_text('https://example.test', max_age=-1)[2] is True
    with pytest.raises(requests.ConnectionError):
        cache.fetch_text('https://uncached.test')


def test_offline_replay_is_real_chronological_and_no_future(monkeypatch):
    monkeypatch.setattr(requests.Session, 'get', lambda *a, **k: pytest.fail('Replay used network'))
    steps = list(replay())
    assert len(steps) == 12
    assert steps[2]['anomaly'].value == 1.83
    assert steps[2]['anomaly'].status == 'detected'
    for step in steps:
        assert step['series']['date'].max() == step['date']
    daily, monthly = replay_rainfall()
    assert len(daily) == 13149
    assert monthly['anomaly'].notna().any()
    assert set(json.loads((ROOT / 'manifest.json').read_text())['files']) == {'Nino_1_2.csv', 'Nino_3.4.csv', 'Piura.csv', 'Tumbes.csv'}


def test_entrypoint_contract(monkeypatch):
    from analysis import anomaly_detection
    monkeypatch.setattr(anomaly_detection, 'get_sst_series', lambda region: sst([2]))
    assert len(detect_anomalies()) == 2


@pytest.mark.parametrize('region', ['Nino 1+2', 'Nino 3.4'])
def test_both_regions_match_shared_contract(region):
    from data.replay import replay
    steps = list(replay(region))
    assert len(steps) == 12
    assert steps[-1]['anomaly'].region == region
    assert '.' not in steps[-1]['anomaly'].anomaly_id


def test_real_snapshots_cover_both_sources_and_baseline():
    from data.climate_sources import REGIONS
    from data.rainfall_sources import LOCATIONS
    for region in REGIONS:
        frame = list(replay(region))[-1]['series']
        assert len(frame) == 24
        assert frame['value'].notna().all()
        assert set(frame['baseline_period']) == {'1991-2020'}
        assert frame['retrieved_at'].notna().all()
    for location in LOCATIONS:
        frame = pd.read_csv(ROOT / (location + '.csv'), parse_dates=['date'])
        assert len(frame) == 13149
        assert frame['date'].min() == pd.Timestamp('1982-01-01')
        assert frame['date'].max() == pd.Timestamp('2017-12-31')
        assert frame['value'].notna().all()
        assert frame['value'].ge(0).all()
        assert set(frame['unit']) == {'mm/day'}
        assert set(frame['region']) == {location}
        assert frame['source'].str.startswith('https://archive-api.open-meteo.com/').all()


def test_translator_accepts_real_snapshot_outputs(monkeypatch):
    import translator
    from analysis import anomaly_detection
    from data import climate_sources
    def snapshot(region):
        return list(replay(region))[-1]['series']
    monkeypatch.setattr(anomaly_detection, 'get_sst_series', snapshot)
    monkeypatch.setattr(climate_sources, 'get_sst_series', snapshot)
    records, mock = translator.load_anomalies()
    assert len(records) == 2 and mock is False
    series, mock = translator.load_observation_series('Nino 3.4')
    assert len(series) == 24 and mock is False
