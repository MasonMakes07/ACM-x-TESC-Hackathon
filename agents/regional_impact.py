"""Regional Impact Analyst agent: assesses implications for Piura and Tumbes.

Owner: Person 2 (Grok Agent Intelligence).
"""

from agents.agent_models import ImpactReport, InvestigationReport
from agents.prompts import REGIONAL_IMPACT_PROMPT
from agents.runner import ChatClient, ProgressCallback, emit, run_agent
from agents.toolbox import AgentToolbox
from schemas.anomaly import AnomalyRecord

AGENT_NAME = "Regional Impact Analyst"
TOOL_NAMES = ("get_rainfall_history", "get_regional_context", "fetch_official_source")


# Assesses qualified regional implications of the investigated anomaly.
def assess_regional_impact(
    client: ChatClient,
    toolbox: AgentToolbox,
    anomaly: AnomalyRecord,
    investigation: InvestigationReport,
    on_progress: ProgressCallback,
) -> ImpactReport:
    emit(on_progress, AGENT_NAME, "Examining rainfall and context for Piura, Tumbes.")
    user_prompt = (
        f"As-of date: {toolbox.as_of_date.isoformat()}\n"
        f"Detected anomaly record:\n{anomaly.model_dump_json(indent=2)}\n"
        f"Climate Investigator report:\n{investigation.model_dump_json(indent=2)}"
    )
    return run_agent(
        client,
        agent_name=AGENT_NAME,
        system_prompt=REGIONAL_IMPACT_PROMPT,
        user_prompt=user_prompt,
        output_model=ImpactReport,
        on_progress=on_progress,
        toolbox=toolbox,
        tool_names=TOOL_NAMES,
    )
