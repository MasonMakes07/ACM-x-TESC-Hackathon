"""Structured outputs each agent must return (validated with Pydantic).

Owner: Person 2 (Grok Agent Intelligence). These are internal to agents/; the
dashboard only ever sees schemas.assessment.Assessment.
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from schemas.assessment import AlertLevel, ConfidenceLevel, EvidenceType

Verdict = Literal["accept", "revise", "reject"]
Severity = Literal["minor", "major"]
AlternativeStatus = Literal["supported", "unsupported", "untested"]


# =============================================================================
# AgentEvidence
# =============================================================================

# One claim proposed by an agent; provenance is re-checked in code afterwards.
class AgentEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_date: date | None = None
    evidence_type: EvidenceType
    limitations: str | None = None
    url: str | None = None


# =============================================================================
# AlternativeExplanation
# =============================================================================

# A competing explanation the Investigator tested (or honestly left untested).
class AlternativeExplanation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    explanation: str = Field(min_length=1)
    evidence_for: str = ""
    evidence_against: str = ""
    status: AlternativeStatus


# =============================================================================
# InvestigationReport
# =============================================================================

# Investigator Bot output: what the evidence does and does not support.
class InvestigationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=1)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    supporting_findings: list[str] = Field(default_factory=list)
    contradictory_findings: list[str] = Field(default_factory=list)
    alternative_explanations: list[AlternativeExplanation] = Field(
        default_factory=list
    )
    open_questions: list[str] = Field(default_factory=list)
    proposed_confidence: ConfidenceLevel


# =============================================================================
# Exposure
# =============================================================================

# One group, sector or asset that could plausibly be affected, with its basis.
class Exposure(BaseModel):
    model_config = ConfigDict(extra="ignore")

    who_or_what: str = Field(min_length=1)
    possible_effect: str = Field(min_length=1)
    basis: str = Field(min_length=1)
    uncertainty: str = ""


# =============================================================================
# ImpactReport
# =============================================================================

# Impact Bot output: who or what could be affected, stated as possibilities.
class ImpactReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    regional_implications: list[str] = Field(default_factory=list)
    exposures: list[Exposure] = Field(default_factory=list)
    evidence: list[AgentEvidence] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


# =============================================================================
# SkepticIssue
# =============================================================================

# One problem the Skeptic found in the draft assessment.
class SkepticIssue(BaseModel):
    model_config = ConfigDict(extra="ignore")

    claim: str = Field(min_length=1)
    problem: str = Field(min_length=1)
    severity: Severity
    suggested_fix: str = ""


# =============================================================================
# VerificationReport
# =============================================================================

# Skeptic / Verifier output: verdict, issues found and a confidence ceiling.
class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    verdict: Verdict
    issues: list[SkepticIssue] = Field(default_factory=list)
    confidence_cap: ConfidenceLevel
    limitations: list[str] = Field(default_factory=list)


# =============================================================================
# ContingencyDraft
# =============================================================================

# One conditional response proposed by the Action Bot.
class ContingencyDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    trigger: str = Field(min_length=1)
    action: str = Field(min_length=1)
    rationale: str = Field(min_length=1)


# =============================================================================
# ActionReport
# =============================================================================

# Action Bot output: alert, short report and contingency plan.
class ActionReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alert_level: AlertLevel
    alert_headline: str = Field(min_length=1)
    alert_message: str = Field(min_length=1)
    report: str = Field(min_length=1)
    contingency_plan: list[ContingencyDraft] = Field(default_factory=list)
    monitoring_triggers: list[str] = Field(default_factory=list)


# =============================================================================
# RevisedDraft
# =============================================================================

# Reviser output: the corrected investigation and impact drafts.
class RevisedDraft(BaseModel):
    model_config = ConfigDict(extra="ignore")

    investigation: InvestigationReport
    impact: ImpactReport
