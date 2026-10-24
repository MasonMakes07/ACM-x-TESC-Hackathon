"""Explanation view checks. Owner: Person 3 (Product & Dashboard)."""

from streamlit.testing.v1 import AppTest

from dashboard.explanation import parse_explanations, open_questions, source_statements
from schemas.assessment import Assessment, EvidenceItem

ALT = (
    "Alternative explanation [{status}]: {text} For: {pro} Against: {con}"
)


# Builds an assessment carrying tested explanations, a published source and an open question.
def _assessment(**overrides) -> Assessment:
    fields = dict(
        anomaly_id="expl_001", summary="Warm SST anomaly detected.", confidence="moderate",
        evidence=[EvidenceItem(
            claim="NOAA CPC describes an El Nino Watch.", source="NOAA CPC ENSO Diagnostic Discussion",
            evidence_type="reported", url="https://www.cpc.ncep.noaa.gov/x",
        )],
        contradictory_findings=[
            ALT.format(status="supported", text="A developing El Nino.", pro="NOAA watch issued.", con="No coupled response yet."),
            "[Unverified] " + ALT.format(status="untested", text="Local upwelling change.", pro="", con=""),
            "A plain contradiction that is not an explanation.",
        ],
        supporting_findings=[ALT.format(status="unsupported", text="Sensor error.", pro="", con="Index matches NOAA file.")],
        limitations=["Open question: Is the warming persistent?", "Something else."],
    )
    return Assessment(**{**fields, **overrides})


# Checks tested explanations are parsed with their status and both evidence sides.
def test_explanations_are_parsed_with_evidence():
    found = parse_explanations(_assessment())
    by_text = {item.text.rstrip("."): item for item in found}
    assert set(by_text) == {"A developing El Nino", "Local upwelling change", "Sensor error"}
    nino = by_text["A developing El Nino"]
    assert nino.status == "supported"
    assert nino.evidence_for == "NOAA watch issued."
    assert nino.evidence_against == "No coupled response yet."
    assert by_text["Local upwelling change"].unverified
    assert by_text["Sensor error"].evidence_against == "Index matches NOAA file."


# Checks ordinary findings are not mistaken for explanations.
def test_plain_findings_are_ignored():
    assert parse_explanations(_assessment(contradictory_findings=["Just a contradiction."], supporting_findings=[])) == []


# Checks open questions and published-source statements are extracted.
def test_open_questions_and_source_statements():
    assessment = _assessment()
    assert open_questions(assessment) == ["Is the warming persistent?"]
    assert [item.source for item in source_statements(assessment)] == ["NOAA CPC ENSO Diagnostic Discussion"]


# Runs the renderer in a real Streamlit script and returns the app.
def _render(assessment, is_sample=False):
    def script(assessment, is_sample):
        from dashboard.explanation import render_explanation
        render_explanation(assessment, is_sample)

    app = AppTest.from_function(script, args=(assessment, is_sample), default_timeout=30)
    return app.run()


# Checks supported causes are shown first and others sit behind a labelled expander.
def test_render_shows_supported_first_and_hides_others():
    app = _render(_assessment())
    assert not app.exception
    text = " ".join(item.value for item in app.markdown)
    assert "Best-supported explanations" in text and "A developing El Nino" in text
    assert "What published sources say" in text and "NOAA CPC describes an El Nino Watch." in text
    assert any("Other possibilities the agents checked (2)" in item.label for item in app.expander)
    assert any("not proven causes" in item.value for item in app.caption)


# Checks an assessment with no supported cause says so instead of inventing one.
def test_render_says_when_no_cause_is_established():
    app = _render(_assessment(contradictory_findings=[], supporting_findings=[]))
    assert any("does not establish a cause" in item.value for item in app.info)


# Checks a missing assessment and a sample assessment are labelled honestly.
def test_render_handles_missing_and_sample_assessments():
    assert any("have not explained" in item.value for item in _render(None).info)
    assert any("SAMPLE explanation" in item.value for item in _render(_assessment(), True).warning)
