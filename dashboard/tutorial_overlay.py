"""Guided browser-local tour with an animated pointer and responsive overlay.

Owner: Person 3 (Product & Dashboard). The tour only points at controls; it never clicks
Run Investigation or changes a selection for the user.
"""

from pathlib import Path

import streamlit as st


# Describes one tour step and how to find the control it points at.
def step(title, text, *, label=None, button=None, tab=None, expander=None, heading=None, selector=None):
    return dict(title=title, text=text, label=label, button=button, tab=tab,
                expander=expander, heading=heading, selector=selector)


COMMON = [
    step("Welcome to EarthWatch", "EarthWatch watches for unusual climate events anywhere on Earth: ocean temperature anomalies such as El Nino, unusually high coastal water at NOAA tide gauges like San Diego, and local weather and climate history worldwide. It shows the evidence behind each one. Use Next and Back to move, or Escape to exit. You can click anything while the tour is open.", selector="h1"),
    step("Choose your monitoring view", "Climate events globe shows every detected event on one globe. Worldwide locations lets you search any place or coordinates for its weather and climate history. The tour follows the view you have open; switch views and click Tutorial again to learn the other one.", label="Monitoring view"),
]

GLOBE = [
    step("Guided demo", "Resets the filters, selects the latest detected event and runs an investigation. It can use Grok API credits, so the tour never clicks it for you.", button="Run guided demo"),
    step("Filter regions", "Choose which places appear on the globe and in the overview. Ocean indices and coastal gauges are listed by name. Removing every region hides every event.", label="Regions to include"),
    step("Filter observation dates", "Show only events observed in this period. Pick both a start and an end date to apply it.", label="Observation period"),
    step("Pick a place and an event", "Region chooses a place; the Anomaly list below it chooses one measurement there. Clicking a marker on the globe sets both for you.", label="Region"),
    step("What an anomaly is", "An anomaly is a measurement that departs from what was expected: an ocean index above its 1991-2020 baseline, or water standing higher than NOAA's predicted tide. Detection is a statistical signal, not a confirmed impact.", label="Anomaly"),
    step("Explain events automatically", "When this is on, opening an event asks the Grok agents why it is happening, once per event. Turn it off to save API credits and use Run Investigation instead.", label="Explain events automatically"),
    step("Explore the globe", "Drag to rotate and scroll to zoom. Every marker is a real event: click one to open it. Colours follow the legend; grey means severity was not assessed.", label="Automatic rotation"),
    step("The event's history", "The chart under the event shows its history: the ocean index over time for El Nino regions, or 30 days of observed water against NOAA's predicted tide and the flood threshold for coastal gauges. Hover for exact values and the source.", selector='[data-testid="stPlotlyChart"]'),
    step("Why is this happening?", "The Grok agents test possible causes against the data they retrieved and mark each supported, not supported or untested, with the evidence for and against. These are hypotheses, not proven causes. If nothing is supported, it says so.", heading="Why is this happening?"),
    step("Run an investigation yourself", "Run Investigation asks the agents to look at the selected event again. Progress appears while they work, and the result is saved for this event during your session.", button="Run Investigation"),
    step("Check the sources", "Every source the agents used is listed with an Open source link, so you can read it yourself. A source without a link says so rather than inventing one.", expander="Sources"),
    step("Overview", "Compare all loaded events and their cards. Comparisons only group matching variables and units.", tab="Overview"),
    step("Climate Explorer", "A larger view of the selected event's history chart and every measured detail: value, baseline, method, date and source.", tab="Climate Explorer"),
    step("Investigation", "The agents' step-by-step progress timeline, and the original measurement next to their conclusion.", tab="Investigation"),
    step("Regional Briefing", "Implications for people and places nearby, confidence, limitations, evidence and recommended next steps. Empty until the event has been investigated.", tab="Regional Briefing"),
]

WORLD = [
    step("Find a place", "Place search finds named places. Coordinates lets you enter any point, including remote areas and oceans. Results describe that point, not a country average.", label="Choose a location by"),
    step("Narrow your search", "Optionally pick a country or territory to narrow matching places, or leave the worldwide option selected.", label="Country or territory"),
    step("Search for a location", "Type at least two characters, then press Enter or click Search locations, and pick a Matching location. With Coordinates, enter a label, latitude and longitude; south and west are negative.", label="City, town, region, or postal code"),
    step("Choose what to look at", "Data view switches between today's weather and the climate history of the place.", label="Data view"),
    step("Choose an observation year", "For climate history, pick a year. Monthly temperature and precipitation are compared with the preceding 30 years; incomplete months stay unknown.", label="Observation year"),
    step("Load observations", "Fetches the place's observations and baseline. It is disabled until a location is chosen.", button="Load climate data"),
    step("Compare climate variables", "After loading, switch between air temperature and precipitation. Missing data and thin baselines are marked.", label="Climate variable"),
    step("Download observations", "Download the daily observations or monthly anomalies as CSV to check the numbers yourself.", button="Download daily observations"),
    step("Choose evidence to investigate", "Pick a month to investigate and review its value, baseline and status first.", label="Observation to investigate"),
    step("Run and read an investigation", "Run Investigation asks the agents to examine that month. Read the findings, limitations and source evidence below. The tour never starts it for you.", button="Run Investigation"),
]

FINISH = step("You're ready to explore", "Reopen Tutorial any time, and try the other monitoring view for its own walkthrough. Check sources, confidence, limitations and sample labels before relying on a result.", selector="h1")

_TUTORIAL = st.components.v2.component(
    "earthwatch_guided_tutorial",
    js=Path(__file__).with_name("tutorial.js").read_text(),
)


# Draws the Tutorial button; each click starts the tour again from the first step.
def tutorial_button(*, sidebar: bool = True) -> None:
    # Bumps the run counter so the browser-side tour restarts.
    def start():
        st.session_state["tutorial_run"] = st.session_state.get("tutorial_run", 0) + 1

    area = st.sidebar if sidebar else st
    area.button("Tutorial" if sidebar else "Start tutorial", icon=":material/help:",
                key="start_tutorial" if sidebar else "start_tutorial_main", on_click=start,
                help="Follow a guided walkthrough of the current monitoring view.")


# Mounts the tour for the open view; it stays hidden until Tutorial is clicked.
def render_tutorial(worldwide: bool) -> None:
    _TUTORIAL(key="earthwatch_tutorial", height=0, data={
        "run": st.session_state.get("tutorial_run", 0),
        "view": "world" if worldwide else "globe",
        "steps": COMMON + (WORLD if worldwide else GLOBE) + [FINISH],
    })
