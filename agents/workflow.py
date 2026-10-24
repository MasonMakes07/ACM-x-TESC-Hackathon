"""Runs the EarthWatch bot pipeline.

Owner: Person 2 (Grok Agent Intelligence).
CONTRACT: translator.py calls run_investigation(); keep its name and signature.

    Sentinel Bot (code)  -> re-checks the detected signal against source data
    Investigator Bot     -> researches it and tests alternative explanations
    Impact Bot           -> estimates who or what could be affected
    Skeptic / Verifier   -> challenges the draft (one Reviser cycle if needed)
    Action Bot           -> alert, short report and contingency plan

Every on_progress event corresponds to a real step that just happened.
"""

from agents.action import act
from agents.agent_errors import AgentOutputError, GrokError
from agents.agent_models import ActionReport
from agents.briefing import alert_ceiling, build_assessment, final_confidence
from agents.context import build_context, coastal_station, infer_as_of_date, is_coastal_water_level, is_live_weather
from agents.grok_client import GrokClient
from agents.investigator import investigate
from agents.ledger import EvidenceLedger, LedgerSource
from agents.regional_impact import assess_regional_impact
from agents.reviser import revise
from agents.runner import ChatClient, ProgressCallback, emit
from agents.sentinel import monitor
from agents.skeptic import review
from agents.toolbox import AgentToolbox
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment

ACTION_BOT_NAME = "Action Bot"
UNSUPPORTED_REGION_REASON = (
    "Record region is neither a supported Pacific index nor a coordinate "
    "location, so no independent data could be retrieved."
)
ACTION_INVALID_OUTPUT_REASON = "it returned invalid structured output twice."
ACTION_API_ERROR_REASON = "the Grok API could not be reached or returned an error."


# Investigates one anomaly end to end and returns a validated Assessment.
def run_investigation(
    anomaly: AnomalyRecord,
    on_progress: ProgressCallback,
    *,
    client: ChatClient | None = None,
    toolbox: AgentToolbox | None = None,
) -> Assessment:
    client = client or GrokClient()
    if toolbox is None and is_live_weather(anomaly):
        from agents.live_tools import LiveWeatherToolbox
        from data.locations import Location
        selected = build_context(anomaly)
        if selected.latitude is None:
            raise ValueError('Live investigations require selected coordinates')
        toolbox = LiveWeatherToolbox(EvidenceLedger(),infer_as_of_date(anomaly),Location(selected.place,selected.latitude,selected.longitude))
    if toolbox is None and is_coastal_water_level(anomaly):
        from agents.coastal_tools import CoastalToolbox
        where = build_context(anomaly)
        if where.latitude is None:
            raise ValueError("Coastal investigations require the gauge coordinates in the region")
        toolbox = CoastalToolbox(EvidenceLedger(), infer_as_of_date(anomaly), coastal_station(anomaly),
                                 where.latitude, where.longitude)
    toolbox = toolbox or AgentToolbox(EvidenceLedger(), infer_as_of_date(anomaly))
    ledger = toolbox.ledger
    context = build_context(anomaly)
    ledger.record_source(LedgerSource(anomaly.source, "measurement"))
    if context.profile == "unknown":
        ledger.record_unavailable("data_tools", UNSUPPORTED_REGION_REASON)

    sentinel = monitor(toolbox, anomaly, context, on_progress)
    sentinel_summary = sentinel.describe()
    investigation = investigate(
        client, toolbox, anomaly, on_progress, context, sentinel_summary
    )
    impact = assess_regional_impact(
        client, toolbox, anomaly, investigation, on_progress, context
    )
    verification = review(
        client, anomaly, investigation, impact, ledger, on_progress, sentinel_summary
    )
    if verification.verdict != "accept":
        revised = revise(
            client, investigation, impact, verification, ledger, on_progress
        )
        investigation, impact = revised.investigation, revised.impact
        verification = review(
            client,
            anomaly,
            investigation,
            impact,
            ledger,
            on_progress,
            sentinel_summary,
        )

    confidence = final_confidence(
        investigation, verification, ledger, context, sentinel
    )
    allowed_level, level_reason = alert_ceiling(anomaly, confidence, sentinel)
    action: ActionReport | None = None
    action_failure: str | None = None
    try:
        action = act(
            client,
            anomaly,
            context,
            investigation,
            impact,
            verification,
            ledger,
            confidence,
            allowed_level,
            level_reason,
            sentinel_summary,
            on_progress,
        )
    except AgentOutputError:
        action_failure = ACTION_INVALID_OUTPUT_REASON
    except GrokError:
        action_failure = ACTION_API_ERROR_REASON
    if action_failure:
        emit(on_progress, ACTION_BOT_NAME, f"Action plan unavailable: {action_failure}")

    assessment = build_assessment(
        anomaly,
        investigation,
        impact,
        verification,
        ledger,
        context,
        sentinel,
        action,
        action_failure,
    )
    plan = assessment.action_plan
    alert_label = plan.alert_level if plan else "none"
    emit(
        on_progress,
        ACTION_BOT_NAME,
        f"Assessment completed (confidence: {assessment.confidence}, "
        f"alert: {alert_label}).",
    )
    return assessment
