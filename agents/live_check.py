"""Live smoke check for the Grok integration (needs a real key in .env).

Owner: Person 2 (Grok Agent Intelligence).
Usage:  python -m agents.live_check          # API access + structured JSON only
        python -m agents.live_check --full   # also run a full sample investigation
The automated tests never call this; it exists to confirm real credentials work.
"""

import argparse
import json
import sys

from agents.agent_errors import AgentOutputError, GrokError
from agents.agent_models import VerificationReport
from agents.grok_client import GrokClient
from agents.runner import run_agent
from agents.workflow import run_investigation
from schemas.anomaly import AnomalyRecord


# Prints each real progress event as it happens.
def print_event(event) -> None:
    print(f"  {event.timestamp:%H:%M:%S} [{event.agent}] {event.message}")


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


# Runs the whole pipeline on a hard-coded anomaly and prints the Assessment.
def check_full_investigation(client: GrokClient) -> None:
    anomaly = AnomalyRecord(
        anomaly_id="live_check_001",
        variable="sea_surface_temperature_anomaly",
        region="Nino 1+2",
        observation_date="2023-06-01",
        value=2.8,
        unit="degC",
        baseline_period="1991-2020",
        source="LIVE CHECK - illustrative value, not a measurement",
        detection_method="published_anomaly_index",
        status="detected",
    )
    assessment = run_investigation(anomaly, print_event, client=client)
    print(json.dumps(assessment.model_dump(mode="json"), indent=2))


# Runs the requested live checks and returns a process exit code.
def main() -> int:
    parser = argparse.ArgumentParser(description="Live Grok smoke check")
    parser.add_argument("--full", action="store_true", help="run a full investigation")
    arguments = parser.parse_args()
    try:
        client = GrokClient()
        check_structured_output(client)
        if arguments.full:
            check_full_investigation(client)
    except (RuntimeError, GrokError, AgentOutputError) as error:
        print(f"Live check failed: {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
