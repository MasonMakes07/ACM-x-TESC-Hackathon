"""Globe checks. Owner: Person 3 (Product & Dashboard)."""

import json
from datetime import date

import pytest

from dashboard.globe import GLOBE_JS, globe_data, unplotted_regions
from dashboard.maps import PERU_LOCATIONS
from schemas.anomaly import AnomalyRecord


# Builds an anomaly record for a region with overridable fields.
def _anomaly(region="Nino 1+2", **overrides) -> AnomalyRecord:
    fields = dict(
        anomaly_id="globe_001", variable="sea_surface_temperature_anomaly", region=region,
        observation_date=date(2023, 6, 1), value=2.8, unit="degC",
        baseline_period="1991-2020", source="Test source",
        detection_method="published_anomaly_index", status="detected",
    )
    return AnomalyRecord(**{**fields, **overrides})


# Checks the page script and textures are pinned and fully substituted.
def test_script_uses_pinned_assets():
    assert "globe.gl@2.46.2" in GLOBE_JS
    assert "three-globe@2.31.0" in GLOBE_JS
    assert "__SCRIPT__" not in GLOBE_JS and "__TEXTURES__" not in GLOBE_JS


# Checks markers are built only from the supplied anomalies and the Peru locations.
def test_markers_come_from_real_records():
    data = globe_data([_anomaly()], "Nino 1+2")
    labels = [point["label"] for point in data["points"]]
    assert "Nino 1+2  +2.8 degC" in labels
    assert all(name in labels for name in PERU_LOCATIONS)
    assert len(labels) == 1 + len(PERU_LOCATIONS)


# Checks only anomaly markers are clickable, and they carry the anomaly id.
def test_only_anomaly_markers_carry_an_id():
    data = globe_data([_anomaly()], "Nino 1+2")
    clickable = [point for point in data["points"] if point["anomaly_id"]]
    assert [point["anomaly_id"] for point in clickable] == ["globe_001"]


# Checks the selected region gets a pulsing ring and is the only highlighted outline.
def test_selected_region_is_highlighted():
    anomalies = [_anomaly("Nino 1+2"), _anomaly("Nino 3.4", anomaly_id="globe_002", status="monitoring")]
    data = globe_data(anomalies, "Nino 3.4")
    assert len(data["rings"]) == 1
    highlighted = [item["name"] for item in data["outlines"] if item["color"] == "#ff6b6b"]
    assert highlighted == ["Nino 3.4"]
    assert data["view"]["lng"] == pytest.approx(-145)
    assert data["view_key"] == "Nino 3.4"


# Checks an unknown region and an empty list still produce usable data.
def test_unknown_region_and_no_anomalies():
    data = globe_data([], "Atlantis")
    assert data["rings"] == []
    assert len(data["points"]) == len(PERU_LOCATIONS)


# Checks tooltip HTML is escaped so a hostile source string cannot inject markup.
def test_hostile_text_is_escaped():
    data = globe_data([_anomaly(source="<img src=x onerror=alert(1)>")], "Nino 1+2")
    assert "<img" not in json.dumps(data)


# Checks events in regions without registered coordinates are reported, not dropped.
def test_unplotted_regions_are_reported():
    anomalies = [_anomaly("Nino 1+2"), _anomaly("Mediterranean", anomaly_id="globe_003")]
    assert unplotted_regions(anomalies) == ["Mediterranean"]
    assert "Mediterranean" not in json.dumps(globe_data(anomalies, None))
