"""Chart and map checks. Owner: Person 3 (Product & Dashboard)."""

from datetime import date

import pandas as pd
import pytest

from dashboard.charts import EMPTY_MESSAGE, observation_chart
from dashboard.maps import PERU_LOCATIONS, REGION_BOXES, region_map
from schemas.anomaly import AnomalyRecord


# A small monthly series spanning the sample anomaly date.
@pytest.fixture
def series():
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-04-01", "2023-05-01", "2023-06-01", "2023-07-01"]),
            "value": [0.5, 1.4, 2.8, float("nan")],
        }
    )


# An anomaly record dated inside the fixture series.
@pytest.fixture
def anomaly():
    return AnomalyRecord(
        anomaly_id="test_001", variable="sea_surface_temperature_anomaly",
        region="Nino 1+2", observation_date=date(2023, 6, 1), value=2.8, unit="degC",
        baseline_period="1991-2020", source="Test source",
        detection_method="published_anomaly_index", status="detected",
    )


# Returns the trace named "Detected anomaly" if the figure has one.
def _anomaly_traces(figure):
    return [trace for trace in figure.data if trace.name == "Detected anomaly"]


# Checks the original three-argument call still works.
def test_backward_compatible_call(series):
    figure = observation_chart(series, "SST", "degC")
    assert len(figure.data) == 1
    assert figure.layout.title.text == "SST"


# Checks replay_until drops observations after the replay date.
def test_replay_until_removes_later_points(series):
    figure = observation_chart(series, "SST", "degC", replay_until=date(2023, 5, 1))
    assert len(figure.data[0].x) == 2


# Checks the anomaly marker and its source hover appear when the date is plotted.
def test_anomaly_marker_in_range(series, anomaly):
    figure = observation_chart(series, "SST", "degC", anomaly=anomaly)
    markers = _anomaly_traces(figure)
    assert len(markers) == 1
    assert "Source: Test source" in markers[0].hovertemplate
    assert "Source: Test source" in figure.data[0].hovertemplate


# Checks the anomaly marker is skipped when replay hides its date.
def test_anomaly_marker_out_of_range(series, anomaly):
    figure = observation_chart(
        series, "SST", "degC", anomaly=anomaly, replay_until=date(2023, 5, 1)
    )
    assert not _anomaly_traces(figure)


# Checks a threshold adds exactly two extra horizontal lines.
def test_threshold_adds_two_lines(series):
    without = observation_chart(series, "SST", "degC")
    with_threshold = observation_chart(series, "SST", "degC", threshold=1.0)
    assert len(with_threshold.layout.shapes) - len(without.layout.shapes) == 2


# Checks empty input, and replay before the first point, give the empty-state message.
@pytest.mark.parametrize("replay_until", [None, date(2000, 1, 1)])
def test_empty_series_shows_message(series, replay_until):
    source = series if replay_until else series.iloc[0:0]
    figure = observation_chart(source, "SST", "degC", replay_until=replay_until)
    assert figure.layout.annotations[0].text == EMPTY_MESSAGE


# Checks the selected region is the only filled box and every location is labelled.
def test_region_map_highlights_selected():
    figure = region_map("Nino 1+2")
    fills = {trace.name: trace.fill for trace in figure.data if trace.name in REGION_BOXES}
    assert fills == {"Nino 1+2": "toself", "Nino 3.4": "none"}
    labels = [trace for trace in figure.data if trace.name == "Northern Peru"][0].text
    assert list(labels) == list(PERU_LOCATIONS)


# Checks an unknown or missing region draws every box dim without raising.
@pytest.mark.parametrize("region", [None, "Atlantis"])
def test_region_map_unknown_region(region):
    figure = region_map(region)
    assert all(trace.fill == "none" for trace in figure.data if trace.name in REGION_BOXES)
