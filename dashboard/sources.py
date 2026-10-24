"""Source list for an event: every source the agents cited, with a link to open it.

Owner: Person 3 (Product & Dashboard). Shows only what the assessment actually contains;
a source without a URL is labelled as such rather than given a made-up link.
"""

from dataclasses import dataclass
from urllib.parse import urlsplit

import streamlit as st

from schemas.anomaly import AnomalyRecord
from schemas.assessment import Assessment, EvidenceItem

EVIDENCE_ORDER = ("measured", "reported", "inferred", "uncertain")


# One cited source with every claim it was used to support.
@dataclass(frozen=True)
class SourceRow:
    name: str
    url: str | None
    source_date: str
    kinds: tuple[str, ...]
    claims: tuple[str, ...]
    limitations: tuple[str, ...]


# Returns the URL when it is a real http(s) link, otherwise None.
def safe_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url)
    except ValueError:
        return None
    return url if parts.scheme.lower() in {"http", "https"} and parts.netloc else None


# Returns the link for an item: its url, or its source text when that is itself a web link.
def item_url(item: EvidenceItem) -> str | None:
    return safe_url(item.url) or safe_url(item.source)


# Returns a readable name, using the host when the source is only a web address.
def item_name(item: EvidenceItem) -> str:
    if safe_url(item.source):
        return f"Data file at {urlsplit(item.source).netloc}"
    return item.source


# Orders evidence types from strongest to weakest, unknown types last.
def _kind_rank(kind: str) -> int:
    return EVIDENCE_ORDER.index(kind) if kind in EVIDENCE_ORDER else len(EVIDENCE_ORDER)


# Groups evidence by link (or by name when there is no link) into one row per source.
def collect_sources(evidence: list[EvidenceItem]) -> list[SourceRow]:
    grouped: dict[str, list[EvidenceItem]] = {}
    for item in evidence:
        grouped.setdefault(item_url(item) or f"name:{item.source}", []).append(item)
    rows = []
    for items in grouped.values():
        kinds = sorted({item.evidence_type for item in items}, key=_kind_rank)
        dates = sorted({str(item.source_date) for item in items if item.source_date})
        rows.append(SourceRow(
            name=item_name(items[0]),
            url=item_url(items[0]),
            source_date=", ".join(dates) or "undated",
            kinds=tuple(kinds),
            claims=tuple(dict.fromkeys(item.claim for item in items)),
            limitations=tuple(dict.fromkeys(item.limitations for item in items if item.limitations)),
        ))
    return sorted(rows, key=lambda row: _kind_rank(row.kinds[0]))


# Renders one source with its open-link button and the claims it supports.
def _render_row(row: SourceRow, position: int) -> None:
    with st.container(border=True):
        st.markdown(f"**{row.name}**")
        st.caption(f"{', '.join(row.kinds)} · {row.source_date}")
        if row.url:
            st.link_button("Open source", row.url, key=f"source_link_{position}")
            st.caption(row.url)
        else:
            st.caption("The agent gave no link for this source. Search for it by name.")
        st.markdown("Used for:\n" + "\n".join(f"- {claim}" for claim in row.claims))
        for limitation in row.limitations:
            st.caption(f"Limitation: {limitation}")


# Renders the measured-data source and every source the agents cited for this event.
def sources_panel(
    anomaly: AnomalyRecord, assessment: Assessment | None, assessment_is_sample: bool
) -> None:
    st.markdown("**Data source**")
    st.caption(f"{anomaly.source} · baseline {anomaly.baseline_period}")
    if assessment is None:
        st.info("No agent sources yet. Run an investigation to see what the agents used.")
        return
    rows = collect_sources(assessment.evidence)
    st.markdown(f"**Sources the agents used ({len(rows)})**")
    if assessment_is_sample:
        st.warning("These are SAMPLE sources, not real citations.")
    if not rows:
        st.info("The agents did not cite any sources for this assessment.")
    for position, row in enumerate(rows):
        _render_row(row, position)
