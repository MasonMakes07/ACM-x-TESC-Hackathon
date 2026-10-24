"""EarthWatch Streamlit entry point. Run with: streamlit run app.py

Owner: Person 3 (Product & Dashboard). Talks to the backend only via translator.py.
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import streamlit as st

import translator
from dashboard import components
from dashboard.charts import observation_chart
from dashboard.globe import render_globe
from dashboard.theme import apply_theme
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, ProgressEvent
from schemas.errors import TranslatorError

TAB_NAMES = ("Overview", "Climate Explorer", "Investigation", "Regional Briefing")
DEFAULT_THRESHOLD = 1.0
CACHE_SECONDS = 600


# One finished (or failed) investigation, kept per anomaly so tabs and reruns keep it.
@dataclass
class InvestigationResult:
    events: list[ProgressEvent] = field(default_factory=list)
    assessment: Assessment | None = None
    is_sample: bool = False
    error: str | None = None


# Loads anomalies once per cache window so slider moves don't re-run the pipeline.
@st.cache_data(ttl=CACHE_SECONDS, show_spinner="Loading anomalies...")
def cached_anomalies() -> tuple[list[AnomalyRecord], bool]:
    return translator.load_anomalies()


# Loads a region's observation series once per cache window.
@st.cache_data(ttl=CACHE_SECONDS, show_spinner="Loading observations...")
def cached_series(region: str) -> tuple[pd.DataFrame, bool]:
    return translator.load_observation_series(region)


# Shows a warning banner when a section is rendered from sample data.
def show_sample_banner(section_name: str) -> None:
    st.warning(f"{section_name}: SAMPLE DATA - workstream not implemented yet.")


# Formats an anomaly as a one-line label for the selector.
def anomaly_label(anomaly: AnomalyRecord) -> str:
    return (
        f"{anomaly.region} | {anomaly.observation_date} | "
        f"{anomaly.value} {anomaly.unit} | {anomaly.status}"
    )


# Returns the investigation results stored for this session, keyed by anomaly id.
def stored_results() -> dict[str, InvestigationResult]:
    return st.session_state.setdefault("results", {})


# Loads the selected region's series, returning None (with an error shown) on failure.
def load_series(region: str) -> tuple[pd.DataFrame | None, bool]:
    try:
        return cached_series(region)
    except TranslatorError as error:
        st.error(str(error))
        return None, False


# Draws the threshold and replay sidebar controls and returns their values.
def demo_controls(
    anomalies: list[AnomalyRecord], series: pd.DataFrame | None
) -> tuple[float, date | None]:
    threshold = st.sidebar.slider(
        "Anomaly threshold (±)", 0.5, 3.0, DEFAULT_THRESHOLD, 0.1,
        help="Dashed reference lines on the chart. Detection itself is done by the climate pipeline.",
    )
    replay_until = None
    if series is not None and not series.empty:
        replay_dates = [stamp.date() for stamp in series["date"]]
        replay_until = st.sidebar.select_slider(
            "Historical replay: show data up to",
            options=replay_dates, value=replay_dates[-1],
        )
    st.sidebar.caption(
        f"{len(anomalies)} anomalies loaded. Results are kept per anomaly while you switch."
    )
    return threshold, replay_until


# Picks a region, then an anomaly in that region, from the sidebar.
def select_anomaly(anomalies: list[AnomalyRecord]) -> AnomalyRecord:
    st.sidebar.header("Demo controls")
    regions = sorted({anomaly.region for anomaly in anomalies})
    region = st.sidebar.selectbox("Region", regions)
    in_region = [anomaly for anomaly in anomalies if anomaly.region == region]
    return st.sidebar.selectbox("Anomaly", in_region, format_func=anomaly_label)


# Runs the investigation, streaming real progress events into a status box and storing them.
def run_investigation(anomaly: AnomalyRecord) -> None:
    result = InvestigationResult()
    with st.status("Investigating...", expanded=True) as status_box:

        # Writes one progress event into the status box and keeps it for the timeline.
        def report_progress(event: ProgressEvent) -> None:
            result.events.append(event)
            status_box.write(
                f"{event.timestamp:%H:%M:%S} **{event.agent}**: {event.message}"
            )

        try:
            result.assessment, result.is_sample = translator.investigate_anomaly(
                anomaly.anomaly_id, report_progress
            )
        except TranslatorError as error:
            result.error = str(error)
            status_box.update(label="Investigation failed", state="error")
        else:
            status_box.update(label="Assessment complete", state="complete", expanded=False)
    stored_results()[anomaly.anomaly_id] = result


# Renders the Overview tab: monitoring status and anomaly cards (the globe is beside it).
def render_overview(
    anomalies: list[AnomalyRecord], anomalies_are_sample: bool, selected: AnomalyRecord
) -> None:
    components.status_strip(anomalies, anomalies_are_sample)
    st.subheader("Detected signals")
    for anomaly in anomalies:
        components.anomaly_card(anomaly, anomaly.anomaly_id == selected.anomaly_id)


# Renders the Climate Explorer tab: the observation chart and the anomaly detail view.
def render_explorer(
    selected: AnomalyRecord,
    series: pd.DataFrame | None,
    series_is_sample: bool,
    threshold: float,
    replay_until: date | None,
) -> None:
    if series is None:
        st.info("Observations are unavailable for this region right now.")
    else:
        if series_is_sample:
            show_sample_banner("Observations")
        st.plotly_chart(
            observation_chart(
                series, f"{selected.region} {selected.variable}", selected.unit,
                anomaly=selected, threshold=threshold, replay_until=replay_until,
            ),
            width="stretch",
        )
        if replay_until and replay_until < selected.observation_date:
            st.caption(
                f"Replay is at {replay_until}. Move the slider to {selected.observation_date} "
                "to reach the detected anomaly."
            )
    components.anomaly_detail(selected)


# Renders the original observation next to the agents' conclusion.
def render_comparison(selected: AnomalyRecord, assessment: Assessment) -> None:
    st.subheader("Observation vs. conclusion")
    observed, concluded = st.columns(2)
    with observed:
        with st.container(border=True):
            st.caption("What the data measured")
            st.metric(selected.region, f"{selected.value:+g} {selected.unit}")
            st.write(f"{selected.observation_date} · {selected.source}")
    with concluded:
        with st.container(border=True):
            st.caption("What the agents concluded")
            st.metric("Confidence", assessment.confidence.capitalize())
            st.write(assessment.summary)


# Renders the Investigation tab: the real progress timeline and the comparison.
def render_investigation(selected: AnomalyRecord, result: InvestigationResult | None) -> None:
    if result is None:
        components.investigation_timeline([])
        return
    components.investigation_timeline(result.events)
    if result.assessment is not None:
        if result.is_sample:
            show_sample_banner("Assessment")
        render_comparison(selected, result.assessment)


# Renders the Regional Briefing tab once an assessment exists for the selected anomaly.
def render_briefing(selected: AnomalyRecord, result: InvestigationResult | None) -> None:
    if result is None or result.assessment is None:
        st.info("Run an investigation to generate the regional briefing.")
        return
    if result.is_sample:
        show_sample_banner("Assessment")
    components.briefing(result.assessment, selected)


# Builds the full EarthWatch page.
def main() -> None:
    st.set_page_config(page_title="EarthWatch", page_icon="🌊", layout="wide")
    apply_theme()
    st.title("EarthWatch")
    st.caption("Global climate intelligence · first monitored: eastern tropical Pacific and northern Peru")
    try:
        anomalies, anomalies_are_sample = cached_anomalies()
    except TranslatorError as error:
        st.error(str(error))
        return
    if anomalies_are_sample:
        show_sample_banner("Anomalies")
    if not anomalies:
        st.info("No anomalies detected.")
        return

    selected = select_anomaly(anomalies)
    series, series_is_sample = load_series(selected.region)
    threshold, replay_until = demo_controls(anomalies, series)

    globe_column, dashboard_column = st.columns([3, 2], gap="medium")
    with globe_column:
        render_globe(anomalies, selected.region)
        st.caption(f"Selected signal: {anomaly_label(selected)}")
    with dashboard_column:
        if st.button("Run Investigation", type="primary", width="stretch"):
            run_investigation(selected)
        result = stored_results().get(selected.anomaly_id)
        if result is not None and result.error:
            st.error(result.error)
        overview, explorer, investigation, briefing = st.tabs(TAB_NAMES)
        with overview:
            render_overview(anomalies, anomalies_are_sample, selected)
        with explorer:
            render_explorer(selected, series, series_is_sample, threshold, replay_until)
        with investigation:
            render_investigation(selected, result)
        with briefing:
            render_briefing(selected, result)


main()
