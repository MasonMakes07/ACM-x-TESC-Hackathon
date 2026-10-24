# EarthWatch — ACM x TESC Hackathon

AI-powered climate intelligence: detect Pacific ocean anomalies, investigate the
evidence with Grok agents, and present an evidence-traceable regional assessment
for northern Peru. Full plan: [plan.md](plan.md). Team workflow: plan.md section 18.

## Setup (once per teammate)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in XAI_API_KEY and XAI_MODEL
```

## Run

```bash
streamlit run app.py        # the dashboard
pytest                      # run before every push
```

Unbuilt parts automatically show **SAMPLE DATA** banners, so the app runs from
day one. Each banner disappears when its owner implements their entry function.

## Who owns what

| Owner | Files | Entry function the app calls |
|---|---|---|
| Person 1 — Climate | `data/`, `analysis/`, `tests/test_anomalies.py` | `detect_anomalies()`, `get_sst_series(region)` |
| Person 2 — Agents | `agents/`, `tests/test_agents.py` | `run_investigation(anomaly, on_progress)` |
| Person 3 — Product | `app.py`, `dashboard/`, `translator.py`, `config.py`, other tests | — |
| Whole team | `schemas/`, `sample_data/`, `requirements.txt` | change only after agreeing |
