"""Evidence ledger: records every source tools really retrieved in one investigation.

Owner: Person 2 (Grok Agent Intelligence). Code uses it to verify the provenance
of agent claims, so an agent cannot cite a source that was never consulted.
"""

from dataclasses import dataclass, field
from typing import Literal

SourceKind = Literal["measurement", "official_report", "reference"]

MIN_MATCH_LENGTH = 4


# =============================================================================
# LedgerSource
# =============================================================================

# One source a tool successfully retrieved.
@dataclass(frozen=True)
class LedgerSource:
    name: str
    kind: SourceKind
    url: str | None = None
    retrieved_at: str | None = None


# =============================================================================
# EvidenceLedger
# =============================================================================

# Tracks retrieved sources and unavailable tools for a single investigation.
@dataclass
class EvidenceLedger:
    sources: list[LedgerSource] = field(default_factory=list)
    unavailable: list[str] = field(default_factory=list)

    # Records a successfully retrieved source (duplicates are ignored).
    def record_source(self, source: LedgerSource) -> None:
        if source not in self.sources:
            self.sources.append(source)

    # Records that a tool could not supply evidence and why.
    def record_unavailable(self, tool_name: str, reason: str) -> None:
        entry = f"{tool_name}: {reason}"
        if entry not in self.unavailable:
            self.unavailable.append(entry)

    # Returns the retrieved source whose URL exactly equals the given text, if any.
    def _find_by_url(self, text: str | None) -> LedgerSource | None:
        cited = (text or "").strip().rstrip("/").lower()
        if not cited.startswith(("http://", "https://")):
            return None
        for source in self.sources:
            if source.url and source.url.strip().rstrip("/").lower() == cited:
                return source
        return None

    # Returns the ledger source matching a cited name or URL, if any.
    # A URL written in the "source" field counts only on an exact URL match.
    def find(
        self, cited_source: str, cited_url: str | None = None
    ) -> LedgerSource | None:
        for candidate in (cited_url, cited_source):
            match = self._find_by_url(candidate)
            if match is not None:
                return match
        cited = cited_source.strip().lower()
        if len(cited) < MIN_MATCH_LENGTH:
            return None
        for source in self.sources:
            known = source.name.lower()
            if cited in known or known in cited:
                return source
        return None

    # Returns True when at least one official report was retrieved.
    def has_official_report(self) -> bool:
        return any(source.kind == "official_report" for source in self.sources)

    # Summarises the ledger as plain text for agent prompts.
    def describe(self) -> str:
        retrieved = [
            f"- {source.name} [{source.kind}]"
            + (f" {source.url}" if source.url else "")
            + (f" (retrieved {source.retrieved_at})" if source.retrieved_at else "")
            for source in self.sources
        ] or ["- none"]
        missing = [f"- {entry}" for entry in self.unavailable] or ["- none"]
        return (
            "Sources actually retrieved:\n" + "\n".join(retrieved)
            + "\nUnavailable evidence:\n" + "\n".join(missing)
        )
