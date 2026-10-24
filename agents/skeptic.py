"""Skeptic / Verifier agent: challenges unsupported or overconfident claims.

Owner: Person 2 (Grok Agent Intelligence). Combines Grok's review with a
deterministic overreach check so causal claims are caught even if Grok misses them.
"""

from agents.agent_models import ImpactReport, InvestigationReport, VerificationReport
from agents.ledger import EvidenceLedger
from agents.prompts import SKEPTIC_PROMPT
from agents.provenance import flag_overreach
from agents.runner import ChatClient, ProgressCallback, emit, run_agent
from schemas.anomaly import AnomalyRecord

AGENT_NAME = "Skeptic / Verifier"


# Lists every user-facing statement in the draft that the Skeptic must check.
def draft_statements(
    investigation: InvestigationReport, impact: ImpactReport
) -> list[str]:
    return [
        investigation.summary,
        *investigation.supporting_findings,
        *impact.regional_implications,
        *impact.recommended_next_steps,
        *(item.claim for item in investigation.evidence + impact.evidence),
    ]


# Reviews the draft and returns a verdict merged with deterministic flags.
def review(
    client: ChatClient,
    anomaly: AnomalyRecord,
    investigation: InvestigationReport,
    impact: ImpactReport,
    ledger: EvidenceLedger,
    on_progress: ProgressCallback,
) -> VerificationReport:
    emit(on_progress, AGENT_NAME, "Reviewing the draft for unsupported conclusions.")
    code_flags = flag_overreach(draft_statements(investigation, impact))
    flagged_text = "\n".join(f"- {issue.claim}" for issue in code_flags) or "- none"
    user_prompt = (
        f"Detected anomaly record:\n{anomaly.model_dump_json(indent=2)}\n"
        f"{ledger.describe()}\n"
        f"Draft investigation:\n{investigation.model_dump_json(indent=2)}\n"
        f"Draft regional impact:\n{impact.model_dump_json(indent=2)}\n"
        f"Statements already flagged by code for causal/certainty overreach:\n"
        f"{flagged_text}"
    )
    report = run_agent(
        client,
        agent_name=AGENT_NAME,
        system_prompt=SKEPTIC_PROMPT,
        user_prompt=user_prompt,
        output_model=VerificationReport,
        on_progress=on_progress,
    )
    known_claims = {issue.claim for issue in report.issues}
    new_flags = [issue for issue in code_flags if issue.claim not in known_claims]
    verdict = report.verdict
    if new_flags and verdict == "accept":
        verdict = "revise"
    major_count = sum(
        issue.severity == "major" for issue in report.issues + new_flags
    )
    emit(
        on_progress,
        AGENT_NAME,
        f"Verdict: {verdict} ({major_count} major issue(s)).",
    )
    return report.model_copy(
        update={"verdict": verdict, "issues": report.issues + new_flags}
    )
