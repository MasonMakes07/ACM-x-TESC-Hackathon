"""Assembly step: turns verified drafts and the Action Bot's plan into an Assessment.

Owner: Person 2 (Grok Agent Intelligence). Deterministic (no LLM call), so the
final confidence, alert ceiling, provenance and limitations are enforced by code.
"""

from collections.abc import Iterable

from agents.agent_models import (
    ActionReport,
    ImpactReport,
    InvestigationReport,
    VerificationReport,
)
from agents.context import AnomalyContext, is_coastal_water_level, is_live_weather
from agents.ledger import EvidenceLedger
from agents.provenance import (
    completeness_cap,
    find_overreach,
    format_alternative,
    format_exposure,
    lowest_alert,
    lowest_confidence,
    max_alert_level,
    observation_evidence,
    verify_evidence,
)
from agents.sentinel import SentinelReport
from agents.skeptic import draft_statements
from schemas.anomaly import AnomalyRecord
from schemas.assessment import (
    ActionPlan,
    Assessment,
    ConfidenceLevel,
    ContingencyStep,
)

UNVERIFIED_PREFIX = "[Unverified] "
STANDING_LIMITATION = (
    "EarthWatch identifies unusual conditions and investigates possible "
    "implications; it does not forecast specific floods or issue official warnings."
)
PACIFIC_NEXT_STEP = "Review the latest NOAA CPC ENSO Diagnostic Discussion."
LOCAL_NEXT_STEP = (
    "Check the national meteorological service and local hazard authorities "
    "for this location."
)
NO_OFFICIAL_REPORT_LIMITATION = "No official NOAA assessment was retrieved."
COASTAL_LIMITATION = (
    "Based on one NOAA tide gauge and model wind and pressure. The flood threshold is NOAA's "
    "minor high-tide-flooding level, not an official warning; check the local NWS office."
)
SINGLE_SOURCE_LIMITATION = (
    "Based on one ERA5 reanalysis grid cell; no independent source corroborates it."
)
FEW_ALTERNATIVES_LIMITATION = (
    "Fewer than two alternative explanations were evaluated."
)
ACTION_DISCLAIMER = (
    "Decision support only: this is not an official warning or forecast. Consult "
    "national meteorological and civil-protection authorities before acting."
)
ACTION_UNAVAILABLE_LIMITATION = "The Action Bot's plan is unavailable: {reason}"
MIN_ALTERNATIVES = 2


# Removes blanks and duplicates while keeping the original order.
def _unique(texts: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(text.strip() for text in texts if text and text.strip()))


# Prefixes statements that still overreach so users see they are unverified.
def _qualify(texts: Iterable[str], unresolved: set[str]) -> list[str]:
    return [
        f"{UNVERIFIED_PREFIX}{text}" if text in unresolved else text
        for text in _unique(texts)
    ]


# Prefixes a single text if it contains causal or certainty overreach.
def _flag_text(text: str) -> str:
    return f"{UNVERIFIED_PREFIX}{text}" if find_overreach([text]) else text


# Returns the final confidence: the lowest of every ceiling that applies.
def final_confidence(
    investigation: InvestigationReport,
    verification: VerificationReport,
    ledger: EvidenceLedger,
    context: AnomalyContext | None = None,
    sentinel: SentinelReport | None = None,
) -> ConfidenceLevel:
    expects_official_report = context is None or context.profile == "pacific"
    ceilings = [
        investigation.proposed_confidence,
        verification.confidence_cap,
        completeness_cap(ledger, expects_official_report),
    ]
    if sentinel is not None and sentinel.status == "mismatch":
        ceilings.append("low")
    if sentinel is not None and sentinel.status == "unverified":
        ceilings.append("moderate")
    confidence = lowest_confidence(*ceilings)
    return "inconclusive" if verification.verdict == "reject" else confidence


# Returns the highest alert level allowed and the reason, for the Action Bot's prompt.
def alert_ceiling(
    anomaly: AnomalyRecord, confidence: ConfidenceLevel, sentinel: SentinelReport | None
):
    reproduced = sentinel is None or sentinel.status != "mismatch"
    return max_alert_level(anomaly.status, confidence, reproduced)


