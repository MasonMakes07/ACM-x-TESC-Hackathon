"""Component contract and rendering checks. Owner: Person 3 / Codex B."""

import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.components import confidence_color, evidence_badge
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment

SAMPLES = Path(__file__).resolve().parents[1] / "sample_data"


# Loads schema-validated samples without touching any backend or external service.
@pytest.fixture
def records() -> tuple[list[AnomalyRecord], Assessment]:
    anomalies = [AnomalyRecord.model_validate(item) for item in json.loads(
        (SAMPLES / "anomalies.json").read_text()
    )]
    assessment = Assessment.model_validate_json((SAMPLES / "assessment.json").read_text())
    return anomalies, assessment


# Exercises all public renderers through Streamlit's actual script runtime.
def _render_component(name: str, anomalies: "list[AnomalyRecord]", assessment: "Assessment") -> None:
    from datetime import datetime, timezone

    from dashboard import components
    from dashboard.theme import apply_theme
    from schemas.assessment import ProgressEvent

    apply_theme()
    if name == "status_strip":
        components.status_strip(anomalies, True)
    elif name == "anomaly_card":
        components.anomaly_card(anomalies[0], selected=True)
    elif name == "anomaly_detail":
        components.anomaly_detail(anomalies[0])
    elif name == "investigation_timeline":
        components.investigation_timeline([
            ProgressEvent(timestamp=datetime(2023, 6, 1, 12, 30, tzinfo=timezone.utc),
                          agent="Verifier", message="Checking source agreement.")
        ])
    elif name == "evidence_list":
        components.evidence_list(assessment.evidence)
    elif name == "briefing":
        components.briefing(assessment, anomalies[0])


# Collects visible text without relying on Streamlit's internal element ordering.
def _visible_text(app: AppTest) -> str:
    return "\n".join(str(element.value) for kind in (
        "text", "markdown", "caption", "subheader", "info", "error"
    ) for element in app.get(kind))


# Known confidence levels have readable colors and unknown values stay neutral.
@pytest.mark.parametrize("level", ["high", "moderate", "low", "inconclusive", "unknown"])
def test_confidence_color(level: str) -> None:
    assert confidence_color(level).startswith("#")
    assert len(confidence_color(level)) == 7
    assert confidence_color("unknown") == confidence_color("inconclusive")
    assert len({confidence_color(value) for value in ("high", "moderate", "low")}) == 3


# Every badge includes meaningful text as well as a symbol.
@pytest.mark.parametrize("kind", ["measured", "reported", "inferred", "uncertain"])
def test_evidence_badge(kind: str) -> None:
    assert kind.capitalize() in evidence_badge(kind)
    assert evidence_badge("unknown") == "❔ Unclassified"


# Each renderer displays its essential content and works with the selected theme.
@pytest.mark.parametrize("name, expected", [
    ("status_strip", "Data as of 2023-06-01 (sample data)"),
    ("anomaly_card", "Selected signal"),
    ("anomaly_detail", "baseline mean are not supplied"),
    ("investigation_timeline", "Checking source agreement."),
    ("evidence_list", "SAMPLE DATA - not a real source"),
    ("briefing", "Potential regional implications"),
])
def test_component_renders(records: tuple[list[AnomalyRecord], Assessment], name: str, expected: str) -> None:
    anomalies, assessment = records
    app = AppTest.from_function(
        _render_component, args=(name, anomalies, assessment), default_timeout=15
    ).run()
    assert not app.exception
    assert expected in _visible_text(app)
    if name == "anomaly_detail":
        assert any("How to use EarthWatch" in item.label for item in app.expander)
    if name == "status_strip":
        assert [item.value for item in app.metric] == ["Signal detected", "Monitoring"]


# Exercises missing data, report mismatches, and evidence source validation.
def _render_edge_cases(anomaly: "AnomalyRecord", assessment: "Assessment") -> None:
    from dashboard.components import briefing, evidence_list, investigation_timeline, status_strip

    status_strip([], False)
    investigation_timeline([])
    evidence_list([])
    briefing(assessment.model_copy(update={"anomaly_id": "other_signal"}), anomaly)
    item = assessment.evidence[0]
    evidence_list([
        item.model_copy(update={"claim": "Uncertain claim", "evidence_type": "uncertain",
                                "source_date": None, "url": "javascript:alert(1)"}),
        item.model_copy(update={"claim": "Measured claim", "url": "https://example.org/evidence"}),
    ])


# Empty states stay informative, mismatched reports are blocked, and unsafe links are omitted.
def test_edge_cases(records: tuple[list[AnomalyRecord], Assessment]) -> None:
    anomalies, assessment = records
    app = AppTest.from_function(
        _render_edge_cases, args=(anomalies[0], assessment), default_timeout=15
    ).run()
    assert not app.exception
    text = _visible_text(app)
    assert "Monitoring status cannot be determined" in text
    assert "No investigation run yet" in text
    assert "No evidence supplied" in text
    assert "different signal" in text
    assert "Source date: undated" in text
    assert "Source link unavailable" in text
    assert "Measured claim" in app.expander[0].label
    assert "Uncertain claim" in app.expander[1].label
    assert len(app.get("link_button")) == 1


# Renders several claims citing one source, including exact repeated evidence.
def _render_shared_source(assessment: "Assessment") -> None:
    from dashboard.components import evidence_list

    item = assessment.evidence[0].model_copy(update={"url": "https://example.org/report"})
    evidence_list([item, item, item.model_copy(update={"claim": "Second claim from the report"})])


# Multiple claims from one report must not cause duplicate Streamlit element IDs.
def test_evidence_allows_repeated_source_links(records: tuple[list[AnomalyRecord], Assessment]) -> None:
    _, assessment = records
    app = AppTest.from_function(_render_shared_source, args=(assessment,)).run()
    assert not app.exception
    assert len(app.get("link_button")) == 3


# Renders a past detected signal followed by a newer monitoring observation.
def _render_regional_history(anomaly: "AnomalyRecord") -> None:
    from datetime import timedelta

    from dashboard.components import status_strip

    recent = anomaly.model_copy(update={
        "observation_date": anomaly.observation_date + timedelta(days=30),
        "status": "monitoring",
    })
    status_strip([anomaly, recent], False)


# Current status must correspond to the date shown rather than an older alert.
def test_status_uses_latest_regional_observation(records: tuple[list[AnomalyRecord], Assessment]) -> None:
    anomalies, _ = records
    app = AppTest.from_function(_render_regional_history, args=(anomalies[0],)).run()
    assert not app.exception
    assert app.metric[0].value == "Monitoring"
    assert "Observed 2023-07-01" in _visible_text(app)
