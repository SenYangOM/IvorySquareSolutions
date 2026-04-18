"""Unit tests for compute_mdna_upfrontedness.

Splits into hermetic arithmetic tests (the Equations 8 + 9 helpers)
and live-data integration-smoke tests (runs the full skill against
the 5 MVP sample filings).

Arithmetic tests are always runnable. Live-data tests carry the
``requires_live_data`` marker and are auto-skipped on clean clones.
"""

from __future__ import annotations

import math

import pytest

from mvp.skills.paper_derived.compute_mdna_upfrontedness.skill import (
    _MIN_PARAGRAPHS,
    _PAPER_P25,
    _PAPER_P75,
    _flag_for,
    _split_paragraphs,
    _upfrontedness,
    _compute_confidence,
    _indeterminate_output,
)
from mvp.skills.registry import Registry, reset_default_registry


# ---------------------------------------------------------------------------
# Helpers for building paragraph test fixtures.
# ---------------------------------------------------------------------------


def _uniform(n: int, length: int = 100) -> list[str]:
    """Return ``n`` identical-length paragraphs."""
    return ["x" * length] * n


def _monotone_decreasing(n: int, start: int = 100) -> list[str]:
    """Lengths start, start-1, ..., start-(n-1) — longer at the front."""
    return ["x" * (start - k) for k in range(n)]


def _monotone_increasing(n: int, start: int = 51) -> list[str]:
    """Lengths start, start+1, ..., start+(n-1) — longer at the back."""
    return ["x" * (start + k) for k in range(n)]


# ---------------------------------------------------------------------------
# Equation 8 + 9 arithmetic.
# ---------------------------------------------------------------------------


def test_uniform_length_collapses_to_analytical_baseline() -> None:
    """Uniform-length → Equation 9 collapses to (N-1)/(2N)."""
    for n in (10, 25, 50, 100, 500):
        paragraphs = _uniform(n, length=120)
        score, diag = _upfrontedness(paragraphs)
        expected = (n - 1) / (2 * n)
        assert math.isclose(score, expected, abs_tol=1e-12), (
            f"N={n}: score={score} vs analytical {expected}"
        )
        assert diag["paragraph_count"] == n
        assert diag["total_characters"] == 120 * n


def test_monotone_decreasing_scores_above_uniform_baseline() -> None:
    """Long paragraphs at the front → score strictly above the uniform
    baseline of (N-1)/(2N).

    Note: for small N the uniform baseline sits below 0.5 (0.45 at N=10,
    0.48 at N=25). The paper's Upfrontedness sits around 0.5 because
    MD&A samples run N in the hundreds. We assert the positionally
    correct signed deviation from the uniform baseline, not an absolute
    cut at 0.5.
    """
    for n in (10, 25, 50, 100):
        paragraphs = _monotone_decreasing(n)
        score, _ = _upfrontedness(paragraphs)
        baseline = (n - 1) / (2 * n)
        assert score > baseline, (
            f"N={n} monotone-decreasing got score={score}; expected above "
            f"uniform baseline {baseline}"
        )


def test_monotone_increasing_scores_below_uniform_baseline() -> None:
    """Long paragraphs at the back → score strictly below the uniform
    baseline of (N-1)/(2N). Mirror of the decreasing test."""
    for n in (10, 25, 50, 100):
        paragraphs = _monotone_increasing(n)
        score, _ = _upfrontedness(paragraphs)
        baseline = (n - 1) / (2 * n)
        assert score < baseline, (
            f"N={n} monotone-increasing got score={score}; expected below "
            f"uniform baseline {baseline}"
        )


def test_monotone_decreasing_above_half_for_large_n() -> None:
    """For realistic MD&A sizes (N≥50) the monotone-decreasing construction
    produces a score above 0.5 — this matches the paper's ~0.5 mean on
    the 66,757-firm sample where N ≫ 50."""
    for n in (50, 100, 200):
        paragraphs = _monotone_decreasing(n)
        score, _ = _upfrontedness(paragraphs)
        assert score > 0.5, f"N={n} got score={score}"


def test_monotone_increasing_below_half_for_large_n() -> None:
    """Mirror for realistic MD&A sizes."""
    for n in (50, 100, 200):
        paragraphs = _monotone_increasing(n)
        score, _ = _upfrontedness(paragraphs)
        assert score < 0.5, f"N={n} got score={score}"


