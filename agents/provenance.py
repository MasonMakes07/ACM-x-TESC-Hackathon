"""Deterministic checks on agent output: the LLM proposes, this code verifies.

Owner: Person 2 (Grok Agent Intelligence).
"""

import re
from collections.abc import Iterable

from agents.agent_models import AgentEvidence, SkepticIssue
from agents.ledger import EvidenceLedger
from schemas.anomaly import AnomalyRecord
from schemas.assessment import ConfidenceLevel, EvidenceItem

CONFIDENCE_ORDER: tuple[ConfidenceLevel, ...] = (
    "inconclusive",
    "low",
    "moderate",
    "high",
)
OVERREACH_PATTERN = re.compile(
    r"\b(caused by|will cause|will flood|will result in|will lead to|"
    r"guarantee[sd]?|certainly|definitely|undoubtedly|proves?|inevitabl[ey])\b",
    re.IGNORECASE,
)
UNVERIFIED_NOTE = "Source was not retrieved during this investigation; unverified."


# Returns the lowest of the given confidence levels.
def lowest_confidence(*levels: ConfidenceLevel) -> ConfidenceLevel:
    return min(levels, key=CONFIDENCE_ORDER.index)


# Joins an optional existing note with a new one.
def _append_note(existing: str | None, note: str) -> str:
    return f"{existing} {note}" if existing else note


# Builds the measured evidence item for the anomaly straight from the record.
def observation_evidence(anomaly: AnomalyRecord) -> EvidenceItem:
    return EvidenceItem(
        claim=(
            f"{anomaly.variable} in {anomaly.region} was {anomaly.value} "
            f"{anomaly.unit} on {anomaly.observation_date} (baseline "
            f"{anomaly.baseline_period}, method {anomaly.detection_method})."
        ),
        source=anomaly.source,
        source_date=anomaly.observation_date,
        evidence_type="measured",
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
def completeness_cap(ledger: EvidenceLedger) -> ConfidenceLevel:
    if ledger.unavailable or not ledger.has_official_report():
        return "low"
    return "high"
