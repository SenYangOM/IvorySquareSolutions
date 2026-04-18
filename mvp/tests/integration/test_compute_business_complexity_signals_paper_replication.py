"""Paper-replication test for compute_business_complexity_signals.

Paper: Bernard, D., Cade, N. L., Connors, E. H., & de Kok, T.
(2025), "Descriptive evidence on small business managers'
information choices," Review of Accounting Studies, 30, 3254-3294,
DOI 10.1007/s11142-025-09885-5, Section 4 / Table 3 Panel a.

Replication strategy
====================

The paper publishes per-regressor OLS coefficients (Table 3 Panel a
column 1 — extensive-margin email-open regression) but NOT firm-year
business-complexity scores (the score is our composite — the paper
does not define a composite). We therefore replicate the paper's
regression-level evidence rather than its score-mean:

1. **Weight derivation faithfulness.** The three shipped weights
   must match the normalisation of Table 3 Panel a column 1
   absolute t-statistics: {size=3.0, stability=2.8, complexity=3.7}.
   Sum 9.5. Within 1e-3.
2. **Per-signal threshold faithfulness.** The three binary cutoffs
   match the practitioner-derived defaults documented in the rule
   template ($1B revenue, 10% YoY stability, 15% SG&A / Revenue).
3. **Signal-level monotonicity.** Synthetic firm-year fixtures hit
   each band correctly: a $5B-revenue fixture fires size; a stable
   fixture fires stability; a high-SG&A-intensity fixture fires
   complexity; etc.
4. **Sign-reversal faithfulness.** Because two of the three
   indicators encode the paper's NEGATIVE coefficients via sign-
   reversal in the binary, dedicated tests confirm:
   - A volatile firm (|dRev/Rev| > 0.10) does NOT fire stability
   - A stable firm (|dRev/Rev| <= 0.10) DOES fire stability
   - A low-SG&A firm (SG&A/Rev < 0.15) does NOT fire complexity
   - A high-SG&A firm (SG&A/Rev >= 0.15) DOES fire complexity
5. **Composite arithmetic.** When all three signals fire, score =
   1.0 (within float tolerance). When none fire, score = 0.0. When
   only size fires, score = w_size = 0.3158. Tests the weighted-sum
   implementation against the documented weights.
6. **Soft real-filing sanity check.** All 5 MVP issuers produce
   non-null scores and non-null flags.
"""

from __future__ import annotations

import math

import pytest

from mvp.skills.paper_derived.compute_business_complexity_signals.skill import (
    WEIGHTS,
    _COMPLEXITY_SGA_INTENSITY_THRESHOLD,
    _FLAG_COMPLEX_THRESHOLD,
    _FLAG_MODERATE_THRESHOLD,
    _PAPER_ABS_T_STATS,
    _SIZE_REVENUE_THRESHOLD_USD,
    _STABILITY_YOY_THRESHOLD,
    _compute_fired_components,
    _compute_score_and_flag,
    _compute_signals,
)
from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


# ---------------------------------------------------------------------------
# (1) Weight derivation faithfulness — must match Table 3 Panel a |t-stats|.
# ---------------------------------------------------------------------------


def test_paper_abs_t_stats_match_table_3_panel_a_column_1() -> None:
    """Bernard et al. (2025) Table 3 Panel a col 1 absolute t-statistics.

    Computed as |coefficient| / standard_error for each kept regressor:
        size:       |+0.003| / 0.001 = 3.0
        stability:  |-0.098| / 0.035 = 2.8
        complexity: |-0.100| / 0.027 = 3.7
    """
    assert _PAPER_ABS_T_STATS["size"] == 3.0
    assert _PAPER_ABS_T_STATS["stability"] == 2.8
    assert _PAPER_ABS_T_STATS["complexity"] == 3.7


