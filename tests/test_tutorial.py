"""The tutorial is available without triggering the investigation workflow."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
pytestmark = pytest.mark.usefixtures("stubbed_backend")


# Starting the tour never runs an investigation (automatic explaining is off here to isolate that).
def test_tutorial_starts_and_restarts_without_running_an_investigation():
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["auto_explain"] = False
    app.run()
    region = app.selectbox(key="region_select").value
    filters = app.multiselect(key="region_filter").value
    app.button(key="start_tutorial").click().run()
    assert not app.exception
    assert app.session_state["tutorial_run"] == 1
    assert app.session_state["results"] == {}
    assert app.selectbox(key="region_select").value == region
    assert app.multiselect(key="region_filter").value == filters
    app.button(key="start_tutorial").click().run()
    assert not app.exception
    assert app.session_state["tutorial_run"] == 2


# The tour button works with empty filters and in the worldwide view.
def test_tutorial_available_with_empty_filters_and_in_worldwide_view():
    app = AppTest.from_file(APP, default_timeout=30).run()
    app.multiselect(key="region_filter").set_value([]).run()
    app.button(key="start_tutorial").click().run()
    assert not app.exception
    assert app.multiselect(key="region_filter").value == []
    app.radio(key="monitoring_view").set_value("Worldwide locations").run()
    app.button(key="start_tutorial").click().run()
    assert not app.exception
    assert app.session_state["tutorial_run"] == 2
    assert "world_climate" not in app.session_state


# The globe tour names coastal events and the explanation, not only El Nino.
def test_globe_tour_covers_coastal_events_and_explanations():
    from dashboard.tutorial_overlay import COMMON, GLOBE

    text = " ".join(item["title"] + " " + item["text"] for item in COMMON + GLOBE)
    assert "San Diego" in text and "tide" in text
    assert any(item["heading"] == "Why is this happening?" for item in GLOBE)
    assert any(item["label"] == "Explain events automatically" for item in GLOBE)
    assert not any(item["button"] == "Search anywhere on Earth" for item in GLOBE)
