"""Live smoke checks for the Grok integration and the real data tools.

Owner: Person 2 (Grok Agent Intelligence).
Usage:  python -m agents.live_check --tools   # real data tools only (no API key)
        python -m agents.live_check           # Grok access + structured JSON
        python -m agents.live_check --full    # also run a full Pacific investigation
        python -m agents.live_check --full --local   # ...for a worldwide location
The automated tests never call this; it exists to confirm real data and credentials.
"""

import argparse
import json
import sys

from agents.agent_errors import AgentOutputError, GrokError
from agents.agent_models import VerificationReport
from agents.context import build_context, infer_as_of_date
from agents.grok_client import GrokClient
from agents.ledger import EvidenceLedger
from agents.runner import run_agent
from agents.sentinel import monitor
from agents.toolbox import OFFICIAL_SOURCES, AgentToolbox
from agents.workflow import run_investigation
from schemas.anomaly import AnomalyRecord

PACIFIC_ANOMALY = dict(
    anomaly_id="live_check_pacific",
    variable="sea_surface_temperature_anomaly",
    region="Nino 1+2",
    observation_date="2017-03-01",
    value=1.83,
    unit="degC",
    baseline_period="1991-2020",
    source="https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
    detection_method="published_anomaly_index",
    status="detected",
)
LOCAL_ANOMALY = dict(
    anomaly_id="live_check_local",
    variable="Monthly precipitation total",
    region="Nairobi, Kenya (-1.2864, 36.8172)",
    observation_date="2023-04-01",
    value=112.4,
    unit="mm/month",
    baseline_period="1993-2022",
    source="https://archive-api.open-meteo.com/v1/archive",
    detection_method="LIVE CHECK - ERA5 value, not an EarthWatch detection result",
    status="monitoring",
)
RESULT_PREVIEW_CHARS = 600


# Prints each real progress event as it happens.
def print_event(event) -> None:
    print(f"  {event.timestamp:%H:%M:%S} [{event.agent}] {event.message}")


# Runs one tool against real data and prints a short preview of its result.
def print_tool_result(toolbox: AgentToolbox, tool_name: str, arguments: dict) -> None:
    raw_result = toolbox.execute(tool_name, arguments)
    result = json.loads(raw_result)
    print(f"\n{tool_name}: {result['status']}")
    if result["status"] != "ok":
        print(f"  {result.get('reason') or result.get('message')}")
        return
    print(f"  source: {result.get('source')}")
    print(
        f"  retrieved_at: {result.get('retrieved_at')}"
        f"  stale: {result.get('cache_stale')}"
    )
    preview_keys = ("summary", "temperature_summary_degC", "precipitation_summary_mm")
    for key in preview_keys:
        if key in result:
            print(f"  {key}: {json.dumps(result[key])[:RESULT_PREVIEW_CHARS]}")
    if "monthly" in result:
        print(f"  last month: {json.dumps(result['monthly'][-1])}")


# Exercises every real data tool for both anomaly types, without calling Grok.
def check_data_tools() -> int:
    pacific = AnomalyRecord(**PACIFIC_ANOMALY)
    local = AnomalyRecord(**LOCAL_ANOMALY)
    pacific_box = AgentToolbox(EvidenceLedger(), infer_as_of_date(pacific))
    local_box = AgentToolbox(EvidenceLedger(), infer_as_of_date(local))
    print("== Pacific record (NOAA SST + Peru rainfall + official text) ==")
    print_tool_result(
        pacific_box,
        "get_climate_observations",
        {"region": "Nino 1+2", "start_date": "2016-03-01", "end_date": "2017-03-01"},
    )
    print_tool_result(
        pacific_box,
        "get_rainfall_history",
        {"location": "Piura", "start_date": "2017-01-01", "end_date": "2017-03-31"},
    )
    for source_id in OFFICIAL_SOURCES:
        print_tool_result(
            pacific_box, "fetch_official_source", {"source_id": source_id}
        )
    print("\n== Worldwide record (ERA5 at coordinates) ==")
    print_tool_result(
        local_box,
        "get_local_weather",
        {
            "latitude": -1.2864,
            "longitude": 36.8172,
            "start_date": "2022-04-01",
            "end_date": "2023-04-30",
        },
    )
    print("\n== Sentinel Bot (code re-check of each record) ==")
    for record, box in ((pacific, pacific_box), (local, local_box)):
        monitor(box, record, build_context(record), print_event)
    print("\nLedger (Pacific):", [source.name for source in pacific_box.ledger.sources])
    print("Unavailable (Pacific):", pacific_box.ledger.unavailable or "none")
    print("Ledger (local):", [source.name for source in local_box.ledger.sources])
    print("Unavailable (local):", local_box.ledger.unavailable or "none")
    return 0


# Confirms Grok answers and returns schema-valid structured JSON.
def check_structured_output(client: GrokClient) -> None:
    result = run_agent(
        client,
        agent_name="Live check",
        system_prompt="You verify a trivial claim. Be brief.",
        user_prompt="Claim: 'Water boils at 100 C at sea level.' Review it.",
        output_model=VerificationReport,
        on_progress=print_event,
    )
    print("Structured output OK:", result.verdict)


# Runs the whole pipeline on a sample anomaly and prints the Assessment.
def check_full_investigation(client: GrokClient, use_local: bool) -> None:
    anomaly = AnomalyRecord(**(LOCAL_ANOMALY if use_local else PACIFIC_ANOMALY))
    assessment = run_investigation(anomaly, print_event, client=client)
    print(json.dumps(assessment.model_dump(mode="json"), indent=2))


# Runs the requested live checks and returns a process exit code.
def main() -> int:
    parser = argparse.ArgumentParser(description="Live smoke checks")
    parser.add_argument("--tools", action="store_true", help="check data tools only")
    parser.add_argument("--full", action="store_true", help="run a full investigation")
    parser.add_argument("--local", action="store_true", help="use a worldwide record")
    arguments = parser.parse_args()
    if arguments.tools:
        return check_data_tools()
    try:
        client = GrokClient()
        check_structured_output(client)
        if arguments.full:
            check_full_investigation(client, arguments.local)
    except (RuntimeError, GrokError, AgentOutputError) as error:
        print(f"Live check failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
