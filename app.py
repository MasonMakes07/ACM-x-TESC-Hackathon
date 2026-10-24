"""EarthWatch Streamlit entry point. Run with: streamlit run app.py

Owner: Person 3 (Product & Dashboard). Talks to the backend only via translator.py.
"""

import streamlit as st

import translator
from dashboard.charts import observation_chart
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, ProgressEvent
from schemas.errors import TranslatorError


# Shows a warning banner when a section is rendered from sample data.
def show_sample_banner(section_name: str) -> None:
    st.warning(f"{section_name}: SAMPLE DATA - workstream not implemented yet.")


# Formats an anomaly as a one-line label for the selector.
def anomaly_label(anomaly: AnomalyRecord) -> str:
    return (
        f"{anomaly.region} | {anomaly.observation_date} | "
        f"{anomaly.value} {anomaly.unit} | {anomaly.status}"
    )


# Renders the observation chart for the selected anomaly's region.
def render_series(anomaly: AnomalyRecord) -> None:
    try:
        series, series_is_sample = translator.load_observation_series(anomaly.region)
    except TranslatorError as error:
        st.error(str(error))
        return
    if series_is_sample:
        show_sample_banner("Observations")
    st.plotly_chart(
        observation_chart(series, f"{anomaly.region} {anomaly.variable}", anomaly.unit),
        width="stretch",
    )


# Renders a finished assessment with evidence, findings and limitations.
def render_assessment(assessment: Assessment, assessment_is_sample: bool) -> None:
    if assessment_is_sample:
        show_sample_banner("Assessment")
    st.subheader(assessment.summary)
    st.write(f"**Confidence:** {assessment.confidence}")
    sections = {
        "Supporting findings": assessment.supporting_findings,
        "Contradictory findings": assessment.contradictory_findings,
        "Regional implications": assessment.regional_implications,
        "Limitations": assessment.limitations,
        "Recommended next steps": assessment.recommended_next_steps,
    }
    for heading, items in sections.items():
        if items:
            st.markdown(f"**{heading}**")
            st.markdown("\n".join(f"- {item}" for item in items))
    for evidence in assessment.evidence:
        with st.expander(f"[{evidence.evidence_type}] {evidence.claim}"):
            st.write(f"Source: {evidence.source} ({evidence.source_date or 'undated'})")
            if evidence.limitations:
                st.write(f"Limitations: {evidence.limitations}")


# Runs the investigation and streams real progress events into a status box.
def run_investigation(anomaly: AnomalyRecord) -> None:
    with st.status("Investigating...", expanded=True) as status_box:

        # Writes one progress event into the status box.
        def report_progress(event: ProgressEvent) -> None:
            status_box.write(
                f"{event.timestamp:%H:%M:%S} **{event.agent}**: {event.message}"
            )

        try:
            assessment, assessment_is_sample = translator.investigate_anomaly(
                anomaly.anomaly_id, report_progress
            )
        except TranslatorError as error:
            status_box.update(label="Investigation failed", state="error")
            st.error(str(error))
            return
        status_box.update(label="Assessment complete", state="complete")
    render_assessment(assessment, assessment_is_sample)


# Builds the full EarthWatch page.
def main() -> None:
    st.set_page_config(page_title="EarthWatch", layout="wide")
    st.title("EarthWatch")
    mode = st.radio("Monitoring view", ["Worldwide locations", "Pacific ocean indices"], horizontal=True)
    if mode == "Worldwide locations":
        from dashboard.global_explorer import render_global_explorer
        render_global_explorer(render_assessment)
        return
    st.caption("Pacific ocean indices")
    try:
        anomalies, anomalies_are_sample = translator.load_anomalies()
    except TranslatorError as error:
        st.error(str(error))
        return
    if anomalies_are_sample:
        show_sample_banner("Anomalies")
    if not anomalies:
        st.info("No anomalies detected.")
        return
    selected_anomaly = st.selectbox("Anomaly", anomalies, format_func=anomaly_label)
    render_series(selected_anomaly)
    if st.button("Run Investigation", type="primary"):
        run_investigation(selected_anomaly)


main()
