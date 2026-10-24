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


# Checks a crashing series source shows an error but the rest of the dashboard still renders.
def test_app_survives_series_failure(stubbed_backend):
    stubbed_backend.setattr(translator.climate_sources, "get_sst_series", _crash)
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert app.error
    assert len(app.tabs) == 4


# Checks the four dashboard sections exist in order.
def test_app_has_four_tabs():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert [tab.label for tab in app.tabs] == [
        "Overview", "Climate Explorer", "Investigation", "Regional Briefing",
    ]


# Checks the timeline and briefing fill in after an investigation and survive a rerun.
def test_investigation_results_persist_across_reruns():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert "No investigation run yet" in app.tabs[2].info[0].value
    app.button[0].click().run()
    app.run()
    assert not app.exception
    assert any("Sample mode" in item.label for item in app.tabs[2].expander)
    assert app.tabs[3].subheader[0].value.startswith("SAMPLE ASSESSMENT")


# Checks the region, replay and threshold controls can all change without errors.
def test_demo_controls_change_without_errors():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.sidebar.selectbox[0].set_value("Nino 3.4").run()
    assert not app.exception
    assert "Nino 3.4" in app.sidebar.selectbox[1].value.region
    replay = app.sidebar.select_slider[0]
    replay.set_value(replay.options[0]).run()
    app.sidebar.slider[0].set_value(2.0).run()
    assert not app.exception
    assert any("Move the slider" in caption.value for caption in app.tabs[1].caption)


# Checks results are kept per anomaly: a different anomaly starts with an empty timeline.
def test_results_are_kept_per_anomaly():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    app.button[0].click().run()
    app.sidebar.selectbox[0].set_value("Nino 3.4").run()
    assert "No investigation run yet" in app.tabs[2].info[0].value
    app.sidebar.selectbox[0].set_value("Nino 1+2").run()
    assert any("Sample mode" in item.label for item in app.tabs[2].expander)
