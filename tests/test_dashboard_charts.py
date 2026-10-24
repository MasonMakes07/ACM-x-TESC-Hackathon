"""Offline checks for the dashboard's chart and geographic views."""

from datetime import date

import pandas as pd
import pytest

from dashboard.charts import observation_chart
from dashboard.maps import PERU_LOCATIONS, REGION_BOXES, region_map
from schemas.anomaly import AnomalyRecord


# Creates a small dated series with a gap for chart tests.
def _series() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.to_datetime(["2023-01-01", "2023-02-01", "2023-03-01"]),
            "value": [0.5, float("nan"), 2.0],
        }
    )


# Creates an anomaly record for the final series observation.
def _anomaly() -> AnomalyRecord:
    return AnomalyRecord(
        anomaly_id="nino12_202303",
        variable="sea_surface_temperature_anomaly",
        region="Nino 1+2",
        observation_date=date(2023, 3, 1),
        value=2.0,
        unit="degC",
        baseline_period="1991-2020",
        source="NOAA CPC",
        detection_method="published_anomaly_index",
        status="detected",
    )


# Keeps the existing three-argument chart call usable.
def test_observation_chart_backward_compatible() -> None:
    figure = observation_chart(_series(), "SST anomalies", "degC")
    assert len(figure.data) == 1
    assert figure.data[0].y[0] == 0.5
    assert pd.isna(figure.data[0].y[1])
    assert figure.data[0].y[2] == 2.0
    assert figure.layout.paper_bgcolor == "rgba(0,0,0,0)"
    assert figure.layout.plot_bgcolor == "rgba(0,0,0,0)"


# Removes all dates later than the replay cutoff.
def test_observation_chart_replay_until() -> None:
    figure = observation_chart(_series(), "SST", "degC", replay_until=date(2023, 2, 1))
    assert len(figure.data[0].x) == 2
    assert max(pd.Timestamp(value).date() for value in figure.data[0].x) == date(2023, 2, 1)


# Highlights a selected anomaly only when its observation is visible.
def test_observation_chart_anomaly_marker_in_and_out_of_range() -> None:
    anomaly = _anomaly()
    visible = observation_chart(_series(), "SST", "degC", anomaly=anomaly)
    assert [trace.name for trace in visible.data] == ["Observations", "Detected anomaly"]
    assert list(visible.data[1].y) == [anomaly.value]
    assert "2.00 degC" in visible.layout.annotations[-1].text
    assert "Source: NOAA CPC" in visible.data[0].hovertemplate

    hidden = observation_chart(
        _series(), "SST", "degC", anomaly=anomaly, replay_until=date(2023, 2, 1)
    )
    assert [trace.name for trace in hidden.data] == ["Observations"]


# Avoids marking a date with no underlying observation.
def test_observation_chart_skips_anomaly_without_observation() -> None:
    gap = _series().loc[[0, 2]].copy()
    anomaly = _anomaly().model_copy(update={"observation_date": date(2023, 2, 1)})
    figure = observation_chart(gap, "SST", "degC", anomaly=anomaly)
    assert [trace.name for trace in figure.data] == ["Observations"]


# Adds positive and negative threshold guides with labels.
def test_observation_chart_threshold() -> None:
    figure = observation_chart(_series(), "SST", "degC", threshold=1.5)
    assert {shape.y0 for shape in figure.layout.shapes} == {0, 1.5, -1.5}
    assert any("+1.5 degC" in item.text for item in figure.layout.annotations)
    assert any("−1.5 degC" in item.text for item in figure.layout.annotations)


# Explains empty and pre-observation replay periods without raising.
def test_observation_chart_empty_period() -> None:
    empty = pd.DataFrame({"date": pd.to_datetime([]), "value": pd.Series(dtype=float)})
    missing = pd.DataFrame({"date": pd.to_datetime(["2023-01-01"]), "value": [float("nan")]})
    for series, replay_until in (
        (empty, None),
        (missing, None),
        (_series(), date(2022, 12, 1)),
    ):
        figure = observation_chart(series, "SST", "degC", replay_until=replay_until)
        assert not figure.data
        assert figure.layout.annotations[0].text == "No observations in this period"
        assert figure.layout.annotations[0].xref == "paper"


# Shows a closed highlighted region alongside all Peru place markers.
def test_region_map_highlights_selected_region() -> None:
    figure = region_map("Nino 1+2")
    boxes = {trace.name: trace for trace in figure.data[:2]}
    assert set(boxes) == set(REGION_BOXES)
    assert boxes["Nino 1+2"].fill == "toself"
    assert boxes["Nino 3.4"].fill == "none"
    assert boxes["Nino 1+2"].lon[0] == boxes["Nino 1+2"].lon[-1]
    assert boxes["Nino 1+2"].lat[0] == boxes["Nino 1+2"].lat[-1]
    assert set(figure.data[-1].text) == set(PERU_LOCATIONS)


# Keeps a global viewport even when a Pacific region is selected.
@pytest.mark.parametrize("region", [None, "Nino 1+2", "Nino 3.4"])
def test_region_map_shows_the_whole_world(region: str | None) -> None:
    geo = region_map(region).layout.geo
    assert geo.scope == "world"
    assert geo.projection.type == "natural earth"
    assert tuple(geo.lataxis.range) == (-90, 90)
    assert tuple(geo.lonaxis.range) == (-180, 180)
    assert geo.showcountries


# Leaves all regions dim for a missing or unsupported selection.
@pytest.mark.parametrize("region", [None, "unknown"])
def test_region_map_unknown_region(region: str | None) -> None:
    figure = region_map(region)
    assert all(trace.fill == "none" for trace in figure.data[:2])
