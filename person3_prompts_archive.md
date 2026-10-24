# Archive: completed Prompts A and B (done, do not paste again)

Kept for reference only. Prompt A produced branch p3-charts, Prompt B produced p3-components.
The current plan is person3_plan.md.

## The goal

A judge opens EarthWatch, picks an anomaly, clicks **Run Investigation**, watches the
real agent progress, opens the evidence, and understands the conclusion without
reading any code. (plan.md: "Definition of done" for Person 3.)

The finished app has four tabs:

1. **Overview**: monitoring status, anomaly cards, region map
2. **Climate Explorer**: SST chart with threshold, highlighted anomaly, replay slider
3. **Investigation**: live agent timeline (expandable steps)
4. **Regional Briefing**: headline, observed vs. inferred, evidence, confidence, next steps, limitations

## Who builds what (no two agents touch the same file)

| Agent | Where it runs | Branch it pushes | Files it may edit |
|---|---|---|---|
| **Agent A: Charts & Map** | any device | `p3-charts` | `dashboard/charts.py`, `dashboard/maps.py`, `tests/test_dashboard_charts.py` |
| **Agent B: Components & Theme** | any device | `p3-components` | `dashboard/components.py`, `dashboard/theme.py`, `.streamlit/config.toml`, `tests/test_dashboard_components.py` |
| **Claude (this VS Code window)** | this Mac | `ALex-Mac-Mini` | `app.py`, `translator.py`, `config.py`, `tests/test_app.py`, `tests/conftest.py`, `tests/test_translator.py` |

Why this is efficient:
- All three agents work at the same time, with no waiting.
- No two agents share a file, so merges can't conflict.
- Every prompt is self-contained, so you paste it once and don't need to explain anything else.
- Agents A and B push their own branches. Claude merges them into `ALex-Mac-Mini`, so you never move files between devices by hand.

---

## Status (2026-10-24)

- [x] Agent B: Components & Theme, pushed as `p3-components` (35d26df) and reviewed
- [x] Agent A: Charts & Map, pushed as `p3-charts` (7ed5504), 10 tests
- [x] Claude: `app.py` four tabs + demo controls + per-anomaly results, 7 new app tests
- [x] All three merged into `ALex-Mac-Mini` and pushed. 80 tests pass and the server boots.
- [ ] YOU: click through it (`streamlit run app.py`)
- [ ] PR `ALex-Mac-Mini` into `main` (tell Claude "open the PR")
- [ ] Integration once Person 1 and Person 2 land code ("pull main")
- [ ] Demo script and rehearsal

## Your steps, in order

### Step 1: start all three at once (about 2 minutes)
1. Paste **Prompt A** into agent #1 (any device).
2. Paste **Prompt B** into agent #2 (any device).
3. Tell Claude here: **"start my part"**.

Both devices need GitHub access to `MasonMakes07/ACM-x-TESC-Hackathon`, either an SSH key or
`gh auth login`. If the agent's first push fails, that's the cause.

### Step 2: when an agent replies that it's done
Tell Claude: **"A pushed"** or **"B pushed"**. Claude fetches the branch, runs `pytest`,
reviews it, merges it into `ALex-Mac-Mini`, and wires it into `app.py`. If something is wrong,
Claude gives you a short fix-up message to paste back to that agent.

### Step 3: click through it yourself
Run `streamlit run app.py`, go through all four tabs, and tell Claude anything that looks wrong.

### Step 4: ship
Tell Claude **"commit and PR"**. Claude pulls `main`, runs `pytest`, pushes `ALex-Mac-Mini`, and
opens a PR into `main`. Post the link in the team chat.

### Step 5: integration
When Person 1 or Person 2 merge into `main`, tell Claude **"pull main"**. The SAMPLE DATA
banners should go away. Demo-ready means no banners and green CI.

### Step 6: rehearse
Ask Claude for a 2-minute demo script, then run it three times.

---

## Prompt A: Charts & Map (paste the whole block)