def test_monotone_decreasing_vs_increasing_symmetric_around_uniform() -> None:
    """For any N, monotone_decreasing(N) and monotone_increasing(N)
    should sit symmetrically around the uniform baseline — differences
    in character lengths aside. We assert the signs correctly flip."""
    n = 50
    dec_score, _ = _upfrontedness(_monotone_decreasing(n))
    inc_score, _ = _upfrontedness(_monotone_increasing(n))
    base = (n - 1) / (2 * n)
    # Magnitudes of the deviation from base should be close (not exactly
    # equal because the two constructions have different total_length
    # distributions), but they MUST sit on opposite sides of base.
    assert dec_score > base > inc_score


def test_one_huge_paragraph_up_front_dominates() -> None:
    """One very long paragraph at position 1 pushes the score high."""
    paragraphs = ["x" * 10000] + _uniform(49, length=100)
    score, diag = _upfrontedness(paragraphs)
    assert score > 0.80, f"expected score > 0.80, got {score}"
    assert diag["longest_paragraph_index"] == 1
    assert math.isclose(
        diag["longest_paragraph_position_score"], 1 - 1 / 50, abs_tol=1e-12
    )


def test_one_huge_paragraph_at_tail_drops_score() -> None:
    """Mirror — one very long paragraph at the last position pulls it low."""
    paragraphs = _uniform(49, length=100) + ["x" * 10000]
    score, diag = _upfrontedness(paragraphs)
    assert score < 0.20, f"expected score < 0.20, got {score}"
    assert diag["longest_paragraph_index"] == 50
    assert diag["longest_paragraph_position_score"] == 0.0


def test_upfrontedness_raises_on_all_empty_paragraphs() -> None:
    """The helper rejects an all-empty fixture loudly rather than divide by zero."""
    with pytest.raises(ValueError):
        _upfrontedness(["", "", ""])


# ---------------------------------------------------------------------------
# _split_paragraphs.
# ---------------------------------------------------------------------------


def test_split_paragraphs_separates_on_blank_lines() -> None:
    text = (
        "First paragraph with real content for the test.\n"
        "\n"
        "Second paragraph likewise has enough text to survive.\n"
        "\n\n"
        "Third paragraph is also long enough.\n"
    )
    parts = _split_paragraphs(text)
    assert len(parts) == 3
    assert parts[0].startswith("First")
    assert parts[1].startswith("Second")
    assert parts[2].startswith("Third")


def test_split_paragraphs_filters_short_fragments() -> None:
    """Fragments under 20 chars are dropped."""
    text = (
        "Item 7.\n"
        "\n"
        "Short\n"
        "\n"
        "This paragraph has enough content to survive the filter.\n"
        "\n"
        "(a)\n"
        "\n"
        "Another long-enough paragraph for the test here.\n"
    )
    parts = _split_paragraphs(text)
    assert len(parts) == 2
    assert "enough content" in parts[0]
    assert "long-enough paragraph" in parts[1]


# ---------------------------------------------------------------------------
# Flag boundary.
# ---------------------------------------------------------------------------


def test_flag_boundaries_are_paper_exact() -> None:
    assert _flag_for(0.5283) == "forthcoming"
    assert _flag_for(0.5283 + 1e-6) == "forthcoming"
    assert _flag_for(0.5012) == "typical"
    assert _flag_for(0.5012 + 1e-6) == "typical"
    assert _flag_for(0.5283 - 1e-6) == "typical"
    assert _flag_for(0.5012 - 1e-6) == "obfuscating_likely"
    assert _flag_for(0.0) == "obfuscating_likely"
    assert _flag_for(1.0) == "forthcoming"


def test_paper_quartile_constants_match_appendix_d() -> None:
    """Kim et al. (2024) Appendix D Panel A: P25=0.5012, P75=0.5283."""
    assert _PAPER_P25 == 0.5012
    assert _PAPER_P75 == 0.5283
    assert _MIN_PARAGRAPHS == 10


# ---------------------------------------------------------------------------
# Confidence + indeterminate output.
# ---------------------------------------------------------------------------


def test_confidence_is_zero_for_indeterminate() -> None:
    assert _compute_confidence(pre_ixbrl=False, indeterminate=True) == 0.0
    assert _compute_confidence(pre_ixbrl=True, indeterminate=True) == 0.0


def test_confidence_drops_for_pre_ixbrl() -> None:
    high = _compute_confidence(pre_ixbrl=False, indeterminate=False)
    low = _compute_confidence(pre_ixbrl=True, indeterminate=False)
    assert high == 0.7
    assert low == 0.55
    assert high > low


def test_indeterminate_output_shape_matches_schema() -> None:
    out = _indeterminate_output(
        warnings=["something went wrong"],
        cur_filing_id="0000000000/fake-accession",
    )
    assert out["upfrontedness_score"] is None
    assert out["flag"] == "indeterminate"
    assert out["paragraph_count"] == 0
    assert out["components"]["mean_paragraph_position"] is None
    assert out["citations"] == []
    assert out["confidence"] == 0.0
    assert "something went wrong" in out["warnings"][0]
    assert out["provenance"]["cur_filing_id"] == "0000000000/fake-accession"


