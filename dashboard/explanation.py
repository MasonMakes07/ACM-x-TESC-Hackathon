"""Why-is-this-happening section: what the Grok bots found about the cause of an anomaly.

Owner: Person 3 (Product & Dashboard). Built only from the validated Assessment. The bots
test competing explanations and mark each supported, unsupported or untested; this view
shows them as hypotheses with their evidence, never as proven causes.
"""

import re
from dataclasses import dataclass

import streamlit as st

from schemas.assessment import Assessment, EvidenceItem

UNVERIFIED_PREFIX = "[Unverified] "
OPEN_QUESTION_PREFIX = "Open question: "
ALTERNATIVE_PATTERN = re.compile(
    r"^(?P<unverified>\[Unverified\] )?Alternative explanation "
    r"\[(?P<status>supported|unsupported|untested)\]: (?P<body>.*)$",
    re.DOTALL,
)
STATUS_LABELS = {
    "supported": "Supported by the evidence",
    "unsupported": "Not supported by the evidence",
    "untested": "Could not be tested",
}
DISCLAIMER = (
    "These are explanations the agents tested against retrieved evidence. They are "
    "hypotheses, not proven causes. A detected anomaly alone does not establish why it happened."
)


# One competing explanation with the evidence the agents found for and against it.
@dataclass(frozen=True)
class Explanation:
    status: str
    text: str
    evidence_for: str
    evidence_against: str
    unverified: bool


# Splits "<explanation> For: <a> Against: <b>" into its three parts.
def _split_body(body: str) -> tuple[str, str, str]:
    for_at = body.find(" For: ")
    against_at = body.find(" Against: ")
    ends = [index for index in (for_at, against_at) if index != -1]
    text = body[: min(ends)] if ends else body
    evidence_for = ""
    evidence_against = ""
    if for_at != -1:
        stop = against_at if against_at > for_at else len(body)
        evidence_for = body[for_at + len(" For: "): stop]
    if against_at != -1:
        stop = for_at if for_at > against_at else len(body)
        evidence_against = body[against_at + len(" Against: "): stop]
    return text.strip(), evidence_for.strip(), evidence_against.strip()


# Pulls the tested explanations out of the assessment's findings, in the order given.
def parse_explanations(assessment: Assessment) -> list[Explanation]:
    found = []
    for finding in [*assessment.contradictory_findings, *assessment.supporting_findings]:
        match = ALTERNATIVE_PATTERN.match(finding)
        if match is None:
            continue
        text, evidence_for, evidence_against = _split_body(match["body"])
        found.append(Explanation(
            status=match["status"], text=text, evidence_for=evidence_for,
            evidence_against=evidence_against, unverified=bool(match["unverified"]),
        ))
    return found


# Returns what the agents say they could not resolve.
def open_questions(assessment: Assessment) -> list[str]:
    return [
        item[len(OPEN_QUESTION_PREFIX):]
        for item in assessment.limitations
        if item.startswith(OPEN_QUESTION_PREFIX)
    ]


# Returns evidence that comes from a published source rather than the raw measurement.
def source_statements(assessment: Assessment) -> list[EvidenceItem]:
    return [item for item in assessment.evidence if item.evidence_type == "reported"]


# Renders one tested explanation with the evidence on each side.
def _render_explanation(item: Explanation) -> None:
    with st.container(border=True):
        st.markdown(f"**{item.text}**")
        label = STATUS_LABELS[item.status]
        st.caption(f"{label}{' · wording overstates the evidence' if item.unverified else ''}")
        if item.evidence_for:
            st.markdown(f"**Evidence for:** {item.evidence_for}")
        if item.evidence_against:
            st.markdown(f"**Evidence against:** {item.evidence_against}")


# Renders the explanation of why the anomaly may be happening, or says honestly that none exists.
def render_explanation(assessment: Assessment | None, assessment_is_sample: bool = False) -> None:
    st.markdown("#### Why is this happening?")
    if assessment is None:
        st.info("The agents have not explained this event yet.")
        return
    if assessment_is_sample:
        st.warning("SAMPLE explanation: placeholder text, not a real finding.")
    st.write(assessment.summary)
    st.caption(DISCLAIMER)
    explanations = parse_explanations(assessment)
    supported = [item for item in explanations if item.status == "supported"]
    others = [item for item in explanations if item.status != "supported"]
    if supported:
        st.markdown("**Best-supported explanations**")
        for item in supported:
            _render_explanation(item)
    else:
        st.info("The retrieved evidence does not establish a cause for this anomaly.")
    if others:
        with st.expander(f"Other possibilities the agents checked ({len(others)})"):
            for item in others:
                _render_explanation(item)
    statements = source_statements(assessment)
    if statements:
        st.markdown("**What published sources say**")
        for evidence in statements:
            st.markdown(f"- {evidence.claim} (*{evidence.source}*)")
    questions = open_questions(assessment)
    if questions:
        with st.expander("Still unknown"):
            st.markdown("\n".join(f"- {text}" for text in questions))
