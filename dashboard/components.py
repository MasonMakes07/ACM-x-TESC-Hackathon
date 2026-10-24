"""Accessible dashboard components. Owner: Person 3 / Codex B."""

from html import escape
from urllib.parse import urlsplit

import streamlit as st

from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, EvidenceItem, ProgressEvent

CONFIDENCE_COLORS = {
    "high": "#70E1BB",
    "moderate": "#FFD180",
    "low": "#FFABAB",
    "inconclusive": "#CBD5E1",
}
EVIDENCE_BADGES = {
    "measured": "📏 Measured",
    "reported": "📰 Reported",
    "inferred": "🔎 Inferred",
    "uncertain": "❓ Uncertain",
}
STATUS_LABELS = {
    "detected": "Signal detected",
    "monitoring": "Monitoring",
    "inconclusive": "Inconclusive",
}


# Returns an accessible foreground color without treating unknown levels as certainty.
def confidence_color(level: str) -> str:
    return CONFIDENCE_COLORS.get(level, "#CBD5E1")


# Pairs each evidence category with text so meaning never depends on its icon.
def evidence_badge(evidence_type: str) -> str:
    return EVIDENCE_BADGES.get(evidence_type, "❔ Unclassified")


# Makes schema field names readable without changing the underlying scientific meaning.
def _readable(value: str) -> str:
    return value.replace("_", " ").capitalize()


# Formats a measurement with its supplied units.
def _measurement(anomaly: AnomalyRecord) -> str:
    unit = "°C" if anomaly.unit == "degC" else anomaly.unit
    return f"{anomaly.value:g} {unit}"


# Displays supplied findings as text, keeping external content out of HTML.
def _findings(items: list[str], empty_message: str) -> None:
    if not items:
        st.caption(empty_message)
    for item in items:
        st.write("• " + item)


# Summarizes regional signal status and explicitly dates the displayed observations.
def status_strip(anomalies: list[AnomalyRecord], is_sample: bool) -> None:
    st.subheader("Monitoring status")
    if not anomalies:
        st.info("No observations available. Monitoring status cannot be determined.")
        if is_sample:
            st.caption("(sample data)")
        return
    latest = max(item.observation_date for item in anomalies)
    st.caption(f"Data as of {latest:%Y-%m-%d}" + (" (sample data)" if is_sample else ""))
    regions = sorted({item.region for item in anomalies})
    for offset in range(0, len(regions), 3):
        batch = regions[offset:offset + 3]
        for column, region in zip(st.columns(len(batch)), batch):
            records = [item for item in anomalies if item.region == region]
            region_date = max(item.observation_date for item in records)
            latest_records = [item for item in records if item.observation_date == region_date]
            status = next(
                (state for state in ("detected", "monitoring", "inconclusive")
                 if any(item.status == state for item in latest_records)),
                None,
            )
            with column:
                st.metric(region, STATUS_LABELS.get(status, "Unknown status"))
                st.caption(f"Observed {region_date:%Y-%m-%d}")


