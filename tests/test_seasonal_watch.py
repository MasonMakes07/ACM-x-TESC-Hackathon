"""Seasonal provenance, forecast integrity, bot checks, and watchlist UI behavior."""
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from agents.agent_errors import AgentOutputError
from agents.seasonal_watch import assess_seasonal, validate_review
from data import seasonal
from data.locations import Location
from schemas.errors import TranslatorError
from schemas.watchlist import HAZARDS, HazardOutlook, MonthlySignal, SeasonalReview
import translator

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


@pytest.fixture
def snapshot():
    months = seasonal.outlook_months(datetime.now(timezone.utc).date(), 3)
    return seasonal.SeasonalSnapshot(
        Location('Test area', 24, 90),
        [MonthlySignal(month=month, temperature_anomaly=1.5, precipitation_anomaly=-25,
                       soil_moisture_anomaly=-0.02, runoff_anomaly=-5) for month in months],
        datetime.now(timezone.utc), 'https://seasonal-api.open-meteo.com/v1/seasonal?latitude=24',
        months[0], months[-1].replace(day=28),
    )


def review_for(snapshot):
    refs = list(snapshot.evidence())[:4]
    return SeasonalReview(summary='Seasonal warm and dry signals deserve monitoring.', outlooks=[
        HazardOutlook(hazard=hazard, level='Elevated watch' if hazard == 'Drought' else 'Monitor',
                      confidence='low', summary='Seasonal potential, not a confirmed event.',
                      rationale='Monthly ensemble-mean indicators support monitoring only.',
                      evidence_refs=refs, limitations=['Uncalibrated seasonal indicators cannot establish event occurrence.'],
                      monitoring_triggers=['Check local authority updates and shorter-range forecasts.'])
        for hazard in HAZARDS
    ])


def test_full_calendar_month_window_rolls_over_year():
    assert seasonal.outlook_months(date(2026, 11, 24), 3) == [date(2026,12,1), date(2027,1,1), date(2027,2,1)]
    assert seasonal.outlook_months(date(2026, 12, 31), 1) == [date(2027,1,1)]
    with pytest.raises(ValueError):
        seasonal.outlook_months(date(2026,1,1), 4)


@pytest.fixture
def source_payload(snapshot):
    fields = list(seasonal.FIELDS)
    return dict(latitude=24.1, longitude=90,
                monthly_units={field: seasonal.FIELDS[field][1] for field in fields},
                monthly={'time': [item.month.isoformat() for item in snapshot.signals],
                         **{field: [item.model_dump()[seasonal.FIELDS[field][0]] for item in snapshot.signals] for field in fields}})


def test_real_seasonal_contract_preserves_units_anomalies_and_source(snapshot, source_payload, monkeypatch):
    captured = {}
    def fetch(url, params, **kwargs):
        captured.update(params=params, options=kwargs)
        return json.dumps(source_payload), datetime.now(timezone.utc).isoformat(), False
    monkeypatch.setattr(seasonal, 'fetch_text', fetch)
    result = seasonal.load_seasonal(snapshot.location)
    assert result.signals[0].precipitation_anomaly == -25
    assert captured['options']['allow_stale'] is False
    assert captured['params']['models'] == 'ecmwf_seas5_ensemble_mean'
    assert result.window_start > datetime.now(timezone.utc).date()
    assert 'monthly=' in result.source_url


@pytest.mark.parametrize('fault', ['units', 'wrong_area', 'missing_month', 'duplicate', 'nan', 'no_data', 'stale', 'old'])
def test_seasonal_source_rejects_unusable_forecasts(snapshot, source_payload, monkeypatch, fault):
    if fault == 'units':
        source_payload['monthly_units']['temperature_2m_anomaly'] = '°F'
    if fault == 'wrong_area':
        source_payload['latitude'] = -30
    if fault == 'missing_month':
        source_payload['monthly']['time'][0] = '2020-01-01'
    if fault == 'duplicate':
        source_payload['monthly']['time'][1] = source_payload['monthly']['time'][0]
    if fault == 'nan':
        source_payload['monthly']['temperature_2m_anomaly'][0] = float('nan')
    if fault == 'no_data':
        for field in seasonal.FIELDS:
            source_payload['monthly'][field] = [None] * 3
    stamp = datetime.now(timezone.utc) - timedelta(days=2 if fault == 'old' else 0)
    monkeypatch.setattr(seasonal, 'fetch_text', lambda *args, **kwargs: (json.dumps(source_payload), stamp.isoformat(), fault == 'stale'))
    with pytest.raises(ValueError):
        seasonal.load_seasonal(snapshot.location)


def test_three_grok_bots_use_the_same_retrieved_evidence(snapshot):
    class Client:
        def __init__(self): self.messages = []
        def chat(self, messages, tools=None):
            self.messages.append(messages)
            return {'content': review_for(snapshot).model_dump_json()}
    client = Client()
    events = []
    result = assess_seasonal(snapshot, events.append, client=client)
    assert len(client.messages) == 3
    assert result.location_key == snapshot.location.key
    assert result.signals == snapshot.signals
    assert {event.agent for event in events} == {'Seasonal Scout', 'Impact Analyst', 'Seasonal Skeptic'}
    assert all('precipitation_anomaly' in messages[1]['content'] for messages in client.messages)


def test_model_cannot_invent_evidence_or_raise_unsupported_flood_watch(snapshot):
    review = review_for(snapshot)
    bad = review.outlooks[0].model_copy(update={'evidence_refs': ['invented_source']})
    with pytest.raises(AgentOutputError, match='not retrieved'):
        validate_review(review.model_copy(update={'outlooks': [bad, *review.outlooks[1:]]}), snapshot)
    flood = review.outlooks[0].model_copy(update={'level': 'Elevated watch'})
    with pytest.raises(AgentOutputError, match='contradicts'):
        validate_review(review.model_copy(update={'outlooks': [flood, *review.outlooks[1:]]}), snapshot)


