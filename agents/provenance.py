"""Deterministic checks on agent output: the LLM proposes, this code verifies.

Owner: Person 2 (Grok Agent Intelligence).
"""

import re
from collections.abc import Iterable

from agents.agent_models import (
    AgentEvidence,
    AlternativeExplanation,
    Exposure,
    SkepticIssue,
)
from agents.ledger import EvidenceLedger
from schemas.anomaly import AnomalyRecord
from schemas.assessment import AlertLevel, ConfidenceLevel, EvidenceItem

CONFIDENCE_ORDER: tuple[ConfidenceLevel, ...] = (
    "inconclusive",
    "low",
    "moderate",
    "high",
)
ALERT_ORDER: tuple[AlertLevel, ...] = ("informational", "monitor", "elevated")
OVERREACH_PATTERN = re.compile(
    r"\b(caused by|will cause|will flood|will result in|will lead to|"
    r"guarantee[sd]?|certainly|definitely|undoubtedly|proves?|inevitabl[ey])\b",
    re.IGNORECASE,
)
UNVERIFIED_NOTE = "Source was not retrieved during this investigation; unverified."


# Returns the lowest of the given confidence levels.
def lowest_confidence(*levels: ConfidenceLevel) -> ConfidenceLevel:
    return min(levels, key=CONFIDENCE_ORDER.index)


# Formats an alternative explanation as one display line (also used for checks).
def format_alternative(alternative: AlternativeExplanation) -> str:
    parts = [
        f"Alternative explanation [{alternative.status}]: {alternative.explanation}"
    ]
    if alternative.evidence_for:
        parts.append(f"For: {alternative.evidence_for}")
    if alternative.evidence_against:
        parts.append(f"Against: {alternative.evidence_against}")
    return " ".join(parts)


# Formats an exposure as one display line (also used for checks).
def format_exposure(exposure: Exposure) -> str:
    detail = f"basis: {exposure.basis}"
    if exposure.uncertainty:
        detail += f"; uncertainty: {exposure.uncertainty}"
    return f"{exposure.who_or_what}: {exposure.possible_effect} ({detail})"


# Returns the highest alert level the evidence justifies (the Action Bot's ceiling).
def max_alert_level(
    anomaly_status: str, confidence: ConfidenceLevel, signal_reproduced: bool
) -> tuple[AlertLevel, str]:
    if anomaly_status != "detected":
        return "informational", f"the record's status is '{anomaly_status}'"
    if not signal_reproduced:
        return "informational", "the Sentinel Bot could not reproduce the signal"
    if confidence == "inconclusive":
        return "informational", "the assessment is inconclusive"
    if confidence == "low":
        return "monitor", "confidence is low"
    return "elevated", f"the signal is detected with {confidence} confidence"


# Returns the lower of two alert levels.
def lowest_alert(first: AlertLevel, second: AlertLevel) -> AlertLevel:
    return min(first, second, key=ALERT_ORDER.index)


# Joins an optional existing note with a new one.
def _append_note(existing: str | None, note: str) -> str:
    return f"{existing} {note}" if existing else note


# Builds the measured evidence item for the anomaly straight from the record.
def observation_evidence(anomaly: AnomalyRecord) -> EvidenceItem:
    from agents.context import is_live_weather
    return EvidenceItem(
        claim=(
            f"{anomaly.variable} in {anomaly.region} was {anomaly.value} "
            f"{anomaly.unit} on {anomaly.observation_date} (baseline "
            f"{anomaly.baseline_period}, method {anomaly.detection_method})."
        ),
        source=anomaly.source,
        source_date=anomaly.observation_date,
        evidence_type="reported" if is_live_weather(anomaly) else "measured",
        limitations='Current weather-model estimate, not a station observation.' if is_live_weather(anomaly) else None,
    )


# Checks agent evidence against the ledger; unverifiable items become uncertain.
def verify_evidence(
    items: Iterable[AgentEvidence], ledger: EvidenceLedger
) -> list[EvidenceItem]:
    verified: list[EvidenceItem] = []
    seen_keys: set[tuple[str, str]] = set()
    for item in items:
        key = (item.claim.strip().lower(), item.source.strip().lower())
        if key in seen_keys:
            continue
        seen_keys.add(key)
        ledger_source = ledger.find(item.source, item.url)
        if ledger_source is None:
            verified.append(
                EvidenceItem(
                    claim=item.claim,
                    source=item.source,
                    source_date=item.source_date,
                    evidence_type="uncertain",
                    limitations=_append_note(item.limitations, UNVERIFIED_NOTE),
                    url=None,
                )
            )
            continue
        evidence_type = item.evidence_type
        if evidence_type == "measured" and ledger_source.kind != "measurement":
            evidence_type = "reported"
        verified.append(
            EvidenceItem(
                claim=item.claim,
                source=ledger_source.name,
                source_date=item.source_date,
                evidence_type=evidence_type,
                limitations=item.limitations,
                url=ledger_source.url,
            )
        )
    return verified


# Returns statements that contain causal or certainty overreach.
def find_overreach(statements: Iterable[str]) -> list[str]:
    return [text for text in statements if OVERREACH_PATTERN.search(text)]


# Turns overreaching statements into major Skeptic issues.
def flag_overreach(statements: Iterable[str]) -> list[SkepticIssue]:
    return [
        SkepticIssue(
            claim=text,
            problem="States causation or certainty the evidence cannot establish.",
            severity="major",
            suggested_fix="Rephrase as a possible association that needs monitoring.",
        )
        for text in find_overreach(statements)
    ]


# Returns a confidence ceiling based on how complete the gathered evidence is.
# Records judged only against one reanalysis model (no official report is
# expected) are capped at "moderate", since nothing independent corroborates them.
def completeness_cap(
    ledger: EvidenceLedger, requires_official_report: bool = True
) -> ConfidenceLevel:
    if ledger.unavailable:
        return "low"
    if not requires_official_report:
        return "moderate"
    return "high" if ledger.has_official_report() else "low"
