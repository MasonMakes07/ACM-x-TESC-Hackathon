"""Globe checks. Owner: Person 3 (Product & Dashboard)."""

import json
import re
from datetime import date

import pytest

from dashboard.globe import globe_html
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


# Pulls the embedded DATA object back out of the generated page.
def _data(html: str) -> dict:
    return json.loads(re.search(r"const DATA = (.*?);\nif \(window", html, re.S).group(1))


# Checks the page pins its script and textures and has no leftover placeholders.
def test_page_uses_pinned_assets_and_no_placeholders():
    html = globe_html([_anomaly()], "Nino 1+2")
    assert "globe.gl@2.46.2" in html
    assert "three-globe@2.31.0" in html
    for placeholder in ("__SCRIPT__", "__TEXTURES__", "__DATA__"):
        assert placeholder not in html


# Checks markers are built only from the supplied anomalies and the Peru locations.
def test_markers_come_from_real_records():
    data = _data(globe_html([_anomaly()], "Nino 1+2"))
    labels = [point["label"] for point in data["points"]]
    assert "Nino 1+2  +2.8 degC" in labels
    assert all(name in labels for name in PERU_LOCATIONS)
    assert len(labels) == 1 + len(PERU_LOCATIONS)


# Checks the selected region gets a pulsing ring and is the only highlighted outline.
def test_selected_region_is_highlighted():
    anomalies = [_anomaly("Nino 1+2"), _anomaly("Nino 3.4", anomaly_id="globe_002", status="monitoring")]
    data = _data(globe_html(anomalies, "Nino 3.4"))
    assert len(data["rings"]) == 1
    highlighted = [item["name"] for item in data["outlines"] if item["color"] == "#ff6b6b"]
    assert highlighted == ["Nino 3.4"]
    assert data["view"]["lng"] == pytest.approx(-145)


# Checks an unknown region and an empty list still produce a usable page.
def test_unknown_region_and_no_anomalies():
    data = _data(globe_html([], "Atlantis"))
    assert data["rings"] == []
    assert len(data["points"]) == len(PERU_LOCATIONS)


# Checks hostile text in a record cannot break out of the script tag or the tooltip HTML.
def test_hostile_text_is_escaped():
    html = globe_html([_anomaly(source="</script><img src=x onerror=alert(1)>")], "Nino 1+2")
    assert html.count("</script>") == 2
    assert "<img" not in html


# Checks events in regions without registered coordinates are reported, not silently dropped.
def test_unplotted_regions_are_reported():
    from dashboard.globe import unplotted_regions

    anomalies = [_anomaly("Nino 1+2"), _anomaly("Mediterranean", anomaly_id="globe_003")]
    assert unplotted_regions(anomalies) == ["Mediterranean"]
    assert "Mediterranean" not in globe_html(anomalies, None)
