"""Paper-replication test for compute_mdna_upfrontedness.

Paper: Kim, Muhn, Nikolaev & Zhang (2024), "Learning Fundamentals from
Text," §VI Equations 8 and 9, Appendix D Panel A distribution.

Replication strategy. The paper publishes a population distribution
(N=66,757, mean=0.5161, std=0.0243, P25=0.5012, P50=0.5143, P75=0.5283)
of their attention-model-weighted Upfrontedness, NOT per-firm values.
Our skill ships a length-share PROXY for paragraph importance (see
manifest implementation_decisions[0] and the notes file at
``workshop/paper_to_skill/notes/fundamentals_text.md`` §e).

We therefore replicate the paper's **equations**, not its
**distribution mean**. The test asserts:

1. Equation 8 + 9 faithfulness on a **uniform-length** construction.
   The length-share proxy collapses to uniform importance and the
   score hits the closed-form ``(N-1)/(2N)`` baseline exactly. This
   is the strongest possible paper-replication bar for the
   arithmetic — within 1e-10 of the analytical value, tighter than
   the ±0.05 bar the success_criteria §4.1 specifies for headline
   metrics.
2. Equation 9 direction on a **monotone-decreasing** construction:
   long paragraphs at the front must produce a score above the
   uniform baseline, by a meaningful margin (> 0.01 for N=50).
3. Equation 9 direction mirror on **monotone-increasing**: long
   paragraphs at the back must produce a score below the uniform
   baseline, again by > 0.01 at N=50.
4. **Degenerate** front/tail constructions hit score > 0.80 and
   < 0.20 respectively — shows the metric covers [0, 1] correctly
   when one paragraph dominates.
5. Soft distribution sanity check on real MVP filings (Apple,
   Carvana, Enron, WorldCom — the four scorable cases): all scores
   land in [0.40, 0.55] — a generous band that accepts the proxy's
   known bias against the paper's attention-model mean.
"""

from __future__ import annotations

import math

import pytest

from mvp.skills.paper_derived.compute_mdna_upfrontedness.skill import (
    _upfrontedness,
)
from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


# ---------------------------------------------------------------------------
# (1) Equation 8/9 faithfulness — uniform-length closed form.
# ---------------------------------------------------------------------------


def test_equations_8_9_uniform_length_matches_closed_form() -> None:
    """With uniform paragraph lengths, Equation 9 reduces to the
    closed-form position-average (N-1)/(2N). Tests Equation 8 indexing
    AND Equation 9 summation in one assertion.
    """
    for n in (10, 50, 100, 500):
        paragraphs = ["x" * 100] * n
        score, _ = _upfrontedness(paragraphs)
        expected = (n - 1) / (2 * n)
        assert math.isclose(score, expected, abs_tol=1e-10), (
            f"N={n}: score={score} vs closed-form {expected}"
        )


# ---------------------------------------------------------------------------
# (2) + (3) Directionality — monotone-decreasing and increasing.
# ---------------------------------------------------------------------------


def test_equation_9_direction_monotone_decreasing_above_baseline() -> None:
    """Monotone-decreasing lengths (long at front) produce a score
    above the uniform baseline by a meaningful margin (>0.01 at N=50)."""
    n = 50
    baseline = (n - 1) / (2 * n)
    paragraphs = ["x" * (100 - k) for k in range(n)]  # 100, 99, ..., 51
    score, _ = _upfrontedness(paragraphs)
    assert score - baseline > 0.01, (
        f"N={n} monotone-decreasing score={score} baseline={baseline}; "
        f"expected margin > 0.01"
    )


def test_equation_9_direction_monotone_increasing_below_baseline() -> None:
    """Mirror — long at back drops score by a meaningful margin."""
    n = 50
    baseline = (n - 1) / (2 * n)
    paragraphs = ["x" * (51 + k) for k in range(n)]  # 51, 52, ..., 100
    score, _ = _upfrontedness(paragraphs)
    assert baseline - score > 0.01, (
        f"N={n} monotone-increasing score={score} baseline={baseline}; "
        f"expected margin > 0.01"
    )


