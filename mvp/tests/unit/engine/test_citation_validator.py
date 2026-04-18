"""Tests for engine.citation_validator."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from mvp.engine.citation_validator import (
    resolve_citation,
    validate_citations,
)
from mvp.engine.rule_executor import build_market_data_citation
from mvp.lib.citation import Citation, build_locator
from mvp.lib.hashing import hash_excerpt
from mvp.skills.manifest_schema import SkillManifest
from mvp.standardize.statements import build_canonical_statements


def _apple_manifest() -> SkillManifest:
    from pathlib import Path
    p = Path(__file__).resolve().parents[3] / "skills" / "fundamental" / "extract_canonical_statements" / "manifest.yaml"
    return SkillManifest.load_from_yaml(p)


@pytest.mark.requires_live_data
def test_validate_citations_happy_path() -> None:
    manifest = _apple_manifest()
    stmts = build_canonical_statements("0000320193/0000320193-23-000106")
    citations = []
    for s in stmts:
        for li in s.line_items:
            citations.append(li.citation.model_dump(mode="json"))
    outputs = {"statements": stmts, "citations": citations, "warnings": []}
    errs = validate_citations(outputs, manifest)
    assert errs == []


def test_validate_citations_empty_fails() -> None:
    manifest = _apple_manifest()
    outputs = {"statements": ["placeholder"], "citations": [], "warnings": []}
    errs = validate_citations(outputs, manifest)
    assert len(errs) >= 1
    assert any("citations" in e.detail for e in errs)


@pytest.mark.requires_live_data
def test_resolve_filing_citation_apple() -> None:
    stmts = build_canonical_statements("0000320193/0000320193-23-000106")
    revenue = next(
        li for s in stmts for li in s.line_items if li.name == "revenue"
    )
    res = resolve_citation(revenue.citation)
    assert res["resolved"] is True
    assert "revenue" in res["passage_text"]
    assert res["source_url"]  # Apple's URL is populated from meta.json


def test_resolve_market_data_citation() -> None:
    c = build_market_data_citation(
        cik="0000320193",
        fiscal_year_end=date(2023, 9, 30),
        fixture_excerpt="test",
        market_value_of_equity=2_662_807_717_920.0,
    )
    res = resolve_citation(c)
    assert res["resolved"] is True
    assert "market_value_of_equity_usd" in res["passage_text"]


def test_resolve_malformed_doc_id() -> None:
    """A citation with an unknown doc_id shape must resolve to unresolved."""
    c = Citation(
        doc_id="junk",
        statement_role=None,
        locator="junk::foo::bar",
        excerpt_hash=hash_excerpt("anything"),
        value=None,
        retrieved_at=datetime.now(timezone.utc),
    )
    res = resolve_citation(c)
    assert res["resolved"] is False


def test_resolve_market_data_with_missing_entry() -> None:
    """Market-data locator pointing at a non-existent issuer."""
    locator = build_locator(
        "market_data/equity_values",
        "market_data",
        "market_value_of_equity_9999999999_2020-01-01",
    )
    c = Citation(
        doc_id="market_data/equity_values",
        statement_role=None,
        locator=locator,
        excerpt_hash=hash_excerpt("anything"),
        value=1.0,
        retrieved_at=datetime.now(timezone.utc),
    )
    res = resolve_citation(c)
    assert res["resolved"] is False
