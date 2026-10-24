"""Climate Investigator agent: gathers evidence for a detected anomaly.

Owner: Person 2 (Grok Agent Intelligence).
"""

from agents.agent_models import InvestigationReport
from agents.prompts import INVESTIGATOR_PROMPT
from agents.runner import ChatClient, ProgressCallback, emit, run_agent
from agents.toolbox import AgentToolbox
from schemas.anomaly import AnomalyRecord

AGENT_NAME = "Climate Investigator"
TOOL_NAMES = ("get_climate_observations", "fetch_official_source")


# Investigates the evidence behind one anomaly and returns a structured report.
def investigate(
    client: ChatClient,
    toolbox: AgentToolbox,
    anomaly: AnomalyRecord,
    on_progress: ProgressCallback,
) -> InvestigationReport:
    emit(on_progress, AGENT_NAME, "Checking measurements and official context.")
    user_prompt = (
        f"As-of date: {toolbox.as_of_date.isoformat()}\n"
        f"Detected anomaly record:\n{anomaly.model_dump_json(indent=2)}"
    )
    return run_agent(
        client,
        agent_name=AGENT_NAME,
        system_prompt=INVESTIGATOR_PROMPT,
        user_prompt=user_prompt,
        output_model=InvestigationReport,
        on_progress=on_progress,
        toolbox=toolbox,
        tool_names=TOOL_NAMES,
    )
