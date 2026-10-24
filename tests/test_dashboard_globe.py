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
    assert data["rings"] == []  # Selection does not imply risk severity.
    highlighted = [item["name"] for item in data["outlines"] if item["color"] == "#8ddcf0"]
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


# Explicit severity determines ring color; an unassessed event never defaults to danger or benefit.
@pytest.mark.parametrize('level,color', [('red', '#FF767C'), ('orange', '#FFB16A'), ('yellow', '#F6DB72'), ('green', '#79DFB5')])
def test_globe_uses_explicit_severity(level: str, color: str) -> None:
    record = _anomaly()
    data = globe_data([record], None, severity_by_anomaly={record.anomaly_id: level})
    assert data['rings'][0]['color'] == color
    assert data['points'][0]['color'] == color
    assert globe_data([record], None)['points'][0]['severity'] == 'unknown'


# Country and city feeds can be mapped worldwide without a Niño-only registry.
def test_globe_accepts_worldwide_coordinates() -> None:
    record = _anomaly('Tokyo', variable='heatwave_temperature_anomaly')
    data = globe_data([record], 'Tokyo', region_locations={'Tokyo': (35.68, 139.69)})
    assert data['points'][0]['lat'] == 35.68
    assert data['points'][0]['lng'] == 139.69
    assert unplotted_regions([record], {'Tokyo': (35.68, 139.69)}) == []


# Two distinct hazard types in the same region retain separate source IDs and click targets.
def test_globe_keeps_multiple_hazard_types() -> None:
    heat = _anomaly('Europe', variable='temperature_anomaly')
    rain = _anomaly('Europe', anomaly_id='rain_001', variable='precipitation_anomaly', unit='mm')
    data = globe_data([heat, rain], 'Europe')
    assert {item['anomaly_id'] for item in data['points'] if item['anomaly_id']} == {'globe_001', 'rain_001'}
