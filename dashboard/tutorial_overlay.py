"""Guided browser-local tour with an animated pointer and responsive overlay."""
from pathlib import Path

import streamlit as st


def step(title, text, *, label=None, button=None, tab=None, expander=None, selector=None):
    return dict(title=title, text=text, label=label, button=button, tab=tab, expander=expander, selector=selector)


COMMON = [
    step("Welcome to EarthWatch", "EarthWatch helps you explore climate observations, unusual signals, and the evidence behind them. Follow the moving guide pointer. Use Next to continue, Back to revisit, or Escape to exit. You can interact with highlighted controls whenever you want. Your real mouse stays under your control.", selector="h1"),
    step("Choose your monitoring view", "Weather anomalies compares current conditions with history. Global risk watchlist explores seasonal outlooks. Worldwide locations searches places and climate history. Pacific ocean indices shows ocean signals. This tour follows the view you have open; switch views and click Tutorial to learn the other workflow.", label="Monitoring view"),
]

PACIFIC = [
    step("Guided demo", "This separate demo resets filters, selects the latest detected signal, and runs an investigation. It can call the investigation service. Click it only when you want to run that workflow; the tutorial never runs it for you.", button="Run guided demo"),
    step("Filter regions", "Choose which regions appear on the globe and in the signal overview. Removing all regions hides all signals; add a region again to restore them.", label="Regions to include"),
    step("Filter observation dates", "Set the start and end dates of the signals you want to see. Finish both dates to apply the period.", label="Observation period"),
    step("Choose a region and signal", "Region selects a monitoring area. The Anomaly selector below it chooses a specific measurement, date, and detection status. The charts, sources, and investigation use that selection.", label="Region"),
    step("Choose the anomaly", "An anomaly is a measurement that differs from its historical baseline. Detection is a statistical signal, not a confirmed impact or risk assessment.", label="Anomaly"),
    step("Chart reference threshold", "Adjust the dashed reference lines on the observation chart. This control changes the chart guide; detection itself is performed by the climate pipeline.", label="Anomaly threshold (±)"),
    step("Historical replay", "Reveal the time series up to a chosen date to see how a signal developed. This changes the displayed history without deleting investigation results. This control appears when an observation series is available.", label="Historical replay: show data up to"),
    step("Explore the globe", "Drag the globe to look around and click an event marker to select its signal. Automatic rotation controls its motion; Alert pulses controls marker animation. Colors reflect supplied classifications, and sample previews are labeled.", label="Automatic rotation"),
    step("Investigate a signal", "Click Run Investigation when you want to analyze the selected anomaly. Progress updates appear while agents work, and the finished result is saved for this signal during your session. You can continue this tour without running it.", button="Run Investigation"),
    step("Review sources", "The selected signal panel shows the measurement, baseline, status, and any completed assessment. Expand Sources to inspect original observations and agent evidence. Check provenance and sample-data labels before using conclusions.", expander="Sources"),
    step("Overview", "Compare detected signals and read their cards. Comparisons only group compatible variables and units. The status strip distinguishes loaded signals, samples, and supplied severity classifications.", tab="Overview"),
    step("Climate Explorer", "See the selected region's observations over time, the anomaly details, and chart reference lines. Use the sidebar replay and threshold controls to explore the history. Some signals do not have an observation series.", tab="Climate Explorer"),
    step("Investigation", "Read the agents' progress timeline and compare what was measured with what the assessment concludes. This section fills after you run an investigation; changing signals restores that signal's saved result.", tab="Investigation"),
    step("Regional Briefing", "After an investigation, read regional implications, confidence, limitations, evidence, and recommended next steps. The expandable world map locates the selected region. An empty briefing means this signal still needs an investigation.", tab="Regional Briefing"),
]

