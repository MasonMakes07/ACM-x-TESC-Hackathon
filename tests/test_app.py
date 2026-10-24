"""Dashboard smoke tests for the Pacific view (worldwide tests are separate)."""
from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest
import translator

APP_PATH = str(Path(__file__).resolve().parent.parent / 'app.py')
pytestmark = pytest.mark.usefixtures('stubbed_backend')


def _crash(*args, **kwargs):
    raise RuntimeError('boom')


def pacific_app():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    return app.radio[0].set_value('Pacific ocean indices').run()


def test_app_renders_and_investigates_in_sample_mode():
    app = pacific_app()
    assert not app.exception
    assert app.title[0].value == 'EarthWatch'
    app.button[0].click().run()
    assert not app.exception
    assert app.subheader


def test_app_shows_error_when_pipeline_fails(stubbed_backend):
    stubbed_backend.setattr(translator.anomaly_detection, 'detect_anomalies', _crash)
    app = pacific_app()
    assert not app.exception
    assert app.error


def test_app_shows_error_when_workflow_fails(stubbed_backend):
    stubbed_backend.setattr(translator.workflow, 'run_investigation', _crash)
    app = pacific_app()
    app.button[0].click().run()
    assert not app.exception
    assert app.error
