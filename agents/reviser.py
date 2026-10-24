"""Reviser step: one revision cycle that fixes the Skeptic's issues.

Owner: Person 2 (Grok Agent Intelligence).
"""

from agents.agent_models import (
    ImpactReport,
    InvestigationReport,
    RevisedDraft,
    VerificationReport,
)
from agents.ledger import EvidenceLedger
from agents.prompts import REVISER_PROMPT
from agents.runner import ChatClient, ProgressCallback, emit, run_agent

AGENT_NAME = "Reviser"


# Revises the investigation and impact drafts to resolve the Skeptic's issues.
def revise(
    client: ChatClient,
    investigation: InvestigationReport,
    impact: ImpactReport,
    verification: VerificationReport,
    ledger: EvidenceLedger,
    on_progress: ProgressCallback,
) -> RevisedDraft:
    emit(
        on_progress,
        AGENT_NAME,
        f"Revising the draft to address {len(verification.issues)} issue(s).",
    )
    user_prompt = (
        f"{ledger.describe()}\n"
        f"Draft investigation:\n{investigation.model_dump_json(indent=2)}\n"
        f"Draft regional impact:\n{impact.model_dump_json(indent=2)}\n"
        f"Skeptic report:\n{verification.model_dump_json(indent=2)}"
    )
    return run_agent(
        client,
        agent_name=AGENT_NAME,
        system_prompt=REVISER_PROMPT,
        user_prompt=user_prompt,
        output_model=RevisedDraft,
        on_progress=on_progress,
    )