# Builds the shared ActionPlan, clamping the alert level and flagging overreach.
def build_action_plan(
    action: ActionReport,
    anomaly: AnomalyRecord,
    confidence: ConfidenceLevel,
    sentinel: SentinelReport | None,
) -> ActionPlan:
    allowed_level, reason = alert_ceiling(anomaly, confidence, sentinel)
    level = lowest_alert(action.alert_level, allowed_level)
    level_reason = f"Maximum allowed level is '{allowed_level}' because {reason}."
    if level != action.alert_level:
        level_reason += f" The proposed '{action.alert_level}' was lowered."
    return ActionPlan(
        alert_level=level,
        level_reason=level_reason,
        alert_headline=_flag_text(action.alert_headline.strip()),
        alert_message=_flag_text(action.alert_message.strip()),
        report=_flag_text(action.report.strip()),
        contingency_plan=[
            ContingencyStep(
                trigger=_flag_text(step.trigger.strip()),
                action=_flag_text(step.action.strip()),
                rationale=_flag_text(step.rationale.strip()),
            )
            for step in action.contingency_plan
        ],
        monitoring_triggers=[
            _flag_text(text) for text in _unique(action.monitoring_triggers)
        ],
        disclaimer=ACTION_DISCLAIMER,
    )


# Describes Sentinel results that need to be disclosed as limitations.
def _sentinel_limitations(sentinel: SentinelReport | None) -> list[str]:
    if sentinel is None or sentinel.status == "confirmed":
        return []
    if sentinel.status == "mismatch":
        return [f"The Sentinel Bot could not reproduce the record: {sentinel.detail}"]
    return [f"The Sentinel Bot could not re-check the record: {sentinel.detail}"]


# Assembles the final, code-verified Assessment for the dashboard.
# A missing context is treated as a Pacific record, which expects NOAA context.
def build_assessment(
    anomaly: AnomalyRecord,
    investigation: InvestigationReport,
    impact: ImpactReport,
    verification: VerificationReport,
    ledger: EvidenceLedger,
    context: AnomalyContext | None = None,
    sentinel: SentinelReport | None = None,
    action: ActionReport | None = None,
    action_failure: str | None = None,
) -> Assessment:
    expects_official_report = context is None or context.profile == "pacific"
    unresolved = set(find_overreach(draft_statements(investigation, impact)))
    confidence = final_confidence(
        investigation, verification, ledger, context, sentinel
    )
    open_issues = (
        [
            f"Unresolved: {issue.problem} ({issue.claim})"
            for issue in verification.issues
            if issue.severity == "major"
        ]
        if verification.verdict != "accept"
        else []
    )
    limitations = _unique(
        [
            *impact.limitations,
            *verification.limitations,
            *(f"Open question: {text}" for text in investigation.open_questions),
            *(f"Missing evidence: {entry}" for entry in ledger.unavailable),
            *(
                [NO_OFFICIAL_REPORT_LIMITATION]
                if expects_official_report and not ledger.has_official_report()
                else []
            ),
            *([] if expects_official_report or is_live_weather(anomaly) or is_coastal_water_level(anomaly) else [SINGLE_SOURCE_LIMITATION]),
            *([COASTAL_LIMITATION] if is_coastal_water_level(anomaly) else []),
            *(['Current model estimates and station readings have different coverage and timestamps; this is not a historical anomaly assessment.'] if is_live_weather(anomaly) else []),
            *_sentinel_limitations(sentinel),
            *(
                [FEW_ALTERNATIVES_LIMITATION]
                if len(investigation.alternative_explanations) < MIN_ALTERNATIVES
                else []
            ),
            *(
                ["Statements marked [Unverified] overstate the evidence."]
                if unresolved
                else []
            ),
            *open_issues,
            *(
                [ACTION_UNAVAILABLE_LIMITATION.format(reason=action_failure)]
                if action_failure
                else []
            ),
            STANDING_LIMITATION,
        ]
    )
    summary = investigation.summary.strip()
    if summary in unresolved:
        summary = UNVERIFIED_PREFIX + summary
    return Assessment(
        anomaly_id=anomaly.anomaly_id,
        summary=summary,
        evidence=[
            observation_evidence(anomaly),
            *verify_evidence(investigation.evidence + impact.evidence, ledger),
        ],
        supporting_findings=_qualify(investigation.supporting_findings, unresolved),
        contradictory_findings=_qualify(
            [
                *investigation.contradictory_findings,
                *(
                    format_alternative(item)
                    for item in investigation.alternative_explanations
                ),
            ],
            unresolved,
        ),
        regional_implications=_qualify(
            [
                *impact.regional_implications,
                *(format_exposure(item) for item in impact.exposures),
            ],
            unresolved,
        ),
        confidence=confidence,
        limitations=limitations,
        recommended_next_steps=_qualify(
            [
                *impact.recommended_next_steps,
                PACIFIC_NEXT_STEP if expects_official_report else LOCAL_NEXT_STEP,
            ],
            unresolved,
        ),
        action_plan=(
            build_action_plan(action, anomaly, confidence, sentinel)
            if action is not None
            else None
        ),
    )