# ---------------------------------------------------------------------------
# (4) Degenerate constructions cover the [0, 1] range.
# ---------------------------------------------------------------------------


def test_huge_first_paragraph_score_above_0_80() -> None:
    """One very long paragraph at position 1, rest uniform small — the
    length-share importance concentrates there, and the position score
    is (N-1)/N ≈ 1."""
    paragraphs = ["x" * 10_000] + ["x" * 100] * 49
    score, _ = _upfrontedness(paragraphs)
    assert score > 0.80, f"expected >0.80, got {score}"


def test_huge_last_paragraph_score_below_0_20() -> None:
    """Mirror — length concentrated at the last position (score 0)."""
    paragraphs = ["x" * 100] * 49 + ["x" * 10_000]
    score, _ = _upfrontedness(paragraphs)
    assert score < 0.20, f"expected <0.20, got {score}"


# ---------------------------------------------------------------------------
# (5) Soft distribution sanity check on real MVP filings.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_real_filings_produce_scores_in_sensible_band() -> None:
    """The four scorable MVP filings (Apple, Carvana, Enron, WorldCom)
    all produce Upfrontedness in [0.40, 0.55]. This is generous
    relative to the paper's Appendix D distribution [0.4675, 0.5647]
    (95% band) because our length-share proxy is known to bias scores
    downward on modern filings with dense late-MD&A content. The
    assertion catches gross bugs (negative scores, scores > 1, swapped
    indexing) without forcing us to reproduce the paper's 0.5161
    population mean (which depends on the unreleased attention model).

    Microsoft is excluded from this check because extract_mdna
    truncates its FY2023 MD&A to a single paragraph and the score is
    correctly indeterminate.
    """
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    cases = [
        ("0000320193", "2023-09-30", "Apple FY2023"),
        ("0001690820", "2022-12-31", "Carvana FY2022"),
        ("0001024401", "2000-12-31", "Enron FY2000"),
        ("0000723527", "2001-12-31", "WorldCom FY2001"),
    ]
    for cik, fye, name in cases:
        out = skill.run({"cik": cik, "fiscal_year_end": fye})
        assert "error" not in out, f"{name}: {out}"
        score = out["upfrontedness_score"]
        assert score is not None, f"{name}: got null score"
        assert 0.40 <= score <= 0.55, (
            f"{name}: score={score} outside [0.40, 0.55] — "
            f"possible bug or structural filing anomaly"
        )


@pytest.mark.requires_live_data
def test_flag_is_derived_deterministically_from_score() -> None:
    """For any real filing, the flag must match the paper-quartile
    derivation from the score."""
    r = _fresh_registry()
    skill = r.get("compute_mdna_upfrontedness")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    score = out["upfrontedness_score"]
    flag = out["flag"]
    if score >= 0.5283:
        assert flag == "forthcoming"
    elif score >= 0.5012:
        assert flag == "typical"
    else:
        assert flag == "obfuscating_likely"


# ---------------------------------------------------------------------------
# (6) Coefficient + threshold pins — the paper's printed values.
# ---------------------------------------------------------------------------


def test_paper_p25_and_p75_are_as_printed_in_appendix_d() -> None:
    """Kim et al. (2024) Appendix D Panel A, reported quartiles."""
    from mvp.skills.paper_derived.compute_mdna_upfrontedness.skill import (
        _PAPER_P25,
        _PAPER_P75,
    )

    assert _PAPER_P25 == 0.5012
    assert _PAPER_P75 == 0.5283


def test_min_paragraphs_matches_paper_regression_sample() -> None:
    """The paper's §VI.A regression sample uses N ≥ 10 paragraphs;
    our indeterminate floor matches."""
    from mvp.skills.paper_derived.compute_mdna_upfrontedness.skill import (
        _MIN_PARAGRAPHS,
    )

    assert _MIN_PARAGRAPHS == 10
