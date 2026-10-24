"""Smoke tests: the Streamlit app must render and investigate without exceptions.

Owner: Person 3 (Product & Dashboard).
"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import translator

APP_PATH = str(Path(__file__).resolve().parent.parent / "app.py")

pytestmark = pytest.mark.usefixtures("stubbed_backend")


# Raises a generic runtime error to simulate a crashing workstream.
def _crash(*args, **kwargs):
    raise RuntimeError("boom")


# Checks the app renders in sample mode and the investigation button works.
def test_app_renders_and_investigates_in_sample_mode():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert app.title[0].value == "EarthWatch"
    app.button[0].click().run()
    assert not app.exception
    assert app.subheader


# Checks a crashing pipeline shows an error message instead of a stack trace.
def test_app_shows_error_when_pipeline_fails(stubbed_backend):
    stubbed_backend.setattr(translator.anomaly_detection, "detect_anomalies", _crash)
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert app.error


# Checks a crashing workflow shows an error message instead of a stack trace.
def test_app_shows_error_when_workflow_fails(stubbed_backend):
    stubbed_backend.setattr(translator.workflow, "run_investigation", _crash)
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.button[0].click().run()
    assert not app.exception
    assert app.error
