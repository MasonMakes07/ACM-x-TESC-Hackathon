"""Runs the Investigator -> Regional Impact -> Skeptic -> Briefing pipeline.

Owner: Person 2 (Grok Agent Intelligence).
CONTRACT: translator.py calls run_investigation(); keep its name and signature.
Every on_progress event corresponds to a real step that just happened.
"""

from agents.briefing import build_assessment
from agents.grok_client import GrokClient
from agents.investigator import investigate
from agents.ledger import EvidenceLedger, LedgerSource
from agents.regional_impact import assess_regional_impact
from agents.reviser import revise
from agents.runner import ChatClient, ProgressCallback, emit
from agents.skeptic import review
from agents.toolbox import AgentToolbox
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment

SENTINEL_NAME = "Ocean Sentinel"
BRIEFING_NAME = "Briefing"


# Investigates one anomaly end to end and returns a validated Assessment.
def run_investigation(
    anomaly: AnomalyRecord,
    on_progress: ProgressCallback,
    *,
    client: ChatClient | None = None,
    toolbox: AgentToolbox | None = None,
) -> Assessment:
    client = client or GrokClient()
    toolbox = toolbox or AgentToolbox(EvidenceLedger(), anomaly.observation_date)
    ledger = toolbox.ledger
    ledger.record_source(LedgerSource(anomaly.source, "measurement"))
    emit(
        on_progress,
        SENTINEL_NAME,
        f"{anomaly.region}: {anomaly.value} {anomaly.unit} on "
        f"{anomaly.observation_date} ({anomaly.detection_method}, "
        f"status {anomaly.status}).",
    )

    investigation = investigate(client, toolbox, anomaly, on_progress)
    impact = assess_regional_impact(
        client, toolbox, anomaly, investigation, on_progress
    )
    verification = review(
        client, anomaly, investigation, impact, ledger, on_progress
    )
    if verification.verdict != "accept":
        revised = revise(
            client, investigation, impact, verification, ledger, on_progress
        )
        investigation, impact = revised.investigation, revised.impact
        verification = review(
            client, anomaly, investigation, impact, ledger, on_progress
        )

    emit(on_progress, BRIEFING_NAME, "Assembling the verified assessment.")
    assessment = build_assessment(anomaly, investigation, impact, verification, ledger)
    emit(
        on_progress,
        BRIEFING_NAME,
        f"Assessment completed (confidence: {assessment.confidence}).",
    )
    return assessment