WORLD = [
    step("Find a place", "Place search finds named locations. Coordinates lets you specify any point, including remote areas and oceans. Choosing a place moves the globe there; observations describe that point rather than a whole-country average.", label="Choose a location by"),
    step("Narrow your search", "Optionally choose a country or territory to narrow matching place names. Leave All countries and territories selected for a worldwide search. This control appears in Place search mode.", label="Country or territory"),
    step("Search for a location", "Enter at least two characters, then press Enter or click Search locations. Select a Matching location from the results. If you use Coordinates instead, enter a label, latitude, and longitude; south and west are negative.", label="City, town, region, or postal code"),
    step("Choose an observation year", "Select the year to examine. Monthly temperature and precipitation are compared with the preceding 30 years. Current-year data can be incomplete; months with insufficient evidence remain unknown.", label="Observation year"),
    step("Load observations", "After selecting a place, click Load climate data to fetch local observations and their historical baseline. The button is disabled until a location is available. This is optional during the tour.", button="Load climate data"),
    step("Explore the location globe", "Drag to look around, use Automatic rotation to pause motion, and toggle Alert pulses to control animation. Once data is loaded, click an event marker to select its climate variable and observation.", label="Automatic rotation"),
    step("Compare climate variables", "After loading data, use Climate variable to switch between air temperature and precipitation. The chart compares observations with the calendar-month baseline. Missing data or inadequate baseline coverage is explicitly marked.", label="Climate variable"),
    step("Inspect baseline details", "Expand Measurements and baseline details after loading data to inspect monthly values, anomalies, z-scores, and baseline counts. These help explain how unusual a measurement is.", expander="Measurements and baseline details"),
    step("Download observations", "After loading data, download daily observations or monthly anomalies as CSV files to review the measurements and calculations outside EarthWatch.", button="Download daily observations"),
    step("Choose evidence to investigate", "After loading data, select a month in Observation to investigate. Review its value, baseline, and detection status before asking for an assessment.", label="Observation to investigate"),
    step("Run and read an investigation", "Click Run Investigation when ready. After completion, review supporting and contradictory findings, regional implications, limitations, next steps, and source evidence below. Statistical-only and sample results are labeled. The tutorial never starts an investigation for you.", button="Run Investigation"),
]

FINISH = step("You're ready to explore", "You can reopen Tutorial at any time. Try another monitoring view for its own walkthrough. Review source links, confidence, limitations, and sample labels whenever you interpret a result.", selector="h1")

_TUTORIAL = st.components.v2.component(
    "earthwatch_guided_tutorial",
    js=Path(__file__).with_name("tutorial.js").read_text(),
)


def tutorial_button(*, sidebar: bool = True) -> None:
    def start():
        st.session_state["tutorial_run"] = st.session_state.get("tutorial_run", 0) + 1

    area = st.sidebar if sidebar else st
    area.button("Tutorial" if sidebar else "Start tutorial", icon=":material/help:",
                key="start_tutorial" if sidebar else "start_tutorial_main", on_click=start,
                help="Follow a guided walkthrough of the current monitoring view.")


WEATHER = [
    step("Watch your places", "Open Add a location in the sidebar, search for a city or postal code, choose a matching place, and click Watch this place.", expander="Add a location"),
    step("Choose temperature units", "Switch between Fahrenheit and Celsius for the weather comparison.", label="Temperature units"),
    step("Compare weather with history", "Scan your watched locations to compare current measurements with the historical baseline. This fetches observations only when you click the scan button.", button="Scan weather against history"),
    step("Explore a location", "Drag the globe to explore. Click a marker or use Open location to inspect a place. The chart and measurements appear after a scan.", label="Open location"),
    step("Understand the comparison", "Review the historical distribution, current measurement, data coverage, and source timestamps. A historical departure alone does not establish an impact or cause.", selector='[data-testid="stPlotlyChart"]'),
    step("Read a briefing", "After scanning, request possible causes and protective actions for the selected location. Review the supporting sources and uncertainty. The tutorial does not request a briefing for you.", button="Explain causes & safety actions"),
]

WATCH = [
    step("Build your watchlist", "Add places or import watched areas using the sidebar. These outlooks describe seasonal conditions rather than today's weather.", expander="Manage watched areas"),
    step("Choose areas", "Select the watched areas to include in the seasonal scan.", label="Areas to scan"),
    step("Choose hazards", "Filter the kinds of hazards you want to review.", label="Hazards to show"),
    step("Request seasonal outlooks", "Click to request outlooks for your selected areas. Review dates, evidence, and uncertainty before interpreting a watch level. The tutorial never starts a scan.", button="Scan selected areas with Grok"),
    step("Read an outlook", "After a scan, choose an area to review its outlook, sources, and limitations.", label="Read an area outlook"),
]


def render_tutorial(view: str) -> None:
    steps = {"Global hazard events": [
        step("Live source events", "NOAA forecast areas load automatically. Grok Scout and Evidence Reviewer explain each area in the background.", selector="h1"),
        step("Update the globe", "Check NOAA for updates and retry pending Grok reviews. Automatic updates check every 30 minutes while open.", button="Update events with Grok"),
        step("Explore forecast types", "Filter cyclone formation, rainfall, and temperature outlooks. Colors identify the forecast type, not severity.", label="Event types"),
        step("Read an event", "Click a shaded area or select an event to read dates, probability, NOAA sources, and the Grok explanation.", label="Choose an event"),
    ], "Worldwide locations": WORLD, "Pacific ocean indices": PACIFIC,
             "Weather anomalies": WEATHER, "Global risk watchlist": WATCH}
    _TUTORIAL(key="earthwatch_tutorial", height=0, data={
        "run": st.session_state.get("tutorial_run", 0),
        "view": view,
        "steps": COMMON + steps.get(view, WEATHER) + [FINISH],
    })
