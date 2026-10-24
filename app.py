"""EarthWatch Streamlit entry point. Run with: streamlit run app.py

Owner: Person 3 (Product & Dashboard). Talks to the backend only via translator.py.
"""

from dataclasses import dataclass, field
from datetime import date

import pandas as pd
import streamlit as st

import translator
from dashboard import components
from dashboard.charts import anomaly_comparison_chart, observation_chart
from dashboard.maps import region_map
from dashboard.globe import render_globe
from dashboard.sources import sources_panel
from dashboard.theme import apply_theme
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, ProgressEvent
from schemas.errors import TranslatorError

TAB_NAMES = ("Overview", "Climate Explorer", "Investigation", "Regional Briefing")
DEFAULT_THRESHOLD = 1.0
CACHE_SECONDS = 600
REGION_KEY = "region_select"
ANOMALY_KEY = "anomaly_select"


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


# Restricts the visible events by region and observation dates without losing saved results.
def event_filters(anomalies: list[AnomalyRecord]) -> list[AnomalyRecord]:
    regions = sorted({item.region for item in anomalies})
    dates = [item.observation_date for item in anomalies]
    selected = st.sidebar.multiselect("Regions to include", regions, default=regions, key="region_filter")
    period = st.sidebar.date_input("Observation period", value=(min(dates), max(dates)), key="period_filter")
    if len(period) != 2:
        st.info("Select the end date to finish the observation period.")
        return []
    return [item for item in anomalies if item.region in selected and period[0] <= item.observation_date <= period[1]]


# Resets filters and chooses the latest detected event for a repeatable demonstration.
def prepare_guided_demo(anomalies: list[AnomalyRecord]) -> None:
    candidates = [item for item in anomalies if item.status == "detected"] or anomalies
    selected = max(candidates, key=lambda item: item.observation_date)
    st.session_state["region_filter"] = sorted({item.region for item in anomalies})
    st.session_state["period_filter"] = (min(item.observation_date for item in anomalies), max(item.observation_date for item in anomalies))
    st.session_state[REGION_KEY] = selected.region
    st.session_state[ANOMALY_KEY] = selected
    st.session_state["guided_pending"] = selected.anomaly_id


# Picks a region, then an anomaly in that region, from the sidebar.
def select_anomaly(anomalies: list[AnomalyRecord]) -> AnomalyRecord:
    st.sidebar.header("Demo controls")
    regions = sorted({anomaly.region for anomaly in anomalies})
    region = st.sidebar.selectbox("Region", regions, key=REGION_KEY)
    in_region = [anomaly for anomaly in anomalies if anomaly.region == region]
    return st.sidebar.selectbox(
        "Anomaly", in_region, format_func=anomaly_label, key=ANOMALY_KEY
    )


# Selects the anomaly whose globe marker was clicked (runs before the script body).
def select_from_globe(anomaly_id: str) -> None:
    try:
        anomalies, _ = cached_anomalies()
    except TranslatorError:
        return
    match = next((item for item in anomalies if item.anomaly_id == anomaly_id), None)
    if match is not None:
        st.session_state[REGION_KEY] = match.region
        st.session_state[ANOMALY_KEY] = match


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


# Reads explicit classifications and offers an illustrative color selector only in sample mode.
def severity_controls(anomalies: list[AnomalyRecord], is_sample: bool) -> dict[str, str]:
    raw = st.session_state.get("severity_by_anomaly", {})
    try:
        levels = components._severity_mapping(anomalies, raw)
    except ValueError as error:
        st.sidebar.error(str(error))
        levels = {}
    if is_sample:
        with st.sidebar.expander("Alert color preview (sample data)"):
            choice = st.selectbox("Illustrative severity", ["Use supplied classification", "red", "orange", "yellow", "green"], key="sample_severity")
            st.caption("Visual demonstration only. These colors are not real risk assessments.")
        if choice != "Use supplied classification":
            levels = {item.anomaly_id: choice for item in anomalies}
            st.warning("Severity colors are a sample preview, not a real risk assessment.")
    return levels


