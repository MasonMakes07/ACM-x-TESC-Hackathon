"""Worldwide search, coordinate ingestion, local baselines, and dashboard flow."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest
import translator
from data.locations import Location, countries, search_locations
from data.weather_sources import get_weather_history
from analysis.global_climate import analyze_location
from schemas.errors import TranslatorError

APP = str(Path(__file__).resolve().parent.parent / 'app.py')


@pytest.mark.parametrize('lat,lon', [(-90,-180), (90,180), (0,0), (-33.9,151.2), (35.7,139.7)])
def test_coordinates_worldwide(lat, lon):
    assert Location('Anywhere', lat, lon).latitude == lat


@pytest.mark.parametrize('lat,lon', [(91,0), (-91,0), (0,181), (0,-181), (float('nan'),0), (0,float('inf'))])
def test_invalid_coordinates(lat, lon):
    with pytest.raises(ValueError):
        Location('Anywhere', lat, lon)


def test_country_picker_is_global():
    values = countries()
    assert len(values) >= 249
    assert len({item['code'] for item in values}) == len(values)
    assert {'US','PE','JP','KE','AU','AQ','BR','IN','GB','FJ','XK'} <= {item['code'] for item in values}


def test_geocoding_country_filter_disambiguation_and_unicode(monkeypatch):
    from data import locations
    captured = {}
    def fake(url, params, **kwargs):
        captured.update(params)
        return json.dumps({'results':[{'name':'Springfield', 'latitude':39.8, 'longitude':-89.6, 'country':'United States', 'country_code':'US', 'admin1':'Illinois'}, {'name':'Springfield','latitude':-27.6,'longitude':152.9,'country_code':'AU'}]}), '', False
    monkeypatch.setattr(locations, 'fetch_text', fake)
    hits = search_locations('Springfield', 'US')
    assert len(hits) == 1 and captured['countryCode'] == 'US'
    assert 'Illinois' in hits[0].label
    assert Location('S\u00e3o Paulo', -23.5, -46.6).key != Location('S\u00e3o Paulo', 1, 2).key
    assert Location('\u6771\u4eac\u90fd', 35.7, 139.7).label == '\u6771\u4eac\u90fd'


def payload():
    return {'latitude':35.75,'longitude':139.75,'timezone':'Asia/Tokyo','daily_units':{'temperature_2m_mean':'\u00b0C','precipitation_sum':'mm'}, 'daily':{'time':['2024-01-01','2024-01-02'], 'temperature_2m_mean':[10,None], 'precipitation_sum':[0,12]}}


def test_weather_request_uses_selected_location_and_timezone(monkeypatch):
    from data import weather_sources
    requested = {}
    def fake(url, params):
        requested.update(params)
        return json.dumps(payload()), '2025-01-01T00:00:00+00:00', False
    monkeypatch.setattr(weather_sources, 'fetch_text', fake)
    location = Location('Tokyo',35.7,139.7,timezone='Asia/Tokyo')
    frame = get_weather_history(location,'2024-01-01','2024-01-02')
    assert requested['latitude'] == 35.7 and requested['longitude'] == 139.7
    assert requested['timezone'] == 'Asia/Tokyo'
    assert requested['cell_selection'] == 'nearest'
    assert frame['temperature'].isna().sum() == 1
    assert set(frame['region']) == {'Tokyo'}
    assert frame['grid_latitude'].iloc[0] == 35.75


@pytest.mark.parametrize('fault', ['units','missing_date','negative','duplicate','infinite'])
def test_weather_invalid_responses(monkeypatch, fault):
    from data import weather_sources
    data = payload()
    if fault == 'units': data['daily_units']['precipitation_sum'] = 'inch'
    if fault == 'missing_date': data['daily']['time'][1] = '2024-01-03'
    if fault == 'negative': data['daily']['precipitation_sum'][0] = -1
    if fault == 'duplicate': data['daily']['time'][1] = '2024-01-01'
    if fault == 'infinite': data['daily']['temperature_2m_mean'][0] = float('inf')
    monkeypatch.setattr(weather_sources, 'fetch_text', lambda *a: (json.dumps(data), '', False))
    with pytest.raises(ValueError):
        get_weather_history(Location('Tokyo',35.7,139.7),'2024-01-01','2024-01-02')


def history(location, start_date, end_date):
    frame = pd.DataFrame({'date':pd.date_range(start_date,end_date)})
    years = frame['date'].dt.year
    frame['temperature'] = frame['date'].dt.month + (years % 5) + location.latitude / 10
    frame['precipitation'] = 1.0 + (years % 5) / 10
    frame.loc[years == 2024,'temperature'] += 20
    frame['region'], frame['source'] = location.label, 'https://archive-api.open-meteo.com/v1/archive'
    frame['retrieved_at'], frame['cache_stale'] = '2025-01-01T00:00:00+00:00', False
    return frame


@pytest.fixture
def global_data(monkeypatch):
    from analysis import global_climate
    monkeypatch.setattr(global_climate, 'get_weather_history', history)


def test_local_baselines_and_records(global_data):
    north = analyze_location(Location('\u6771\u4eac',35.7,139.7),2024)
    south = analyze_location(Location('Cape Town',-33.9,18.4),2024)
    assert len(north.anomalies) == 24
    assert north.baseline_period == '1994-2023'
    assert north.monthly['baseline_count'].eq(30).all()
    temp = north.monthly.query("variable == 'temperature'")
    assert temp['z_score'].gt(2).all()
    assert temp['anomaly'].gt(18).all()
    assert not north.monthly['baseline_mean'].equals(south.monthly['baseline_mean'])
    assert {a.anomaly_id for a in north.anomalies}.isdisjoint({a.anomaly_id for a in south.anomalies})
    assert all('\u6771\u4eac' in a.region for a in north.anomalies)


def test_missing_day_invalidates_month(monkeypatch):
    from analysis import global_climate
    def missing(*args):
        frame = history(*args)
        frame.loc[frame['date'] == '2024-01-10', 'temperature'] = np.nan
        return frame
    monkeypatch.setattr(global_climate, 'get_weather_history', missing)
    result = analyze_location(Location('Remote',0,0),2024)
    assert result.monthly.iloc[0]['value'] is np.nan or pd.isna(result.monthly.iloc[0]['value'])
    assert len(result.anomalies) == 23


def test_global_investigation_never_returns_peru_sample(global_data, monkeypatch):
    def stub(*a): raise NotImplementedError
    monkeypatch.setattr(translator.workflow,'run_investigation',stub)
    climate = analyze_location(Location('Nairobi',-1.3,36.8,country='Kenya'),2024)
    report, statistical = translator.investigate_location(climate,climate.anomalies[0].anomaly_id,lambda event:None)
    assert statistical is True
    assert 'Nairobi' in report.summary
    assert 'Peru' not in report.model_dump_json()
    assert report.evidence[0].source_date.year == 2024
    with pytest.raises(TranslatorError):
        translator.investigate_location(climate,'unrelated',lambda event:None)


def button(app, label):
    return next(item for item in app.button if item.label == label)


def test_global_app_default_has_world_country_picker():
    app = AppTest.from_file(APP).run()
    assert not app.exception
    assert app.radio[0].value == 'Worldwide locations'
    assert len(app.selectbox[0].options) >= 250
    assert button(app, "Load today's weather").disabled


def historical_app():
    app = AppTest.from_file(APP).run()
    return app.radio[-1].set_value('Climate history').run()


def test_coordinate_ui_load_investigate_and_selection_change(global_data, monkeypatch):
    def stub(*a): raise NotImplementedError
    monkeypatch.setattr(translator.workflow, 'run_investigation', stub)
    app = historical_app()
    app.radio[1].set_value('Coordinates').run()
    app.text_input[0].set_value('Tokyo').run()
    app.number_input[0].set_value(35.7)
    app.number_input[1].set_value(139.7)
    app.number_input[2].set_value(2024).run()
    button(app,'Load climate data').click().run()
    assert not app.exception
    assert app.subheader[0].value == 'Tokyo'
    button(app,'Run Investigation').click().run()
    assert not app.exception
    assert any('Tokyo' in item.value for item in app.subheader)
    app.number_input[0].set_value(-1.3).run()
    assert not app.subheader  # Previous coordinates must not leak into a new selection.


def test_search_ui_country_and_place_flow(global_data, monkeypatch):
    captured = []
    def search(query, code):
        captured.append((query, code))
        return [Location('Nairobi',-1.3,36.8,'Kenya','KE')]
    monkeypatch.setattr(translator,'search_world_locations',search)
    app = historical_app()
    kenya = next(item for item in countries() if item['code'] == 'KE')
    app.selectbox[0].set_value(kenya)
    app.text_input[0].set_value('Nairobi').run()
    button(app,'Search locations').click().run()
    assert captured == [('Nairobi','KE')]
    app.number_input[0].set_value(2024).run()
    button(app,'Load climate data').click().run()
    assert not app.exception
    assert app.subheader[0].value == 'Nairobi, Kenya'


def test_current_year_uses_publication_buffer_and_incomplete_month(monkeypatch):
    from datetime import date
    from analysis import global_climate
    class Clock(date):
        @classmethod
        def today(cls): return cls(2026,10,24)
    monkeypatch.setattr(global_climate, 'date', Clock)
    captured = []
    def source(*args):
        captured.append(args)
        return history(*args)
    monkeypatch.setattr(global_climate,'get_weather_history',source)
    result = analyze_location(Location('Current monitoring',1,2),2026)
    assert captured[0][2] == '2026-10-17'
    assert result.daily['date'].max() == pd.Timestamp('2026-10-17')
    october = result.monthly.loc[result.monthly['date'] == '2026-10-01']
    assert october['value'].isna().all()
    assert result.baseline_period == '1996-2025'
    assert all(record.observation_date.month <= 9 for record in result.anomalies)