```
You are a coding agent helping "Person 3 (dashboard)" on the EarthWatch hackathon project:
a Python + Streamlit + Plotly app that shows Pacific sea-surface-temperature (SST) anomalies
and AI agent investigations for northern Peru. Two other agents are working on OTHER files
at the same time, so follow the file rules exactly.

== SETUP (do this first) ==
git clone git@github.com:MasonMakes07/ACM-x-TESC-Hackathon.git earthwatch
  (if SSH fails: gh repo clone MasonMakes07/ACM-x-TESC-Hackathon earthwatch)
cd earthwatch
git checkout main && git pull
git checkout -b p3-charts
python3 -m venv .venv
  macOS/Linux: source .venv/bin/activate      Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest            # must pass before you start
Then read README.md, plan.md section 7, and section 18, plus schemas/anomaly.py and the
current dashboard/charts.py.

== FILE RULES ==
Edit or create ONLY these files:
  dashboard/charts.py, dashboard/maps.py, tests/test_dashboard_charts.py
Do NOT touch app.py, translator.py, schemas/, sample_data/, requirements.txt, or anything
else. Do not add dependencies; plotly, pandas and streamlit are already installed.
Code style: one short comment line above every function, type hints, small functions.

== WHAT TO BUILD ==
These signatures are fixed, because app.py is being written against them right now.

1) dashboard/charts.py
   observation_chart(series: pd.DataFrame, title: str, unit: str,
                     anomaly: AnomalyRecord | None = None,
                     threshold: float | None = None,
                     replay_until: date | None = None) -> go.Figure
   - Backward compatible: observation_chart(series, title, unit) must still work.
   - series has columns "date" (datetime64) and "value" (float, may contain NaN).
   - replay_until: plot only rows with date <= replay_until (historical replay).
   - threshold: dashed, labelled horizontal lines at +threshold and -threshold.
   - anomaly (schemas.anomaly.AnomalyRecord, which has observation_date, value, unit and
     source): highlight that date with a large marker plus an annotation showing value and
     unit. Skip it if the date is outside the plotted range.
   - Hover shows date, value with unit, and "Source: <anomaly.source>" when an anomaly is given.
   - Styling: template "plotly_dark", transparent paper and plot backgrounds.
   - Empty series, or nothing left after replay_until: return a figure with a centered
     "No observations in this period" annotation. Never raise.

2) dashboard/maps.py
   REGION_BOXES: dict[str, tuple[float, float, float, float]]
       # name -> (lat_min, lat_max, lon_min, lon_max)
       {"Nino 1+2": (-10, 0, -90, -80), "Nino 3.4": (-5, 5, -170, -120)}
   PERU_LOCATIONS: dict[str, tuple[float, float]]
       # Piura, Tumbes, Chiclayo, Trujillo -> (lat, lon)
   region_map(selected_region: str | None = None) -> go.Figure
   - Plotly go.Scattergeo, centered on the eastern tropical Pacific and northern Peru.
   - Every box drawn as a closed outline. The selected region is filled and highlighted;
     the others are dim. None or an unknown region: draw all of them dim and don't raise.
   - Peru locations as labelled markers. Dark styling to match the charts.

3) tests/test_dashboard_charts.py (pytest, no network)
   - the backward-compatible call works
   - replay_until removes later points
   - the anomaly marker is present when in range and absent when out of range
   - threshold adds two lines
   - an empty series gives the "No observations" annotation
   - region_map highlights the selected region and doesn't raise for an unknown region

== FINISH ==
pytest                                  # the whole repo must pass
git add dashboard/charts.py dashboard/maps.py tests/test_dashboard_charts.py
git commit -m "Dashboard: SST chart with replay/threshold/anomaly marker, region map"
git push -u origin p3-charts
Do NOT merge, do NOT open a PR, and do NOT push to main or any other branch.
Reply with: the branch name, the test result line, and at most 5 bullets of decisions.
```

## Prompt B: Components & Theme (paste the whole block)

