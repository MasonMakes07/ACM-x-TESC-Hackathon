"""Source list checks. Owner: Person 3 (Product & Dashboard)."""

from datetime import date

from dashboard.sources import collect_sources, safe_url
from schemas.assessment import EvidenceItem


# Builds an evidence item with overridable fields.
def _item(**overrides) -> EvidenceItem:
    fields = dict(
        claim="A claim", source="NOAA CPC", source_date=date(2023, 6, 1),
        evidence_type="reported", url="https://example.org/report",
    )
    return EvidenceItem(**{**fields, **overrides})


# Checks only real http(s) links are accepted.
def test_safe_url_accepts_only_http_links():
    assert safe_url("https://example.org/a") == "https://example.org/a"
    assert safe_url("javascript:alert(1)") is None
    assert safe_url("ftp://example.org") is None
    assert safe_url("https://") is None
    assert safe_url(None) is None


# Checks two claims from the same link become one source listing both claims.
def test_claims_from_one_link_are_grouped():
    rows = collect_sources([_item(claim="One"), _item(claim="Two", evidence_type="measured")])
    assert len(rows) == 1
    assert rows[0].claims == ("One", "Two")
    assert rows[0].kinds == ("measured", "reported")


# Checks a source with no link is kept, shown without a link, and never given one.
def test_source_without_link_is_kept_without_url():
    rows = collect_sources([_item(url=None), _item(url="not a url", claim="Other")])
    assert len(rows) == 1
    assert rows[0].url is None


# Checks measured sources are listed before weaker ones.
def test_sources_are_ordered_by_strength():
    rows = collect_sources([
        _item(source="Guess", url="https://a.example", evidence_type="uncertain"),
        _item(source="Data", url="https://b.example", evidence_type="measured"),
    ])
    assert [row.name for row in rows] == ["Data", "Guess"]
