"""The restored tutorial is available in every view without starting paid workflows."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / 'app.py')
pytestmark = pytest.mark.usefixtures('stubbed_backend')


@pytest.mark.parametrize('view', ['Weather anomalies', 'Global risk watchlist', 'Worldwide locations', 'Pacific ocean indices'])
def test_tutorial_can_start_and_restart_in_each_view(view):
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state['auto_explain'] = False
    app.run()
    app.radio(key='monitoring_view').set_value(view).run()
    app.button(key='start_tutorial').click().run()
    assert not app.exception
    assert app.session_state['tutorial_run'] == 1
    assert 'results' not in app.session_state or not app.session_state['results']
    app.button(key='start_tutorial').click().run()
    assert not app.exception
    assert app.session_state['tutorial_run'] == 2


def test_tutorial_keeps_empty_filters_and_remains_available():
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state['auto_explain'] = False
    app.run()
    app.radio(key='monitoring_view').set_value('Pacific ocean indices').run()
    app.multiselect(key='region_filter').set_value([]).run()
    app.button(key='start_tutorial').click().run()
    assert not app.exception
    assert app.multiselect(key='region_filter').value == []
    assert 'results' not in app.session_state or not app.session_state['results']