# Presents a compact anomaly card with a textual selection indicator.
def anomaly_card(anomaly: AnomalyRecord, selected: bool = False) -> None:
    with st.container(border=True):
        if selected:
            st.caption("● Selected signal")
        st.text(anomaly.region)
        st.caption(_readable(anomaly.variable))
        st.metric("Recorded value", _measurement(anomaly))
        label = escape(STATUS_LABELS.get(anomaly.status, "Unknown status"))
        st.markdown(
            f'<span style="display:inline-block;border:1px solid #b8c8d9;'
            f'border-radius:999px;padding:.2rem .65rem;color:#edf3fa">{label}</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"Observed {anomaly.observation_date:%Y-%m-%d}")


# Explains the selected record and offers a short optional walkthrough.
def anomaly_detail(anomaly: AnomalyRecord) -> None:
    st.subheader("Signal details")
    st.text(f"{anomaly.region} · {_readable(anomaly.variable)}")
    left, right = st.columns(2)
    with left:
        st.metric("Recorded value", _measurement(anomaly))
        st.text(f"Observation date: {anomaly.observation_date:%Y-%m-%d}")
        st.text(f"Status: {STATUS_LABELS.get(anomaly.status, 'Unknown status')}")
    with right:
        st.text(f"Baseline period: {anomaly.baseline_period}")
        st.text(f"Detection method: {_readable(anomaly.detection_method)}")
        st.text(f"Source: {anomaly.source}")
    if "anomaly" in anomaly.variable.lower():
        st.caption(
            f"Anomaly magnitude: {_measurement(anomaly)} relative to the source's "
            "baseline. Positive means above the baseline; negative means below. "
            "The absolute temperature and baseline mean are not supplied in this record."
        )
    else:
        st.caption("Anomaly magnitude and baseline mean are not supplied in this record.")
    with st.expander("New here? How to use EarthWatch"):
        st.markdown(
            "1. **Choose a signal.** Select a region and an observation to inspect.\n"
            "2. **Explore the measurements.** Check the date, units, source, and baseline. "
            "An anomaly is a difference from a historical reference.\n"
            "3. **Run Investigation.** Click the button to ask the agents to examine "
            "the selected signal. Follow their actual progress in Investigation.\n"
            "4. **Read the briefing.** Compare measured observations with potential "
            "regional implications, then expand the evidence to check sources.\n"
            "5. **Check uncertainty.** Read confidence, conflicting findings, and "
            "limitations before using the assessment."
        )
        st.caption(
            "Measured = data observation; reported = a source's statement; "
            "inferred = an interpretation; uncertain = unresolved. "
            "Sample data is illustrative. Historical replay shows past observations. "
            "A detected anomaly alone does not establish a flood forecast."
        )


# Renders only actual progress events, preserving their supplied order.
def investigation_timeline(events: list[ProgressEvent]) -> None:
    if not events:
        st.info("No investigation run yet. Click Run Investigation.")
        return
    st.caption("Investigation progress · timestamps as supplied by the backend")
    for event in events:
        with st.expander(f"{event.timestamp:%H:%M:%S}  {event.agent}"):
            st.text(event.message)
            st.caption(f"Timestamp: {event.timestamp.isoformat()}")


# Orders evidence by provenance and exposes only HTTP or HTTPS source links.
def evidence_list(evidence: list[EvidenceItem]) -> None:
    if not evidence:
        st.info("No evidence supplied. The assessment cannot be independently checked here.")
        return
    order = {kind: index for index, kind in enumerate(EVIDENCE_BADGES)}
    for item in sorted(evidence, key=lambda record: order.get(record.evidence_type, 4)):
        with st.expander(f"{evidence_badge(item.evidence_type)} · {item.claim}"):
            st.text(f"Source: {item.source}")
            st.text(f"Source date: {item.source_date or 'undated'}")
            st.text(f"Evidence type: {item.evidence_type}")
            if item.limitations:
                st.text(f"Limitations: {item.limitations}")
            if item.url:
                try:
                    url = urlsplit(item.url)
                    valid = url.scheme.lower() in {"http", "https"} and bool(url.netloc)
                except ValueError:
                    valid = False
                if valid:
                    st.link_button("Open source", item.url)
                else:
                    st.caption("Source link unavailable: a valid HTTP or HTTPS URL is required.")


# Separates supplied observations, interpretations, provenance, and uncertainty.
def briefing(assessment: Assessment, anomaly: AnomalyRecord) -> None:
    if assessment.anomaly_id != anomaly.anomaly_id:
        st.error("This assessment belongs to a different signal. Run an investigation for the selected signal.")
        return
    st.caption("Regional briefing")
    st.subheader(assessment.summary)
    level = escape(assessment.confidence.capitalize())
    st.markdown(
        f'<span class="ew-confidence" style="color:{confidence_color(assessment.confidence)}">'
        f'Confidence: {level}</span>', unsafe_allow_html=True,
    )
    st.caption(
        "Confidence is the investigation's qualitative assessment, not a probability. "
        "Check the evidence and limitations below for its basis; no separate confidence "
        "rationale is supplied in this report."
    )
    st.markdown("### What we observed")
    st.text(
        f"{anomaly.region}: {_readable(anomaly.variable)} = {_measurement(anomaly)} "
        f"on {anomaly.observation_date:%Y-%m-%d}. Source: {anomaly.source}. "
        f"Baseline period: {anomaly.baseline_period}."
    )
    measured = [item.claim for item in assessment.evidence if item.evidence_type == "measured"]
    _findings(measured, "No additional measured evidence supplied.")
    st.markdown("### Why it matters")
    st.caption("Potential regional implications · these are not confirmed outcomes")
    _findings(assessment.regional_implications, "No regional implications established.")
    supporting, contradictory = st.columns(2)
    with supporting:
        st.markdown("### Supporting findings")
        _findings(assessment.supporting_findings, "No supporting findings supplied.")
    with contradictory:
        st.markdown("### Contradictory findings")
        _findings(assessment.contradictory_findings, "No contradictory findings supplied. This does not establish agreement.")
    st.markdown("### Evidence and sources")
    evidence_list(assessment.evidence)
    st.markdown("### Recommended next steps")
    _findings(assessment.recommended_next_steps, "No next steps supplied.")
    st.markdown("### Limitations")
    _findings(assessment.limitations, "No limitations supplied. This does not establish certainty.")
    st.caption("EarthWatch investigates unusual conditions. An ocean-temperature anomaly alone cannot establish a specific flood forecast.")
