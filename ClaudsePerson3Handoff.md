# Person 3 (Product & Dashboard) - Work Summary

Branch: `Alex` (based on `main` at `597f585 skeleton`). Commits: `c7b15ea`, `2ffda55`.
Scope: only Person 3 files were touched. `schemas/`, `sample_data/`, `requirements.txt`,
`data/`, `analysis/` and `agents/` are unchanged.

## What was built

A four-tab Streamlit dashboard that runs today on sample data and switches to live
data automatically when Person 1 and Person 2 implement their entry functions.

| Tab | Contents |
|---|---|
| Overview | Signals monitored, anomalies detected, strongest signal, anomaly cards, bar chart of every anomaly vs the +/-0.5 neutral band |
| Climate Explorer | Anomaly detail (variable, region, value, date, baseline, method, source, status) and a time-series chart with the selected anomaly marked |
| Investigation | Agent progress timeline, original observation vs agent conclusion, confidence, supporting/contradictory findings, limitations, next steps, expandable evidence list with provenance and source links |
| Regional Impact | World map (selected region highlighted) plus the assessment's regional implications |

Sidebar controls: region multiselect, historical period, anomaly selector,
**Run Investigation** (calls the real backend and streams real progress events),
and **Run guided demo** (resets filters, selects the strongest anomaly, runs it - a
repeatable demo path).

Results are kept in `st.session_state["results"]` keyed by anomaly id, so switching
tabs or filters does not lose a finished investigation.

## Files changed

- `app.py` - tabs, sidebar controls, investigation runner, guided demo.
- `dashboard/charts.py` - `observation_chart` (threshold band + highlighted anomaly), `anomaly_comparison_chart`, `ENSO_THRESHOLD = 0.5`.
- `dashboard/components.py` - `anomaly_card`, `anomaly_detail`, `progress_timeline`, `evidence_list`, `assessment_view`, `show_sample_banner`, `anomaly_label`.
- `dashboard/maps.py` - world map (`REGION_BOUNDS` for 7 ocean regions, `CONTEXT_LOCATIONS` for commonly ENSO-affected areas worldwide; unknown regions are not highlighted but never crash).
- `translator.py` - region validation changed from a two-region allow-list to `REGION_PATTERN` (`^[A-Za-z0-9 +._-]{1,64}$`) so any global region passes.
- `tests/test_app.py`, `tests/test_dashboard.py`, `tests/test_translator.py` - 51 tests total, all passing.

## Backend contract (unchanged)

The UI talks only to `translator.py`:

- `load_anomalies() -> (list[AnomalyRecord], is_sample)`
- `load_observation_series(region) -> (DataFrame[date, value], is_sample)`
- `investigate_anomaly(anomaly_id, on_progress) -> (Assessment, is_sample)`

Stub workstreams raise `NotImplementedError`, which the translator turns into sample
data plus a visible SAMPLE DATA banner. Real failures become `TranslatorError` and show
as an error message, never a stack trace.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/streamlit run app.py
.venv/bin/python -m pytest        # 51 passed
```

## Notes for whoever merges or continues

- **Global scope:** the product is no longer Peru-specific. Remaining Peru wording is in
  `README.md` line 5 and `sample_data/assessment.json` (shared file, needs team agreement).
- **Person 1 dependency:** real data is still limited to the Nino regions until
  `get_sst_series` / `detect_anomalies` cover other regions. The dashboard displays
  whatever they return.
- **Context markers** on the map (Indonesia, Horn of Africa, etc.) come from general
  ENSO knowledge, not a cited source; verify before presenting.
- **Tests:** the app tests locate the run button by label (`Run Investigation`), not by
  index, because sidebar buttons come first.
- **Map tiles:** OpenStreetMap (CartoDB tiles now need an API key).
- **Not done yet:** visual polish pass, final presentation, re-verifying against live
  Person 1 / Person 2 output once they land.

## Merging

```bash
git fetch origin
git merge Alex        # or: git cherry-pick c7b15ea 2ffda55
```
Conflicts are only likely in `translator.py` (one line) and `tests/test_translator.py`.
