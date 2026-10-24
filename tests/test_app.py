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
    return app.radio[0].set_value('Climate events globe').run()


# Opens the globe dashboard with automatic explanations off, for tests of the manual button flow.
def manual_app():
    app = AppTest.from_file(APP_PATH, default_timeout=30)
    app.session_state["auto_explain"] = False
    app.run()
    return app.radio[0].set_value('Climate events globe').run()


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
    app = manual_app()
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
    app = manual_app()
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
    app = manual_app()
    assert any("No agent sources yet" in item.value for item in app.info)
    app.button(key="run_investigation").click().run()
    assert not app.exception
    assert any("SAMPLE sources" in item.value for item in app.warning)
    assert any("gave no link" in item.value for item in app.caption)


# The guided demo restores empty filters and completes the existing backend workflow.
def test_guided_demo_recovers_empty_filters_and_investigates():
    app = pacific_app()
    app.sidebar.multiselect(key='region_filter').set_value([]).run()
    assert not app.exception
    assert any('No events match' in item.value for item in app.info)
    app.button(key='guided_demo').click().run()
    assert not app.exception
    assert app.session_state['results']
    assert any('Sample mode' in item.label for item in app.tabs[2].expander)


# Color previews are labeled and reach the real dashboard's event cards and briefing.
def test_severity_preview_is_wired_into_the_current_app():
    app = pacific_app()
    app.selectbox(key='sample_severity').select('red').run()
    assert not app.exception
    assert any('sample preview' in item.value for item in app.warning)
    assert any('Critical danger' in item.value for item in app.markdown)
    app.button(key='run_investigation').click().run()
    assert not app.exception
    assert any('Critical danger' in item.value for item in app.tabs[3].markdown)


# A heatwave event must not display an SST series under its temperature label.
def test_non_sst_event_does_not_call_sst_source(stubbed_backend):
    record = translator._load_sample_anomalies()[0].model_copy(update={
        'region': 'Europe', 'variable': 'heatwave_temperature_anomaly',
    })
    stubbed_backend.setattr(translator.anomaly_detection, 'detect_anomalies', lambda: [record])
    calls = []
    stubbed_backend.setattr(translator.climate_sources, 'get_sst_series', lambda region: calls.append(region))
    app = pacific_app()
    assert not app.exception
    assert calls == []
    assert any('Europe' in item.value for item in app.subheader)


# The real default view includes the integrated globe and both motion controls.
def test_default_view_is_the_globe_dashboard_with_globe_controls():
    app = AppTest.from_file(APP_PATH, default_timeout=30).run()
    assert not app.exception
    assert app.radio(key="monitoring_view").value == 'Climate events globe'
    assert any('Worldwide climate events' in item.value for item in app.caption)
    assert len(app.toggle) == 3


# Opening an event explains it automatically, without pressing Run Investigation.
def test_event_is_explained_automatically_when_opened():
    app = pacific_app()
    assert not app.exception
    assert any("Why is this happening?" in item.value for item in app.markdown)
    assert any("Sample mode" in item.label for item in app.tabs[2].expander)
    assert any("SAMPLE explanation" in item.value for item in app.warning)


# Turning the switch off means nothing runs until the button is pressed, and the page says so.
def test_auto_explain_off_waits_for_the_button():
    app = manual_app()
    assert not app.exception
    assert any("have not explained this event yet" in item.value for item in app.info)
    app.button(key="run_investigation").click().run()
    assert any("SAMPLE explanation" in item.value for item in app.warning)


# Each newly opened event is explained once; switching back reuses the saved explanation.
def test_auto_explain_runs_once_per_event(monkeypatch):
    calls = []
    original = translator.investigate_anomaly

    def counting(anomaly_id, on_progress):
        calls.append(anomaly_id)
        return original(anomaly_id, on_progress)

    monkeypatch.setattr(translator, "investigate_anomaly", counting)
    app = pacific_app()
    app.sidebar.selectbox[0].set_value("Nino 3.4").run()
    app.sidebar.selectbox[0].set_value("Nino 1+2").run()
    app.run()
    assert len(calls) == 2 and len(set(calls)) == 2


# A failed automatic explanation shows the reason and is not retried on every rerun.
def test_auto_explain_failure_is_shown_and_not_retried(stubbed_backend):
    calls = []

    def refuse(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("Missing XAI_API_KEY. Copy .env.example to .env and set it.")

    stubbed_backend.setattr(translator.workflow, "run_investigation", refuse)
    app = pacific_app()
    app.run()
    app.run()
    assert any("XAI_API_KEY" in item.value for item in app.error)
    assert len(calls) == 1