# ---------------------------------------------------------------------------
# Skill error-path (registry + unknown filing).
# ---------------------------------------------------------------------------


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


def test_unknown_filing_returns_structured_error() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "9999999999", "fiscal_year_end": "2030-12-31"})
    assert "error" in out
    assert out["error"]["error_code"] == "unknown_filing"
    assert out["error"]["retry_safe"] is False


def test_input_schema_rejects_missing_cik() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"fiscal_year_end": "2023-09-30"})
    assert "error" in out
    assert out["error"]["error_code"] == "input_validation"


def test_input_schema_rejects_extra_keys() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run(
        {
            "cik": "0000320193",
            "fiscal_year_end": "2023-09-30",
            "some_extra_key": "nope",
        }
    )
    assert "error" in out
    assert out["error"]["error_code"] == "input_validation"


# ---------------------------------------------------------------------------
# Live-data happy paths (requires_live_data — skipped on clean clones).
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_apple_happy_path() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert "error" not in out
    # Apple's MD&A is valid (extract_mdna returns a section),
    # paragraph_count > 10, score is a real number in [0, 1].
    assert out["paragraph_count"] >= _MIN_PARAGRAPHS
    assert out["upfrontedness_score"] is not None
    assert 0.0 <= out["upfrontedness_score"] <= 1.0
    assert out["flag"] in {"forthcoming", "typical", "obfuscating_likely"}
    assert out["confidence"] == 0.7  # modern iXBRL, proxy active
    assert any(
        "paragraph_importance_proxy_used" in w for w in out["warnings"]
    )


@pytest.mark.requires_live_data
def test_microsoft_returns_indeterminate_due_to_mdna_extraction() -> None:
    """Microsoft FY2023 is a known extract_mdna edge — the finder
    truncates the section. Our skill propagates indeterminate cleanly
    rather than computing on a one-paragraph fixture."""
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0000789019", "fiscal_year_end": "2023-06-30"})
    assert "error" not in out
    assert out["flag"] == "indeterminate"
    assert out["upfrontedness_score"] is None
    assert out["confidence"] == 0.0
    assert any(
        "mdna_too_short" in w or "mdna_section_not_located" in w
        for w in out["warnings"]
    )


@pytest.mark.requires_live_data
def test_enron_pre_ixbrl_confidence_penalty() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    assert "error" not in out
    # Enron's MD&A is long and SGML-era — we expect a computable score
    # with the pre-iXBRL confidence penalty applied (0.7 − 0.15 = 0.55).
    assert out["upfrontedness_score"] is not None
    assert out["confidence"] == 0.55
    assert any(
        "pre_ixbrl_paragraph_structure" in w for w in out["warnings"]
    )


@pytest.mark.requires_live_data
def test_worldcom_is_scorable() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0000723527", "fiscal_year_end": "2001-12-31"})
    assert "error" not in out
    assert out["upfrontedness_score"] is not None
    assert 0.0 <= out["upfrontedness_score"] <= 1.0
    assert any(
        "pre_ixbrl_paragraph_structure" in w for w in out["warnings"]
    )


@pytest.mark.requires_live_data
def test_carvana_is_scorable() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0001690820", "fiscal_year_end": "2022-12-31"})
    assert "error" not in out
    assert out["upfrontedness_score"] is not None
    assert 0.0 <= out["upfrontedness_score"] <= 1.0
    # Carvana is iXBRL-era so no pre-iXBRL warning.
    assert not any(
        "pre_ixbrl_paragraph_structure" in w for w in out["warnings"]
    )
    assert out["confidence"] == 0.7


@pytest.mark.requires_live_data
def test_citation_locator_resolves_to_mdna() -> None:
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert "error" not in out
    citations = out["citations"]
    assert len(citations) == 1
    c = citations[0]
    assert "::mdna::item_7" in c["locator"]
    # sha256 excerpt hash — 64 hex chars
    assert len(c["excerpt_hash"]) == 64


@pytest.mark.requires_live_data
def test_determinism_back_to_back_calls_produce_same_score() -> None:
    """Two runs back-to-back must produce identical scores modulo the
    volatile provenance timestamps."""
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    a = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    b = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert a["upfrontedness_score"] == b["upfrontedness_score"]
    assert a["flag"] == b["flag"]
    assert a["paragraph_count"] == b["paragraph_count"]
    assert a["components"] == b["components"]
