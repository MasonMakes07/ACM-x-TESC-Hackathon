from datetime import datetime, timezone
import json

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from analysis.current_anomalies import compare_metric
from agents.weather_brief import explain
from schemas.weather_comparison import WeatherComparison


def snapshot():
    now=datetime.now(timezone.utc)
    rows=[datetime(year,now.month,now.day,hour=now.hour,tzinfo=timezone.utc) for year in range(1991,2021) for _ in range(10)]
    history=pd.DataFrame({'time':pd.to_datetime(rows),'day':[d.date() for d in rows], 'hour':now.hour,'temperature':20.,'wind':5.,'precipitation':0.})
    metrics=[compare_metric(key,value,now,history) for key,value in [('temperature',38.),('wind',5.),('precipitation',0.)]]
    return WeatherComparison(location_key='test',location_label='Test',latitude=32.,longitude=-117.,conditions_time=now,retrieved_at=now,timezone='UTC',current_source='https://example.com',baseline_source='https://example.com/history',baseline_retrieved_at=now,metrics=metrics)


def test_screening_and_missing_baseline():
    result=snapshot()
    assert result.metrics[0].unusual
    assert not result.metrics[1].unusual
    assert result.evidence()['temperature.difference_fahrenheit']==32.4
    missing=compare_metric('temperature',38.,result.conditions_time,None)
    assert missing.historical_mean is None and not missing.unusual


def test_grok_rejects_invented_evidence():
    class Client:
        def chat(self,messages):
            return {'content':json.dumps(dict(summary='Warm',possible_causes=[dict(hypothesis='Possible circulation',evidence_refs=['invented'],what_to_check='Pressure')],actions=[dict(action_id='cool',why_it_helps='Reduces exposure')],limitations=['No attribution']))}
    with pytest.raises(ValueError,match='unsupported evidence'):
        explain(snapshot(),Client())


def test_default_view_and_snapshot_selection():
    from dashboard.weather_anomalies import DEFAULTS
    at=AppTest.from_file(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app.py').run()
    assert not at.exception
    at.sidebar.radio[0].set_value('Weather anomalies').run()
    assert at.sidebar.radio[0].value=='Weather anomalies'
    result=snapshot().model_copy(update={'location_key':DEFAULTS[0].key})
    at.session_state['weather_snapshots']={DEFAULTS[0].key:result}
    at.run()
    assert not at.exception
    assert any(m.label=='Historical mean' for m in at.metric)
    at.selectbox(key='weather_selected').set_value(DEFAULTS[1].key).run()
    assert not at.exception
    assert any('Scan this location' in i.value for i in at.info)


def test_san_diego_shows_reported_heat_anomaly_without_a_scan():
    from dashboard.weather_anomalies import DEFAULTS, REPORTED_COLOR, reported_event
    assert reported_event(DEFAULTS[0]) is not None and reported_event(DEFAULTS[1]) is None
    at=AppTest.from_file(__import__('pathlib').Path(__file__).resolve().parents[1] / 'app.py').run()
    at.sidebar.radio[0].set_value('Weather anomalies').run()
    assert not at.exception
    assert any('Reported weather anomaly' in str(item.proto.title) for item in at.error)
    assert any('ridge of high pressure' in item.value for item in at.markdown)
    assert any('105°F' in item.value for item in at.markdown)
    at.selectbox(key='weather_selected').set_value(DEFAULTS[1].key).run()
    assert not at.exception and not at.error
    assert REPORTED_COLOR.startswith('#')
