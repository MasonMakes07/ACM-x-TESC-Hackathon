"""Shared assessment contract returned by the agent workflow to the dashboard.

SHARED FILE: changing it changes the contract for all three workstreams. Agree as
a team first, update sample_data/ in the same commit, and run pytest before pushing.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EvidenceType = Literal["measured", "reported", "inferred", "uncertain"]
ConfidenceLevel = Literal["low", "moderate", "high", "inconclusive"]


# =============================================================================
# EvidenceItem
# =============================================================================

# One factual claim with its provenance, as required by plan.md Task 4.
class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    claim: str = Field(min_length=1)
    source: str = Field(min_length=1)
    source_date: date | None = None
    evidence_type: EvidenceType
    limitations: str | None = None
    url: str | None = None


# =============================================================================
# Assessment
# =============================================================================

# The verified, structured investigation report the dashboard displays.
class Assessment(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    anomaly_id: str = Field(pattern=r"^[a-z0-9_]{1,64}$")
    summary: str = Field(min_length=1)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    supporting_findings: list[str] = Field(default_factory=list)
    contradictory_findings: list[str] = Field(default_factory=list)
    regional_implications: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel
    limitations: list[str] = Field(default_factory=list)
    recommended_next_steps: list[str] = Field(default_factory=list)


# =============================================================================
# ProgressEvent
# =============================================================================

# One real progress update emitted by an agent while an investigation runs.
class ProgressEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    timestamp: datetime
    agent: str = Field(min_length=1)
    message: str = Field(min_length=1)
