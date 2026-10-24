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
    assert app.title[0].value == "EarthWatch"
    app.button(key="run_investigation").click().run()
    assert not app.exception
    assert app.subheader


def test_app_shows_error_when_pipeline_fails(stubbed_backend):
    stubbed_backend.setattr(translator.anomaly_detection, 'detect_anomalies', _crash)
    app = pacific_app()
    assert not app.exception
    assert app.error


def test_app_shows_error_when_workflow_fails(stubbed_backend):
    stubbed_backend.setattr(translator.workflow, "run_investigation", _crash)
    app = pacific_app()
    app.button(key="run_investigation").click().run()
    assert not app.exception
    assert app.error


# Checks a crashing series source shows an error but the rest of the dashboard still renders.
def test_app_survives_series_failure(stubbed_backend):
    stubbed_backend.setattr(translator.climate_sources, "get_sst_series", _crash)
    app = pacific_app()
    assert not app.exception
    assert app.error
    assert len(app.tabs) == 4


# Checks the four dashboard sections exist in order.
def test_app_has_four_tabs():
    app = pacific_app()
    assert [tab.label for tab in app.tabs] == [
        "Overview", "Climate Explorer", "Investigation", "Regional Briefing",
    ]


# Checks the timeline and briefing fill in after an investigation and survive a rerun.
def test_investigation_results_persist_across_reruns():
    app = pacific_app()
    assert "No investigation run yet" in app.tabs[2].info[0].value
    app.button(key="run_investigation").click().run()
    app.run()
    assert not app.exception
    assert any("Sample mode" in item.label for item in app.tabs[2].expander)
    assert app.tabs[3].subheader[0].value.startswith("SAMPLE ASSESSMENT")


# Checks the region, replay and threshold controls can all change without errors.
def test_demo_controls_change_without_errors():
    app = pacific_app()
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
    app = pacific_app()
    app.button(key="run_investigation").click().run()
    app.sidebar.selectbox[0].set_value("Nino 3.4").run()
    assert "No investigation run yet" in app.tabs[2].info[0].value
    app.sidebar.selectbox[0].set_value("Nino 1+2").run()
    assert any("Sample mode" in item.label for item in app.tabs[2].expander)


# Checks the region selection key the globe sets switches the page to that region's event.
def test_globe_selection_opens_that_event():
    app = pacific_app()
    app.session_state["region_select"] = "Nino 3.4"
    app.run()
    assert not app.exception
    assert app.sidebar.selectbox[0].value == "Nino 3.4"
    assert any("Nino 3.4" in item.value for item in app.subheader)


# Checks the event panel lists the agents' sources after an investigation, labelled as sample.
def test_event_panel_shows_sources_after_investigation():
    app = pacific_app()
    assert any("No agent sources yet" in item.value for item in app.info)
    app.button(key="run_investigation").click().run()
    assert not app.exception
    assert any("SAMPLE sources" in item.value for item in app.warning)
    assert any("gave no link" in item.value for item in app.caption)