def test_weights_normalise_t_stats_to_sum_to_one() -> None:
    """The three weights are the three |t-stats| divided by their sum (9.5)."""
    total = sum(_PAPER_ABS_T_STATS.values())
    assert math.isclose(total, 9.5, abs_tol=1e-9)
    for name, t in _PAPER_ABS_T_STATS.items():
        expected = round(t / total, 4)
        assert math.isclose(WEIGHTS[name], expected, abs_tol=1e-4), (
            f"weight {name}: got {WEIGHTS[name]} expected {expected}"
        )
    # Sum of normalised weights must be ≈ 1.0 (modulo per-weight rounding).
    assert math.isclose(sum(WEIGHTS.values()), 1.0, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# (2) Per-signal threshold faithfulness.
# ---------------------------------------------------------------------------


def test_size_threshold_pin() -> None:
    """$1B revenue — "large cap" practitioner default."""
    assert _SIZE_REVENUE_THRESHOLD_USD == 1_000_000_000.0


def test_stability_threshold_pin() -> None:
    """10% YoY revenue delta — "stable growth" practitioner cutoff."""
    assert _STABILITY_YOY_THRESHOLD == 0.10


def test_complexity_threshold_pin() -> None:
    """15% SG&A / Revenue — "substantial corporate overhead" practitioner cutoff."""
    assert _COMPLEXITY_SGA_INTENSITY_THRESHOLD == 0.15


def test_flag_band_thresholds_pin() -> None:
    """Composite flag bands at 0.30 and 0.60 — presentation convention."""
    assert _FLAG_COMPLEX_THRESHOLD == 0.60
    assert _FLAG_MODERATE_THRESHOLD == 0.30


# ---------------------------------------------------------------------------
# (3) Signal-level monotonicity — synthetic firm-year fixtures.
# ---------------------------------------------------------------------------


def _values(
    *,
    revenue: float | None = 5_000_000_000.0,
    sga: float | None = 100_000_000.0,
) -> dict[str, float | None]:
    return {
        "revenue": revenue,
        "selling_general_admin_expense": sga,
    }


def test_size_signal_fires_when_revenue_large() -> None:
    """Revenue $5B > $1B threshold → size fires."""
    cur = _values(revenue=5_000_000_000.0)
    sig = _compute_signals(cur_values=cur, prior_values=None)
    components = _compute_fired_components(sig)
    assert components["size_fired"] == 1


def test_size_signal_does_not_fire_when_revenue_small() -> None:
    """Revenue $500M < $1B threshold → size does not fire."""
    cur = _values(revenue=500_000_000.0)
    sig = _compute_signals(cur_values=cur, prior_values=None)
    components = _compute_fired_components(sig)
    assert components["size_fired"] == 0


def test_size_signal_null_when_revenue_missing() -> None:
    """Null revenue → size_fired is null."""
    cur = _values(revenue=None)
    sig = _compute_signals(cur_values=cur, prior_values=None)
    components = _compute_fired_components(sig)
    assert components["size_fired"] is None
    assert sig["revenue_usd"] is None


# ---------------------------------------------------------------------------
# (4) Sign-reversal faithfulness — stability fires on LOW volatility.
# ---------------------------------------------------------------------------


def test_stability_signal_fires_when_yoy_revenue_stable() -> None:
    """|dRev/Rev| = 0.05 <= 0.10 → stability fires."""
    cur = _values(revenue=10_500_000_000.0)    # up 5%
    prior = _values(revenue=10_000_000_000.0)
    sig = _compute_signals(cur_values=cur, prior_values=prior)
    # |10.5B − 10.0B| / 10.0B = 0.05 <= 0.10 → fires.
    assert sig["yoy_revenue_change"] == pytest.approx(0.05)
    components = _compute_fired_components(sig)
    assert components["stability_fired"] == 1


def test_stability_signal_does_not_fire_when_yoy_revenue_volatile() -> None:
    """|dRev/Rev| = 0.25 > 0.10 → stability does NOT fire (sign-reversed)."""
    cur = _values(revenue=12_500_000_000.0)    # up 25%
    prior = _values(revenue=10_000_000_000.0)
    sig = _compute_signals(cur_values=cur, prior_values=prior)
    assert sig["yoy_revenue_change"] == pytest.approx(0.25)
    components = _compute_fired_components(sig)
    assert components["stability_fired"] == 0


def test_stability_null_when_prior_year_missing() -> None:
    """No prior-year data → stability is null."""
    cur = _values(revenue=5_000_000_000.0)
    sig = _compute_signals(cur_values=cur, prior_values=None)
    components = _compute_fired_components(sig)
    assert components["stability_fired"] is None


# ---------------------------------------------------------------------------
# (5) Sign-reversal faithfulness — complexity fires on HIGH SG&A intensity.
# ---------------------------------------------------------------------------


def test_complexity_signal_fires_when_sga_intense() -> None:
    """SG&A / Rev = 0.20 >= 0.15 → complexity fires."""
    cur = _values(revenue=5_000_000_000.0, sga=1_000_000_000.0)  # 20%
    sig = _compute_signals(cur_values=cur, prior_values=None)
    assert sig["sga_to_revenue_ratio"] == pytest.approx(0.20)
    components = _compute_fired_components(sig)
    assert components["complexity_fired"] == 1


def test_complexity_signal_does_not_fire_when_sga_light() -> None:
    """SG&A / Rev = 0.05 < 0.15 → complexity does NOT fire."""
    cur = _values(revenue=5_000_000_000.0, sga=250_000_000.0)  # 5%
    sig = _compute_signals(cur_values=cur, prior_values=None)
    assert sig["sga_to_revenue_ratio"] == pytest.approx(0.05)
    components = _compute_fired_components(sig)
    assert components["complexity_fired"] == 0


def test_complexity_null_when_sga_missing() -> None:
    """Null SG&A → complexity is null."""
    cur = _values(revenue=5_000_000_000.0, sga=None)
    sig = _compute_signals(cur_values=cur, prior_values=None)
    components = _compute_fired_components(sig)
    assert components["complexity_fired"] is None


# ---------------------------------------------------------------------------
# (6) Composite arithmetic — weighted sum invariants.
# ---------------------------------------------------------------------------


def test_all_signals_off_score_is_zero() -> None:
    """Revenue populated, all three signals off → score 0.0, flag simple."""
    # Revenue must be populated so flag isn't "indeterminate".
    signals = {
        "revenue_usd": 500_000_000.0,   # small — won't fire size
        "yoy_revenue_change": 0.25,     # volatile — won't fire stability
        "sga_to_revenue_ratio": 0.05,   # light — won't fire complexity
    }
    components = {
        "size_fired": 0,
        "stability_fired": 0,
        "complexity_fired": 0,
    }
    score, flag = _compute_score_and_flag(components, signals)
    assert score == 0.0
    assert flag == "simple_monitoring_light"


def test_all_signals_on_score_is_one() -> None:
    """All three firing → score ≈ 1.0, flag complex_monitoring_intensive."""
    signals = {
        "revenue_usd": 10_000_000_000.0,
        "yoy_revenue_change": 0.03,
        "sga_to_revenue_ratio": 0.20,
    }
    components = {
        "size_fired": 1,
        "stability_fired": 1,
        "complexity_fired": 1,
    }
    score, flag = _compute_score_and_flag(components, signals)
    # Sum of weights — float-rounded.
    assert math.isclose(score, sum(WEIGHTS.values()), abs_tol=1e-3)
    assert flag == "complex_monitoring_intensive"


def test_only_size_fires_score_equals_size_weight() -> None:
    """Size-only fire → score = w_size = 0.3158, flag moderate."""
    signals = {
        "revenue_usd": 10_000_000_000.0,
        "yoy_revenue_change": 0.25,
        "sga_to_revenue_ratio": 0.05,
    }
    components = {
        "size_fired": 1,
        "stability_fired": 0,
        "complexity_fired": 0,
    }
    score, flag = _compute_score_and_flag(components, signals)
    assert math.isclose(score, WEIGHTS["size"], abs_tol=1e-9)
    # 0.3158 falls in the moderate band [0.30, 0.60).
    assert flag == "moderate_monitoring_intensity"


def test_size_plus_complexity_fires_complex() -> None:
    """Size + complexity → score ≈ 0.7053, flag complex."""
    signals = {
        "revenue_usd": 10_000_000_000.0,
        "yoy_revenue_change": 0.25,
        "sga_to_revenue_ratio": 0.20,
    }
    components = {
        "size_fired": 1,
        "stability_fired": 0,
        "complexity_fired": 1,
    }
    score, flag = _compute_score_and_flag(components, signals)
    expected = WEIGHTS["size"] + WEIGHTS["complexity"]
    assert math.isclose(score, expected, abs_tol=1e-9)
    # 0.3158 + 0.3895 = 0.7053 → above 0.60 → complex.
    assert flag == "complex_monitoring_intensive"


def test_indeterminate_when_revenue_missing() -> None:
    """Revenue null → all three signals unevaluable → indeterminate."""
    signals = {
        "revenue_usd": None,
        "yoy_revenue_change": None,
        "sga_to_revenue_ratio": None,
    }
    components = {
        "size_fired": None,
        "stability_fired": None,
        "complexity_fired": None,
    }
    score, flag = _compute_score_and_flag(components, signals)
    assert score is None
    assert flag == "indeterminate"


def test_revenue_populated_but_sga_missing_still_publishes() -> None:
    """Revenue populated, SG&A missing → complexity treated as not-fired;
    score still publishes.
    """
    signals = {
        "revenue_usd": 10_000_000_000.0,
        "yoy_revenue_change": 0.05,     # stable
        "sga_to_revenue_ratio": None,   # missing
    }
    components = {
        "size_fired": 1,
        "stability_fired": 1,
        "complexity_fired": None,        # null treated as not-fired
    }
    score, flag = _compute_score_and_flag(components, signals)
    expected = WEIGHTS["size"] + WEIGHTS["stability"]
    assert math.isclose(score, expected, abs_tol=1e-9)
    # Flag depends on score — Apple-like case.
    assert flag == "complex_monitoring_intensive"


# ---------------------------------------------------------------------------
# (7) Soft real-filing sanity check on the 5 MVP issuers.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_real_filings_produce_non_null_scores() -> None:
    """All 5 MVP issuers produce a non-null business_complexity_score
    and a non-null flag. This catches gross bugs (NaN propagation, type
    errors) without forcing us to pin specific scores — the scores
    depend on the practitioner thresholds documented in the manifest,
    which an accounting expert may legitimately edit in the rule
    template.
    """
    r = _fresh_registry()
    skill = r.get("compute_business_complexity_signals")
    cases = [
        ("0000320193", "2023-09-30", "Apple FY2023"),
        ("0001690820", "2022-12-31", "Carvana FY2022"),
        ("0001024401", "2000-12-31", "Enron FY2000"),
        ("0000723527", "2001-12-31", "WorldCom FY2001"),
        ("0000789019", "2023-06-30", "Microsoft FY2023"),
    ]
    for cik, fye, name in cases:
        out = skill.run({"cik": cik, "fiscal_year_end": fye})
        assert "error" not in out, f"{name}: {out}"
        score = out["business_complexity_score"]
        assert score is not None, f"{name}: got null score"
        assert 0.0 <= score <= 1.0, (
            f"{name}: score={score} outside [0, 1]"
        )
        assert out["flag"] in {
            "complex_monitoring_intensive",
            "moderate_monitoring_intensity",
            "simple_monitoring_light",
            "indeterminate",
        }, f"{name}: unexpected flag {out['flag']!r}"
        # Size should fire for every MVP filing (all are > $1B revenue).
        assert out["components"]["size_fired"] == 1, (
            f"{name}: size_fired expected 1, got {out['components']['size_fired']}"
        )


@pytest.mark.requires_live_data
def test_carvana_fires_all_three_signals() -> None:
    """Carvana FY2022 is the 'all three signals fire' anchor case:
    revenue 13.6B, YoY change ~6%, SG&A/Rev ~20%.
    Score should be at the composite ceiling (≈1.0, flag
    complex_monitoring_intensive)."""
    r = _fresh_registry()
    skill = r.get("compute_business_complexity_signals")
    out = skill.run({"cik": "0001690820", "fiscal_year_end": "2022-12-31"})
    assert "error" not in out
    assert out["components"]["size_fired"] == 1
    assert out["components"]["stability_fired"] == 1
    assert out["components"]["complexity_fired"] == 1
    assert out["flag"] == "complex_monitoring_intensive"
    # Score should be very close to 1.0 (sum of all three weights).
    assert out["business_complexity_score"] >= 0.99


@pytest.mark.requires_live_data
def test_enron_fires_only_size() -> None:
    """Enron FY2000 is the 'size-only' anchor case: revenue 100.8B (size
    fires), YoY change ~151% (stability does NOT fire — highly volatile,
    the inflated revenue growth that later turned out to be fictitious),
    SG&A/Rev ~3% (complexity does NOT fire). Score should be exactly
    w_size = 0.3158, flag moderate."""
    r = _fresh_registry()
    skill = r.get("compute_business_complexity_signals")
    out = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    assert "error" not in out
    assert out["components"]["size_fired"] == 1
    assert out["components"]["stability_fired"] == 0
    assert out["components"]["complexity_fired"] == 0
    assert out["flag"] == "moderate_monitoring_intensity"
    assert math.isclose(
        out["business_complexity_score"], WEIGHTS["size"], abs_tol=1e-3
    )