# Renders the clicked event: what happened, the agents' latest update, and their sources.
def render_event_panel(selected: AnomalyRecord, result: InvestigationResult | None, severity: str | None = None) -> None:
    st.subheader(f"{selected.region}: {selected.variable.replace('_', ' ')}")
    components.severity_alert(severity)
    st.write(
        f"{selected.value:+g} {selected.unit} on {selected.observation_date} "
        f"(baseline {selected.baseline_period}) · status: {selected.status}"
    )
    assessment = result.assessment if result else None
    if assessment is not None:
        st.write(assessment.summary)
        st.caption(f"Confidence: {assessment.confidence}")
    if result and result.events:
        last = result.events[-1]
        st.caption(f"Last agent update {last.timestamp:%Y-%m-%d %H:%M:%S} · {last.agent}")
    with st.expander("Sources", expanded=True):
        sources_panel(selected, assessment, bool(result and result.is_sample))


# Renders the Overview tab: monitoring status and anomaly cards (the globe is beside it).
def render_overview(
    anomalies: list[AnomalyRecord], anomalies_are_sample: bool, selected: AnomalyRecord,
    severities: dict[str, str] | None = None,
) -> None:
    components.status_strip(anomalies, anomalies_are_sample, severity_by_anomaly=severities)
    st.subheader("Detected signals")
    st.plotly_chart(anomaly_comparison_chart(anomalies, selected.anomaly_id), width="stretch", alt="Supplied anomalies compared only within matching variables and units")
    for anomaly in anomalies:
        components.anomaly_card(anomaly, anomaly.anomaly_id == selected.anomaly_id, severity=(severities or {}).get(anomaly.anomaly_id))


# Renders the Climate Explorer tab: the observation chart and the anomaly detail view.
def render_explorer(
    selected: AnomalyRecord,
    series: pd.DataFrame | None,
    series_is_sample: bool,
    threshold: float,
    replay_until: date | None,
    severity: str | None = None,
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
    components.anomaly_detail(selected, severity=severity)


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
def render_briefing(selected: AnomalyRecord, result: InvestigationResult | None, severity: str | None = None) -> None:
    with st.expander("World map · all continents"):
        st.plotly_chart(region_map(selected.region), width="stretch", alt="World map with the selected monitoring region highlighted")
    if result is None or result.assessment is None:
        st.info("Run an investigation to generate the regional briefing.")
        return
    if result.is_sample:
        show_sample_banner("Assessment")
    components.briefing(result.assessment, selected, severity=severity)


# Builds the full EarthWatch page.
def main() -> None:
    st.set_page_config(page_title="EarthWatch", page_icon="🌍", layout="wide")
    apply_theme()
    st.title("EarthWatch")
    st.caption("Worldwide climate events and anomaly awareness · explore evidence, uncertainty, and recommended actions")
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

    st.sidebar.button("Run guided demo", key="guided_demo", on_click=prepare_guided_demo, args=(anomalies,))
    visible = event_filters(anomalies)
    if not visible:
        st.info("No events match these filters. Adjust the region or observation period, or run the guided demo.")
        return
    if st.session_state.get(REGION_KEY) not in {item.region for item in visible}:
        st.session_state.pop(REGION_KEY, None)
        st.session_state.pop(ANOMALY_KEY, None)
    selected = select_anomaly(visible)
    if "sea_surface_temperature" in selected.variable or selected.variable == "sst":
        series, series_is_sample = load_series(selected.region)
    else:
        series, series_is_sample = None, False
    severities = severity_controls(anomalies, anomalies_are_sample)
    severity = severities.get(selected.anomaly_id)
    threshold, replay_until = demo_controls(anomalies, series)

    globe_column, dashboard_column = st.columns([3, 2], gap="medium")
    with globe_column:
        render_globe(visible, selected.region, select_from_globe,
                     region_locations=st.session_state.get("region_locations"),
                     severity_by_anomaly={item.anomaly_id: severities[item.anomaly_id] for item in visible if item.anomaly_id in severities})
        st.caption(f"Selected signal: {anomaly_label(selected)}")
    with dashboard_column:
        pending = st.session_state.pop("guided_pending", None)
        if st.button("Run Investigation", type="primary", width="stretch", key="run_investigation") or pending == selected.anomaly_id:
            run_investigation(selected)
        result = stored_results().get(selected.anomaly_id)
        if result is not None and result.error:
            st.error(result.error)
        render_event_panel(selected, result, severity)
        overview, explorer, investigation, briefing = st.tabs(TAB_NAMES)
        with overview:
            render_overview(visible, anomalies_are_sample, selected, {item.anomaly_id: severities[item.anomaly_id] for item in visible if item.anomaly_id in severities})
        with explorer:
            render_explorer(selected, series, series_is_sample, threshold, replay_until, severity)
        with investigation:
            render_investigation(selected, result)
        with briefing:
            render_briefing(selected, result, severity)


main()
