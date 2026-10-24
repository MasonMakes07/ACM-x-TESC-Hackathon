"""Clickable heat reports, source integrity, and Grok evidence boundaries."""
from pathlib import Path
import json

import pytest
from streamlit.testing.v1 import AppTest

from data import san_diego_heat as heat
from dashboard.global_hazards import build_globe_data
from agents.heat_report import review_heat_report
from agents.agent_errors import AgentOutputError

APP = str(Path(__file__).resolve().parents[1] / 'app.py')


def test_heat_report_opens_from_featured_button_without_noaa_or_grok():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.button(key='open_san_diego_heat').click().run()
    assert not app.exception
    assert app.selectbox(key='global_hazard_selected').value == heat.EVENT_ID
    assert any(item.value == heat.TITLE for item in app.subheader)
    assert any('925' in item.value and 'all-cause' in item.value for item in app.markdown)
    assert any('El Niño alone caused' in item.value for item in app.markdown)
    assert any(item.label == 'Download San Diego report' for item in app.get('download_button'))
    app.run()
    assert app.selectbox(key='global_hazard_selected').value == heat.EVENT_ID


def test_heat_report_opens_via_globe_trigger_and_stops_rotation():
    # AppTest cannot click WebGL; execute the actual registered callback against its state.
    def callback_script():
        import streamlit as st
        from dashboard.global_hazards import select_event_from_globe
        from data.san_diego_heat import EVENT_ID
        st.session_state['global_hazard_visible_ids'] = [EVENT_ID]
        st.session_state['global_hazard_globe'] = {'selected': EVENT_ID}
        select_event_from_globe()
        st.write(st.session_state['global_hazard_selected'])
    clicked = AppTest.from_function(callback_script).run()
    assert not clicked.exception
    assert clicked.markdown[0].value == heat.EVENT_ID
    data = build_globe_data([], heat.EVENT_ID, {})
    assert not data['rotate']
    assert data['view']['lng'] == heat.LONGITUDE
    assert data['points'][0]['anomaly_id'] == heat.EVENT_ID


def test_report_filter_and_featured_button_restore_selection():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.multiselect(key='global_hazard_types').set_value([]).run()
    assert not app.exception
    app.button(key='open_san_diego_heat').click().run()
    assert not app.exception
    assert app.selectbox(key='global_hazard_selected').value == heat.EVENT_ID


def test_report_distinguishes_impacts_and_limits_attribution():
    report = heat.report_markdown()
    assert 'all-cause totals' in report
    assert 'year-to-date figure' in report
    assert 'does not claim that El Niño alone caused' in report
    for finding in heat.FINDINGS:
        assert finding['refs']
        assert set(finding['refs']) <= set(heat.SOURCES)


def test_grok_heat_report_rejects_unknown_sources():
    class Client:
        def chat(self, messages, tools=None):
            section = dict(text='Unsupported', evidence_refs=['invented-source'])
            return {'content': json.dumps({name: section for name in ('summary','damage','causes','el_nino_connection','limitations')})}
    with pytest.raises(AgentOutputError, match='unknown source'):
        review_heat_report(lambda name: None, client=Client())


def test_noaa_winding_is_corrected_for_display_without_changing_source():
    from dashboard.global_hazards import display_geometry
    from schemas.global_hazards import HazardGeometry
    outer = [(-118., 32.), (-116., 32.), (-116., 34.), (-118., 34.), (-118., 32.)]
    hole = [(-117.8, 32.2), (-117.8, 32.4), (-117.6, 32.4), (-117.6, 32.2), (-117.8, 32.2)]
    geometry = HazardGeometry(coordinates=[[outer, hole]])
    shown = display_geometry(geometry)['coordinates'][0]
    signed = lambda ring: sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(ring,ring[1:]))
    assert signed(shown[0]) < 0
    assert signed(shown[1]) > 0
    assert geometry.coordinates[0][0] == outer
    assert geometry.coordinates[0][1] == hole