def test_missing_hazard_indicators_are_inconclusive(snapshot):
    missing = seasonal.SeasonalSnapshot(snapshot.location,
        [item.model_copy(update={'soil_moisture_anomaly': None}) for item in snapshot.signals],
        snapshot.retrieved_at, snapshot.source_url, snapshot.window_start, snapshot.window_end)
    review = review_for(snapshot)
    safe = [item.model_copy(update={'evidence_refs': [ref for ref in item.evidence_refs if 'soil_moisture' not in ref]}) for item in review.outlooks]
    checked = validate_review(review.model_copy(update={'outlooks': safe}), missing)
    assert next(item for item in checked.outlooks if item.hazard == 'Drought').level == 'Inconclusive'
    assert next(item for item in checked.outlooks if item.hazard == 'Wildfire conditions').confidence == 'inconclusive'


def test_schema_requires_all_hazards_and_disallows_invented_probabilities(snapshot):
    review = review_for(snapshot).model_dump()
    review['outlooks'][0]['probability'] = 0.9
    with pytest.raises(ValueError):
        SeasonalReview.model_validate(review)
    with pytest.raises(ValueError):
        SeasonalReview(summary='Missing hazards', outlooks=[review_for(snapshot).outlooks[0]] * 5)


def test_partial_indicator_coverage_caps_confidence(snapshot):
    partial = seasonal.SeasonalSnapshot(snapshot.location,
        [snapshot.signals[0], snapshot.signals[1].model_copy(update={'soil_moisture_anomaly': None}), snapshot.signals[2]],
        snapshot.retrieved_at, snapshot.source_url, snapshot.window_start, snapshot.window_end)
    review = review_for(snapshot)
    items = [item.model_copy(update={'confidence': 'moderate'}) for item in review.outlooks]
    checked = validate_review(review.model_copy(update={'outlooks': items}), partial)
    drought = next(item for item in checked.outlooks if item.hazard == 'Drought')
    assert drought.confidence == 'low'
    assert any('incomplete' in note for note in drought.limitations)


def test_translator_rejects_cross_area_or_modified_forecasts(snapshot, monkeypatch):
    from agents import seasonal_watch
    result = assess_seasonal(snapshot, lambda event: None,
        client=type('Client', (), {'chat': lambda self, *args, **kwargs: {'content': review_for(snapshot).model_dump_json()}})())
    monkeypatch.setattr(seasonal, 'load_seasonal', lambda *args: snapshot)
    monkeypatch.setattr(seasonal_watch, 'assess_seasonal', lambda *args: result.model_copy(update={'location_key': 'different_area'}))
    with pytest.raises(TranslatorError, match='did not match'):
        translator.scan_seasonal_area(snapshot.location, 3, lambda event: None)


def test_watchlist_default_never_scans_automatically(monkeypatch):
    calls = []
    monkeypatch.setattr(translator, 'scan_seasonal_area', lambda *args: calls.append(args))
    monkeypatch.setattr(translator, 'seasonal_agent_ready', lambda: False)
    app = AppTest.from_file(APP).run()
    app.radio(key='monitoring_view').set_value('Global risk watchlist').run()
    assert not app.exception
    assert app.button(key='scan_watchlist').disabled
    assert len(app.session_state['watch_areas']) == 8
    assert not app.session_state['watch_results']
    assert calls == []


def test_watchlist_scans_retains_results_and_exposes_failed_refresh(snapshot, monkeypatch):
    result = assess_seasonal(snapshot, lambda event: None,
        client=type('Client', (), {'chat': lambda self, *args, **kwargs: {'content': review_for(snapshot).model_dump_json()}})())
    monkeypatch.setattr(translator, 'seasonal_agent_ready', lambda: True)
    monkeypatch.setattr(translator, 'scan_seasonal_area', lambda place, *args: result.model_copy(update={
        'location_key': place.key, 'location_label': place.label,
        'latitude': place.latitude, 'longitude': place.longitude,
    }))
    app = AppTest.from_file(APP).run()
    app.radio(key='monitoring_view').set_value('Global risk watchlist').run()
    first = next(iter(app.session_state['watch_areas']))
    app.multiselect(key='watch_scan_selection').set_value([first]).run()
    app.button(key='scan_watchlist').click().run()
    assert not app.exception
    assert len(app.session_state['watch_results']) == 1
    assert next(metric.value for metric in app.metric if metric.label == 'Current reviews') == '1'
    app.run()
    assert len(app.session_state['watch_results']) == 1
    def fail(*args): raise TranslatorError('Seasonal source unavailable')
    monkeypatch.setattr(translator, 'scan_seasonal_area', fail)
    app.button(key='scan_watchlist').click().run()
    assert not app.exception
    assert first in app.session_state['watch_failures']
    assert first in app.session_state['watch_results']
    assert any('Previous review' in item.value for item in app.warning)


def test_new_watched_point_does_not_inherit_another_area_results(monkeypatch):
    monkeypatch.setattr(translator, 'seasonal_agent_ready', lambda: True)
    app = AppTest.from_file(APP).run()
    app.radio(key='monitoring_view').set_value('Global risk watchlist').run()
    next(item for item in app.text_input if item.label == 'Area name').set_value('New island')
    next(item for item in app.number_input if item.label == 'Latitude').set_value(1.5)
    next(item for item in app.number_input if item.label == 'Longitude').set_value(120.0)
    next(item for item in app.button if item.label == 'Add to watchlist').click().run()
    assert not app.exception
    assert len(app.session_state['watch_areas']) == 9
    assert app.session_state['watch_results'] == {}
