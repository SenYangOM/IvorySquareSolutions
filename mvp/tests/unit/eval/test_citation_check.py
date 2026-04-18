"""Unit tests for mvp.eval.citation_check.

Covers:
- Happy path: well-formed citation resolves + passes numeric drift check.
- Unresolved doc_id shape returns an "unresolved" failure.
- Numeric drift beyond ±0.5% is caught.
- Malformed citation (missing required field) becomes a schema failure.
- Empty citations list yields resolution_rate=1.0.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pytest

from mvp.eval.citation_check import (
    CitationFailure,
    CitationReport,
    _check_numeric_match,
    _check_one,
    check_citations,
    format_console_report,
)
from mvp.lib.citation import Citation
from mvp.lib.hashing import hash_excerpt


# ---------------------------------------------------------------------------
# Tiny stub registry + skill.
# ---------------------------------------------------------------------------


class _StubSkill:
    def __init__(self, out: dict[str, Any]) -> None:
        self._out = out

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return self._out


class _StubRegistry:
    def __init__(self, skills: dict[str, _StubSkill]) -> None:
        self._skills = skills

    def get(self, skill_id: str, *, version: str | None = None) -> _StubSkill:
        return self._skills[skill_id]


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def _fake_citation(**overrides: Any) -> dict[str, Any]:
    base = {
        "doc_id": "0000320193/0000320193-23-000106",
        "statement_role": "income_statement",
        "locator": "0000320193/0000320193-23-000106::income_statement::revenue",
        "excerpt_hash": "a" * 64,
        "value": 383285000000.0,
        "retrieved_at": datetime(2026, 4, 17, tzinfo=timezone.utc).isoformat(),
    }
    base.update(overrides)
    return base


@pytest.mark.requires_live_data
def test_happy_path_real_citation_from_apple() -> None:
    """A real Apple FY2023 revenue citation resolves and passes numeric drift."""
    # Use the real Apple revenue line item — we know it resolves via the
    # facts store + canonical statements because Phase 4 validated it.
    from mvp.standardize.statements import build_canonical_statements

    stmts = build_canonical_statements("0000320193/0000320193-23-000106")
    revenue_li = next(
        (li for s in stmts for li in s.line_items if li.name == "revenue"), None
    )
    assert revenue_li is not None
    failure = _check_one(
        case_id="apple_test",
        skill_id="compute_beneish_m_score",
        cite_raw=revenue_li.citation.model_dump(mode="json"),
    )
    assert failure is None


def test_unresolved_doc_id_shape_reported() -> None:
    cite_raw = _fake_citation(
        doc_id="unknown_doc_id_with_no_slash",
        locator="unknown_doc_id_with_no_slash::income_statement::revenue",
    )
    failure = _check_one(
        case_id="toy",
        skill_id="compute_beneish_m_score",
        cite_raw=cite_raw,
    )
    assert failure is not None
    assert failure.failure_mode == "unresolved"


def test_numeric_match_within_tolerance() -> None:
    # A citation's value should appear in the passage text.
    cite = Citation(
        doc_id="x/y",
        statement_role="income_statement",
        locator="x/y::income_statement::revenue",
        excerpt_hash="a" * 64,
        value=100.0,
        retrieved_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    passage_exact = "revenue (usd) = 100.0"
    assert _check_numeric_match(cite=cite, passage=passage_exact) is None
    passage_close = "revenue (usd) = 100.4"  # 0.4% drift, under 0.5% cap
    assert _check_numeric_match(cite=cite, passage=passage_close) is None


def test_numeric_match_beyond_tolerance_fails() -> None:
    cite = Citation(
        doc_id="x/y",
        statement_role="income_statement",
        locator="x/y::income_statement::revenue",
        excerpt_hash="a" * 64,
        value=100.0,
        retrieved_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    passage_far = "revenue (usd) = 500.0"  # 400% drift
    msg = _check_numeric_match(cite=cite, passage=passage_far)
    assert msg is not None
    assert "no numeric literal within" in msg


def test_numeric_match_none_for_string_value() -> None:
    cite = Citation(
        doc_id="x/y",
        statement_role="income_statement",
        locator="x/y::income_statement::some_text",
        excerpt_hash="a" * 64,
        value="narrative_excerpt",
        retrieved_at=datetime(2026, 4, 17, tzinfo=timezone.utc),
    )
    # String-valued citations bypass numeric check.
    assert _check_numeric_match(cite=cite, passage="anything goes") is None


def test_malformed_citation_becomes_schema_failure() -> None:
    cite_raw = {"doc_id": "x/y"}  # missing every other required field
    failure = _check_one(
        case_id="toy",
        skill_id="compute_beneish_m_score",
        cite_raw=cite_raw,
    )
    assert failure is not None
    assert failure.failure_mode == "citation_schema_invalid"


def test_non_dict_citation_flagged() -> None:
    failure = _check_one(
        case_id="toy",
        skill_id="compute_beneish_m_score",
        cite_raw="not_a_dict",
    )
    assert failure is not None
    assert failure.failure_mode == "non_dict_citation"


def test_check_citations_empty_registry() -> None:
    # Empty skill_inputs → zero citations, rate 1.0 by convention.
    class _EmptyRegistry:
        def get(self, skill_id: str, *, version: str | None = None) -> Any:
            raise KeyError(skill_id)

    # Passing an explicit empty case_results list avoids the gold-load branch.
    report = check_citations(
        case_results=[], registry=_EmptyRegistry()
    )
    assert report.total_citations == 0
    assert report.resolution_rate == 1.0


def test_format_console_report_happy_and_failure() -> None:
    clean = CitationReport(total_citations=10, resolved=10, failures=[])
    assert "100.00%" in format_console_report(clean)

    broken = CitationReport(
        total_citations=10,
        resolved=9,
        failures=[
            CitationFailure(
                case_id="toy",
                skill_id="compute_beneish_m_score",
                doc_id="x/y",
                locator="x/y::income_statement::revenue",
                failure_mode="unresolved",
                detail="line_item_not_found",
            )
        ],
    )
    text = format_console_report(broken)
    assert "90.00%" in text
    assert "unresolved" in text
    assert "toy" in text
