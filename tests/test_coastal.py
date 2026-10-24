"""Coastal water-level events: data, detection, translator, agents and dashboard.

Owner: Person 3 (Product & Dashboard). No network: NOAA and Open-Meteo calls are faked.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

import translator
from agents import workflow
from agents.coastal_tools import CoastalToolbox
from agents.context import build_context, coastal_station, infer_as_of_date, is_coastal_water_level
from agents.ledger import EvidenceLedger
from analysis import coastal_detection
from analysis.coastal_detection import COASTAL_VARIABLE, classify, station_event
from data import coastal_sources
from data.coastal_sources import StationLevels

APP = str(Path(__file__).resolve().parents[1] / "app.py")
STATION = "9410170"
PAGE = coastal_sources.station_page(STATION)


# Builds 72 hours of 6-minute levels with a steady +0.30 m residual and a peak at 15:18.
def _levels(residual=0.30) -> pd.DataFrame:
    times = pd.date_range("2026-10-22 00:00", periods=720, freq="6min", tz="UTC")
    predicted = pd.Series(range(720), dtype="float64").mod(124).sub(62).abs().mul(-0.012).add(0.2).to_numpy()
    frame = pd.DataFrame({"time": times, "predicted_m": predicted})
    frame["observed_m"] = frame["predicted_m"] + residual
    peak = frame.index[frame["time"] == pd.Timestamp("2026-10-24 15:18", tz="UTC")][0]
    frame.loc[peak, "observed_m"] = 0.633
    frame["residual_m"] = (frame["observed_m"] - frame["predicted_m"]).round(3)
    return frame[["time", "observed_m", "predicted_m", "residual_m"]]


# Wraps levels as the data layer returns them.
def _station(levels=None, minor=0.569) -> StationLevels:
    return StationLevels(
        station=STATION, name="San Diego, CA", latitude=32.7156, longitude=-117.1767,
        levels=_levels() if levels is None else levels, minor_flood_m=minor,
        source=PAGE, retrieved_at="2026-10-24T21:00:00+00:00", stale=False,
    )


# The record the detector produces for the fake San Diego data.
def _record():
    return station_event(_station())


# ---------------------------------------------------------------------------- data

# Parses NOAA observed and predicted JSON into aligned levels and a residual.
def test_station_levels_parse_noaa_json(monkeypatch):
    def fake_fetch(url, params=None, **kwargs):
        if "floodlevels" in url:
            return json.dumps({"nos_minor": 11.38}), "t", False
        if "datums" in url:
            return json.dumps({"datums": [{"name": "MHHW", "value": 2.9}]}), "t", False
        if params["product"] == "water_level":
            return json.dumps({"metadata": {"lat": "32.7156", "lon": "-117.1767"},
                               "data": [{"t": "2026-10-24 15:18", "v": "0.633"},
                                        {"t": "2026-10-24 15:24", "v": ""}]}), "2026-10-24T21:00Z", False
        return json.dumps({"predictions": [{"t": "2026-10-24 15:18", "v": "0.167"}]}), "t", False

    monkeypatch.setattr(coastal_sources, "fetch_text", fake_fetch)
    data = coastal_sources.get_station_levels(STATION, datetime(2026, 10, 24, tzinfo=timezone.utc),
                                              datetime(2026, 10, 25, tzinfo=timezone.utc))
    assert len(data.levels) == 1  # the blank reading is dropped, never filled in
    assert data.levels["residual_m"].iloc[0] == pytest.approx(0.466)
    assert data.minor_flood_m == pytest.approx(11.38 * 0.3048 - 2.9, abs=0.001)
    assert data.source == PAGE


# NOAA error payloads and unsupported stations raise instead of returning empty data.
def test_station_levels_refuse_errors_and_unknown_stations(monkeypatch):
    monkeypatch.setattr(coastal_sources, "fetch_text",
                        lambda *a, **k: (json.dumps({"error": {"message": "No data"}}), "t", False))
    window = (datetime(2026, 10, 24, tzinfo=timezone.utc), datetime(2026, 10, 25, tzinfo=timezone.utc))
    with pytest.raises(ValueError, match="No data"):
        coastal_sources.get_station_levels(STATION, *window)
    with pytest.raises(ValueError, match="Unsupported"):
        coastal_sources.get_station_levels("0000000", *window)


# ----------------------------------------------------------------------- detection

# Classification: flood threshold or a big residual is detected; a modest residual is monitoring.
def test_classify_thresholds():
    assert classify(0.60, 0.10, 0.569) == "detected"
    assert classify(0.20, 0.35, 0.569) == "detected"
    assert classify(0.20, 0.20, None) == "monitoring"
    assert classify(0.20, 0.05, 0.569) is None


# The record describes the highest water and the residual there, with provenance.
def test_station_event_describes_the_highest_water():
    record = _record()
    assert record.variable == COASTAL_VARIABLE
    assert record.region == "San Diego, CA (32.7156, -117.1767)"
    assert record.observation_date == date(2026, 10, 24)
    assert record.value == pytest.approx(0.633 - _levels().set_index("time").loc[
        pd.Timestamp("2026-10-24 15:18", tz="UTC"), "predicted_m"], abs=0.001)
    assert record.status == "detected"
    assert record.source == PAGE
    assert "minor high-tide-flooding threshold" in record.detection_method


# A quiet gauge produces no event; one failing gauge never hides the others.
def test_quiet_and_failing_stations(monkeypatch):
    quiet = _levels(residual=0.0)
    quiet["observed_m"] = quiet["predicted_m"]
    quiet["residual_m"] = 0.0
    assert station_event(_station(quiet)) is None

    def recent(station, hours, now):
        if station == STATION:
            return _station()
        raise ConnectionError("gauge offline")

    monkeypatch.setattr(coastal_detection, "get_recent_levels", recent)
    events = coastal_detection.detect_coastal_events()
    assert [item.anomaly_id for item in events] == [_record().anomaly_id]


# ---------------------------------------------------------------------- translator

# The globe gets climate-pipeline events plus coastal events, and coastal failures are isolated.
def test_load_events_merges_and_isolates_failures(stubbed_backend):
    stubbed_backend.setattr(translator.coastal_detection, "detect_coastal_events", lambda: [_record()])
    events, is_sample = translator.load_events()
    assert is_sample
    assert events[-1].variable == COASTAL_VARIABLE
    assert len(events) == len(translator.load_anomalies()[0]) + 1

    def offline():
        raise ConnectionError("NOAA down")

    stubbed_backend.setattr(translator.coastal_detection, "detect_coastal_events", offline)
    assert len(translator.load_events()[0]) == len(translator.load_anomalies()[0])


# A coastal event can be investigated by id (it is found among all events).
def test_coastal_event_is_investigable(stubbed_backend):
    stubbed_backend.setattr(translator.coastal_detection, "detect_coastal_events", lambda: [_record()])
    assessment, is_sample = translator.investigate_anomaly(_record().anomaly_id, lambda event: None)
    assert assessment.anomaly_id == _record().anomaly_id


# --------------------------------------------------------------------------- agents

# The agents recognise a coastal record, its station, coordinates and as-of day.
def test_context_recognises_coastal_records():
    record = _record()
    assert is_coastal_water_level(record)
    assert coastal_station(record) == STATION
    assert build_context(record).latitude == 32.7156
    assert infer_as_of_date(record) == date(2026, 10, 24)


# The coastal tools return real fields, record provenance and refuse hindsight.
def test_coastal_tools_return_levels_and_refuse_hindsight(monkeypatch):
    monkeypatch.setattr(coastal_sources, "get_station_levels", lambda station, start, end: _station())
    weather = pd.DataFrame({"time": pd.date_range("2026-10-23", periods=48, freq="h", tz="UTC"),
                            "wind_speed_kmh": 12.0, "wind_direction_deg": 270.0, "pressure_msl_hpa": 1015.0})
    monkeypatch.setattr(coastal_sources, "get_coastal_weather", lambda *a: (weather, "t", False))
    ledger = EvidenceLedger()
    tools = CoastalToolbox(ledger, date(2026, 10, 24), STATION, 32.7156, -117.1767)
    water = json.loads(tools.execute("get_coastal_water_level", {"start_date": "2026-10-22", "end_date": "2026-10-24"}))
    assert water["status"] == "ok"
    assert water["highest_water"]["observed_m"] == pytest.approx(0.633)
    assert water["minor_flood_threshold_m"] == pytest.approx(0.569)
    assert water["url"] == PAGE
    wind = json.loads(tools.execute("get_coastal_weather", {"start_date": "2026-10-23", "end_date": "2026-10-24"}))
    assert wind["lowest_pressure"]["pressure_msl_hpa"] == 1015.0
    assert {source.name for source in ledger.sources} == {water["source"], wind["source"]}
    future = json.loads(tools.execute("get_coastal_water_level", {"start_date": "2026-11-01", "end_date": "2026-11-02"}))
    assert future["status"] == "error"


# A failed gauge request becomes an explicit unavailable result, never invented data.
def test_coastal_tool_unavailable_when_noaa_fails(monkeypatch):
    def down(*a):
        raise ConnectionError("down")

    monkeypatch.setattr(coastal_sources, "get_station_levels", down)
    ledger = EvidenceLedger()
    tools = CoastalToolbox(ledger, date(2026, 10, 24), STATION, 32.7156, -117.1767)
    result = json.loads(tools.execute("get_coastal_water_level", {"start_date": "2026-10-24", "end_date": "2026-10-24"}))
    assert result["status"] == "unavailable"
    assert ledger.unavailable


# Fake Grok that answers each bot from a queue, chosen by its system prompt.
class _Script:
    def __init__(self, scripts):
        self.scripts = {key: list(value) for key, value in scripts.items()}
        self.prompts = []

    def chat(self, messages, tools=None):
        system = messages[0]["content"]
        self.prompts.append((system, [tool["function"]["name"] for tool in tools or []]))
        for marker, queue in self.scripts.items():
            if marker in system:
                if not queue:
                    raise AssertionError(f"No scripted reply left for {marker!r}: {self.prompts[-1][1]}")
                return queue.pop(0)
        raise AssertionError("Unexpected agent")


# Builds a chat reply carrying a JSON payload or tool calls.
def _reply(payload=None, calls=()):
    if calls:
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"c{index}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}
            for index, (name, args) in enumerate(calls)]}
    return {"role": "assistant", "content": json.dumps(payload)}


# A coastal investigation uses the coastal prompt and tools, and cites the gauge with a link.
def test_full_coastal_investigation(monkeypatch):
    monkeypatch.setattr(coastal_sources, "get_station_levels", lambda station, start, end: _station())
    weather = pd.DataFrame({"time": pd.date_range("2026-10-15", periods=24 * 10, freq="h", tz="UTC"),
                            "wind_speed_kmh": 10.0, "wind_direction_deg": 250.0, "pressure_msl_hpa": 1016.0})
    monkeypatch.setattr(coastal_sources, "get_coastal_weather", lambda *a: (weather, "t", False))
    gauge = "NOAA CO-OPS San Diego, CA tide gauge 9410170 water levels"
    window = {"start_date": "2026-10-15", "end_date": "2026-10-24"}
    investigation = {
        "summary": "Highest water combined a modest predicted tide with a sustained +0.45 m residual.",
        "evidence": [{"claim": "Residual averaged about +0.45 m for three days.", "source": gauge,
                      "evidence_type": "measured", "source_date": "2026-10-24"}],
        "supporting_findings": ["The residual was sustained, not a short spike."],
        "contradictory_findings": [],
        "alternative_explanations": [
            {"explanation": "A persistent ocean-scale sea-level anomaly.", "evidence_for": "Residual steady for days.",
             "evidence_against": "", "status": "supported"},
            {"explanation": "Wind-driven storm surge.", "evidence_for": "",
             "evidence_against": "Winds stayed near 10 km/h.", "status": "unsupported"},
        ],
        "open_questions": ["How much is long-term sea-level rise?"],
        "proposed_confidence": "moderate",
    }
    impact = {"regional_implications": ["Low-lying waterfront areas could see minor flooding at high tide."],
              "exposures": [], "limitations": [], "recommended_next_steps": ["Check NOAA Tides & Currents."]}
    client = _Script({
        "You are the Investigator Bot": [_reply(calls=[("get_coastal_water_level", window),
                                                       ("get_coastal_weather", window)]), _reply(investigation)],
        "You are the Impact Bot": [_reply(impact)],
        "You are the Skeptic / Verifier": [_reply({"verdict": "accept", "issues": [], "confidence_cap": "moderate",
                                                   "limitations": []})],
        "You are the Action Bot": [_reply({
            "alert_level": "monitor", "alert_headline": "High water under watch at San Diego",
            "alert_message": "Water stood above the predicted tide; confidence is moderate.",
            "report": "The gauge measured a sustained residual; alternatives remain open.",
            "contingency_plan": [{"trigger": "Residual persists through the next high tide",
                                  "action": "Re-run the investigation", "rationale": "Persistence matters"}],
            "monitoring_triggers": ["NWS coastal flood advisory issued"],
        })],
    })
    events = []
    assessment = workflow.run_investigation(_record(), events.append, client=client)
    investigator_prompt, investigator_tools = client.prompts[0]
    assert "COASTAL WATER LEVEL" in investigator_prompt
    assert set(investigator_tools) == {"get_coastal_water_level", "get_coastal_weather", "fetch_official_source"}
    cited = [item for item in assessment.evidence if item.source == gauge]
    assert cited and cited[0].url == PAGE and cited[0].evidence_type == "measured"
    assert any("persistent ocean-scale" in item for item in assessment.contradictory_findings)
    assert any("one NOAA tide gauge" in item for item in assessment.limitations)
    assert any("reproduces the record" in event.message for event in events)


# ------------------------------------------------------------------------ dashboard

# A coastal event shows up, can be selected like a globe click, and shows its gauge history.
def test_coastal_event_is_selectable_and_shows_history(stubbed_backend):
    stubbed_backend.setattr(translator.coastal_detection, "detect_coastal_events", lambda: [_record()])
    stubbed_backend.setattr(translator, "load_coastal_history", lambda anomaly, days=30: (_levels(), 0.569))
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["auto_explain"] = False
    app.run()
    assert not app.exception
    region = _record().region
    assert "San Diego, CA" in app.sidebar.selectbox(key="region_select").options  # shown without coordinates
    app.session_state["region_select"] = region
    app.run()
    assert not app.exception
    assert any(item.value.startswith("San Diego, CA: ") for item in app.subheader)
    assert app.get("plotly_chart")


# The page opens on the most notable event: a detected one, most recent first.
def test_page_opens_on_the_most_notable_event(stubbed_backend):
    stubbed_backend.setattr(translator.coastal_detection, "detect_coastal_events", lambda: [_record()])
    stubbed_backend.setattr(translator, "load_coastal_history", lambda anomaly, days=30: (_levels(), 0.569))
    app = AppTest.from_file(APP, default_timeout=30)
    app.session_state["auto_explain"] = False
    app.run()
    assert app.sidebar.selectbox(key="region_select").value == _record().region
