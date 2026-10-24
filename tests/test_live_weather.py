"""Live weather freshness, dates, units, cache policy, and dashboard behavior."""
from datetime import datetime, timezone
import json
from pathlib import Path

import pytest
import requests
from streamlit.testing.v1 import AppTest

from data import cache, live_weather
from data.locations import Location
from schemas.errors import TranslatorError
import translator

NOW = datetime(2026, 10, 24, 18, 30, tzinfo=timezone.utc)
APP = str(Path(__file__).resolve().parent.parent / 'app.py')


def payload(zone='America/Los_Angeles', midnight='2026-10-24T07:00:00+00:00'):
    start = datetime.fromisoformat(midnight).timestamp()
    current = {field: 12 for field in live_weather.FIELDS}
    current.update(time=NOW.timestamp(), interval=900)
    return {
        'timezone': zone, 'latitude': 32.75, 'longitude': -117.25,
        'current_units': live_weather.FIELDS.copy(),
        'hourly_units': live_weather.FIELDS.copy(),
        'current': current,
        'hourly': {'time':[start + hour * 3600 for hour in range(24)],
                   **{field:[12] * 24 for field in live_weather.FIELDS}},
    }


@pytest.fixture
def source(monkeypatch):
    body = payload()
    calls = []
    monkeypatch.setattr(live_weather, '_now', lambda: NOW)
    monkeypatch.setattr(translator,'load_station_weather',lambda *a,**k:dict(status='unavailable',reason='No test station'))
    def fetch(url, params, **kwargs):
        calls.append((url, params, kwargs))
        return json.dumps(body), NOW.isoformat(), False
    monkeypatch.setattr(live_weather, 'fetch_text', fetch)
    return body, calls


def test_today_current_and_forecast_are_separate_and_attributed(source):
    body, calls = source
    result = live_weather.get_live_weather(Location('San Diego', 32.73, -117.18))
    assert result.current_time.date().isoformat() == '2026-10-24'
    assert result.current_time.hour == 11
    assert result.interval_seconds == 900
    assert len(result.hourly) == 24
    assert set(result.hourly['data_kind']) == {'Model estimate', 'Forecast'}
    assert calls[0][0] == live_weather.SOURCE
    assert calls[0][1]['latitude'] == 32.73
    assert calls[0][1]['timeformat'] == 'unixtime'
    assert calls[0][2] == {'max_age':300, 'allow_stale':False}
    live_weather.get_live_weather(result.location, refresh=True)
    assert calls[-1][2]['max_age'] == 0
    assert result.hourly['source'].eq(live_weather.SOURCE).all()


def test_local_today_across_international_date_line(source):
    body, _ = source
    body.update(payload('Pacific/Auckland', '2026-10-24T11:00:00+00:00'))
    result = live_weather.get_live_weather(Location('Auckland', -36.85, 174.76))
    assert result.current_time.date().isoformat() == '2026-10-25'
    assert all(day.isoformat() == '2026-10-25' for day in result.hourly.date.dt.date)


@pytest.mark.parametrize('fault', ['yesterday','future','units','negative_rain','infinity','humidity','duplicate_time','missing_today','no_current'])
def test_bad_live_data_rejected(source, fault):
    body, _ = source
    if fault == 'yesterday': body['current']['time'] -= 86400
    if fault == 'future': body['current']['time'] += 7200
    if fault == 'units': body['current_units']['temperature_2m'] = 'F'
    if fault == 'negative_rain': body['current']['precipitation'] = -1
    if fault == 'infinity': body['current']['temperature_2m'] = float('inf')
    if fault == 'humidity': body['current']['relative_humidity_2m'] = 110
    if fault == 'duplicate_time': body['hourly']['time'][1] = body['hourly']['time'][0]
    if fault == 'missing_today': body['hourly']['time'] = [t - 86400 for t in body['hourly']['time']]
    if fault == 'no_current': body['current'].update({key:None for key in live_weather.FIELDS})
    with pytest.raises(ValueError):
        live_weather.get_live_weather(Location('Test', 1, 2))


def test_missing_values_stay_unavailable(source):
    body, _ = source
    body['current']['temperature_2m'] = None
    body['hourly']['temperature_2m'][0] = None
    result = live_weather.get_live_weather(Location('Test', 1, 2))
    assert result.current['temperature_2m'] is None
    assert result.hourly['temperature_2m'].isna().sum() == 1


def test_live_cache_never_falls_back_to_expired_data(tmp_path, monkeypatch):
    monkeypatch.setenv('EARTHWATCH_CACHE_DIR', str(tmp_path))
    class Response:
        text = 'weather'
        def raise_for_status(self): pass
    monkeypatch.setattr(requests.Session, 'get', lambda *a, **k:Response())
    cache.fetch_text('https://example.test')
    def offline(*a, **k): raise requests.ConnectionError('offline')
    monkeypatch.setattr(requests.Session, 'get', offline)
    with pytest.raises(requests.ConnectionError):
        cache.fetch_text('https://example.test', max_age=0, allow_stale=False)


def test_stale_return_and_old_retrieval_rejected(monkeypatch):
    monkeypatch.setattr(live_weather, '_now', lambda:NOW)
    for stamp, stale in [(NOW.isoformat(), True), ('2026-10-23T18:30:00+00:00', False)]:
        monkeypatch.setattr(live_weather, 'fetch_text', lambda *a, **k:(json.dumps(payload()), stamp, stale))
        with pytest.raises(ValueError):
            live_weather.get_live_weather(Location('Test', 1, 2))


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_live_ui_load_refresh_and_location_change(source, monkeypatch):
    calls = []
    def load(location, *, refresh=False):
        calls.append(refresh)
        return live_weather.get_live_weather(location, refresh=refresh)
    monkeypatch.setattr(translator, 'load_live_weather', load)
    app = AppTest.from_file(APP).run()
    app.radio[1].set_value('Coordinates').run()
    app.text_input[0].set_value('San Diego').run()
    button(app, "Load today's weather").click().run()
    assert not app.exception
    assert len(app.metric) == 5
    assert 'San Diego' in app.subheader[0].value
    assert app.metric[0].value == '12 \u00b0C'
    assert calls[-1] is True
    button(app, 'Refresh live weather').click().run()
    assert not app.exception and calls[-1] is True
    app.number_input[0].set_value(45.0).run()
    assert not app.metric


def test_live_ui_failure_clears_previous_conditions(source, monkeypatch):
    app = AppTest.from_file(APP).run()
    app.radio[1].set_value('Coordinates').run()
    button(app, "Load today's weather").click().run()
    assert app.metric and not app.exception
    def unavailable(*a, **k): raise TranslatorError('Live source unavailable')
    monkeypatch.setattr(translator, 'load_live_weather', unavailable)
    button(app, 'Refresh live weather').click().run()
    assert not app.exception
    assert app.error and not app.metric


def test_live_ui_investigates_current_snapshot(source,monkeypatch):
    from schemas.assessment import Assessment
    calls=[]
    def investigate(weather,station,progress):
        calls.append(weather)
        record=translator.live_weather_record(weather)
        return Assessment(anomaly_id=record.anomaly_id,summary='Current San Diego weather verified',confidence='moderate')
    monkeypatch.setattr(translator,'investigate_live_weather',investigate)
    app=AppTest.from_file(APP).run()
    app.radio[1].set_value('Coordinates').run()
    button(app,"Load today's weather").click().run()
    button(app,"Investigate today's weather with Grok").click().run()
    assert not app.exception
    assert len(calls)==1 and calls[0].current_time.date().isoformat()=='2026-10-24'
    assert any('Current San Diego' in item.value for item in app.subheader)