```
You are a coding agent helping "Person 3 (dashboard)" on the EarthWatch hackathon project:
a Python + Streamlit + Plotly app that shows Pacific sea-surface-temperature (SST) anomalies
and AI agent investigations for northern Peru. Two other agents are working on OTHER files
at the same time, so follow the file rules exactly.

== SETUP (do this first) ==
git clone git@github.com:MasonMakes07/ACM-x-TESC-Hackathon.git earthwatch
  (if SSH fails: gh repo clone MasonMakes07/ACM-x-TESC-Hackathon earthwatch)
cd earthwatch
git checkout main && git pull
git checkout -b p3-components
python3 -m venv .venv
  macOS/Linux: source .venv/bin/activate      Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest            # must pass before you start
Then read README.md, plan.md section 2 ("Person 3", Task 2), section 7, and section 18, plus
schemas/anomaly.py, schemas/assessment.py, sample_data/anomalies.json and
sample_data/assessment.json.

== FILE RULES ==
Edit or create ONLY these files:
  dashboard/components.py, dashboard/theme.py, .streamlit/config.toml,
  tests/test_dashboard_components.py
Do NOT touch app.py, translator.py, schemas/, sample_data/, requirements.txt, or anything
else. Do not add dependencies.
Code style: one short comment line above every function, type hints, small functions.

== THE LOOK ==
A dark, satellite-inspired "climate intelligence workstation", not a chatbot. It must stay
readable.

== WHAT TO BUILD ==
These signatures are fixed, because app.py is being written against them right now.
Every render function draws with streamlit (st.*) and returns None.

dashboard/theme.py
  apply_theme() -> None
      # inject a compact CSS block via st.markdown(..., unsafe_allow_html=True)
.streamlit/config.toml
  [theme] base = "dark", plus primaryColor, backgroundColor, secondaryBackgroundColor, textColor

dashboard/components.py   (import models from schemas.anomaly and schemas.assessment)
  confidence_color(level: str) -> str
      # pure: hex color for "high", "moderate", "low", "inconclusive"; gray for anything else
  evidence_badge(evidence_type: str) -> str
      # pure: short label + emoji for "measured", "reported", "inferred", "uncertain";
      # a neutral badge for anything else
  status_strip(anomalies: list[AnomalyRecord], is_sample: bool) -> None
      # one st.metric per region showing its status (detected / monitoring / inconclusive),
      # a visible "Data as of <latest observation_date>", and "(sample data)" when is_sample
  anomaly_card(anomaly: AnomalyRecord, selected: bool = False) -> None
      # compact bordered card: region, variable, value + unit, date, status pill
  anomaly_detail(anomaly: AnomalyRecord) -> None
      # variable, region, observed value + unit, baseline period, detection method,
      # observation date, source
  investigation_timeline(events: list[ProgressEvent]) -> None
      # one st.expander per event, titled "HH:MM:SS  <agent>", with the message inside.
      # Empty list: st.info("No investigation run yet. Click Run Investigation.")
  evidence_list(evidence: list[EvidenceItem]) -> None
      # one expander per item: badge + claim; inside: source, source_date ("undated" if
      # None), limitations, and a link when url is set. Order: measured, reported,
      # inferred, uncertain.
  briefing(assessment: Assessment, anomaly: AnomalyRecord) -> None
      # headline = assessment.summary
      # "What we observed": measured facts from the anomaly + the measured evidence
      # "Why it matters": regional_implications, labelled as POTENTIAL, not confirmed
      # supporting_findings vs contradictory_findings side by side (st.columns)
      # confidence with a colored badge (confidence_color)
      # recommended_next_steps, limitations
      # evidence section uses evidence_list

tests/test_dashboard_components.py (pytest, no network)
  - unit tests for confidence_color and evidence_badge, including unknown values
  - smoke tests with streamlit.testing.v1.AppTest.from_function for every render function,
    using records loaded from sample_data/*.json; assert no exception and that the key text
    is shown

== FINISH ==
pytest                                  # the whole repo must pass
git add dashboard/components.py dashboard/theme.py .streamlit/config.toml tests/test_dashboard_components.py
git commit -m "Dashboard: dark theme, anomaly cards/detail, timeline, evidence, briefing"
git push -u origin p3-components
Do NOT merge, do NOT open a PR, and do NOT push to main or any other branch.
Reply with: the branch name, the test result line, and at most 5 bullets of decisions.
```

---

## Claude's own task list (nothing for you to paste)

1. Set up `.venv` and confirm `pytest` passes. Done: 47 passed.
2. `app.py`: `st.tabs` with the four tabs, plus sidebar demo controls (region, anomaly, replay date
   slider, threshold). **Run Investigation** stays the first button and saves its progress
   events and the assessment in `st.session_state`.
3. Merge `p3-charts` and `p3-components` into `ALex-Mac-Mini` as they land, and wire them in.
4. Extend `tests/test_app.py` to cover the tabs, the controls, and a crashing backend.
5. Commit, push, and open the PR into `main`.
