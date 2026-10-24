"""Briefing step: turns the verified drafts into the final Assessment.

Owner: Person 2 (Grok Agent Intelligence). Deterministic (no LLM call), so the
final confidence, provenance and limitations are always enforced by code.
"""

from collections.abc import Iterable

from agents.agent_models import ImpactReport, InvestigationReport, VerificationReport
from agents.ledger import EvidenceLedger
from agents.provenance import (
    completeness_cap,
    find_overreach,
    lowest_confidence,
    observation_evidence,
    verify_evidence,
)
from agents.skeptic import draft_statements
from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment

UNVERIFIED_PREFIX = "[Unverified] "
STANDING_LIMITATION = (
    "EarthWatch identifies unusual conditions and investigates possible "
    "implications; it does not forecast specific floods or issue official warnings."
)
DEFAULT_NEXT_STEP = "Review the latest NOAA CPC ENSO Diagnostic Discussion."


# Removes blanks and duplicates while keeping the original order.
def _unique(texts: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(text.strip() for text in texts if text and text.strip()))


# Prefixes statements that still overreach so users see they are unverified.
def _qualify(texts: Iterable[str], unresolved: set[str]) -> list[str]:
    return [
        f"{UNVERIFIED_PREFIX}{text}" if text in unresolved else text
        for text in _unique(texts)
    ]


# Assembles the final, code-verified Assessment for the dashboard.
def build_assessment(
    anomaly: AnomalyRecord,
    investigation: InvestigationReport,
    impact: ImpactReport,
    verification: VerificationReport,
    ledger: EvidenceLedger,
) -> Assessment:
    unresolved = set(find_overreach(draft_statements(investigation, impact)))
    confidence = lowest_confidence(
        investigation.proposed_confidence,
        verification.confidence_cap,
        completeness_cap(ledger),
    )
    if verification.verdict == "reject":
        confidence = "inconclusive"
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
                []
                if ledger.has_official_report()
                else ["No official NOAA assessment was retrieved."]
            ),
            *(
                ["Statements marked [Unverified] overstate the evidence."]
                if unresolved
                else []
            ),
            *open_issues,
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
        contradictory_findings=_unique(investigation.contradictory_findings),
        regional_implications=_qualify(impact.regional_implications, unresolved),
        confidence=confidence,
        limitations=limitations,
        recommended_next_steps=_qualify(
            [*impact.recommended_next_steps, DEFAULT_NEXT_STEP], unresolved
        ),
    )
