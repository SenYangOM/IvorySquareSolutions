"""Paper-replication test for compute_context_importance_signals.

Paper: Kim, A. G., & Nikolaev, V. V. (2024), "Context-Based
Interpretation of Financial Information," J. Accounting Research,
DOI 10.1111/1475-679X.12593, §5.4 Table 7 Panel A.

Replication strategy
====================

The paper publishes per-signal contextuality differences (Table 7
Panel A) but NOT firm-year context-importance scores (the score is
our composite — the paper's headline contextuality measure is the
unreleased BERT+ANN accuracy delta which we explicitly do NOT
implement). We therefore replicate the paper's signal-level evidence
rather than its score-mean:

1. **Weight derivation faithfulness.** The four shipped weights must
   match the normalisation of Table 7 Panel A column "Earnings", row
   "Diff" statistics: {Loss=2.94, Volatility=1.79, Accruals=1.34,
   MTB=1.50}. Sum 7.57. Within 1e-3.
2. **Per-signal threshold faithfulness.** The four binary cutoffs
   match the practitioner-derived defaults documented in the rule
   template (vol ≥ 0.05, |accr| ≥ 0.10, MTB ≥ 5.0 / ≤ 0.8).
3. **Signal-level monotonicity.** Synthetic firm-year fixtures hit
   each band correctly: a loss firm fires loss; a vol > 0.05 firm
   fires vol; an extreme MTB firm fires the right MTB band; etc.
4. **Composite arithmetic.** When all four signals fire, score = 1.0
   (within float tolerance). When none fire, score = 0.0. When only
   loss fires, score = w_loss = 0.3884. Tests the weighted-sum
   implementation against the documented weights.
5. **Soft real-filing sanity check.** All 5 MVP issuers produce
   non-null scores (Carvana via the negative-book-equity MTB encoding
   path) and a non-null flag.
"""

from __future__ import annotations

import math

import pytest

from mvp.skills.paper_derived.compute_context_importance_signals.skill import (
    WEIGHTS,
    _ACCRUALS_THRESHOLD,
    _FLAG_CRITICAL_THRESHOLD,
    _FLAG_HELPFUL_THRESHOLD,
    _MTB_HIGH_THRESHOLD,
    _MTB_LOW_THRESHOLD,
    _PAPER_DIFFS,
    _VOLATILITY_THRESHOLD,
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
# (1) Weight derivation faithfulness — must match Table 7 Panel A.
# ---------------------------------------------------------------------------


def test_paper_diffs_match_table_7_panel_a_earnings_column() -> None:
    """Kim & Nikolaev (2024) Table 7 Panel A, column 'Earnings', row 'Diff'."""
    assert _PAPER_DIFFS["loss"] == 2.94
    assert _PAPER_DIFFS["volatility"] == 1.79
    assert _PAPER_DIFFS["accruals"] == 1.34
    assert _PAPER_DIFFS["mtb"] == 1.50


def test_weights_normalise_diffs_to_sum_to_one() -> None:
    """The four weights are the four Diffs divided by their sum (7.57)."""
    total = sum(_PAPER_DIFFS.values())
    assert math.isclose(total, 7.57, abs_tol=1e-9)
    for name, diff in _PAPER_DIFFS.items():
        expected = round(diff / total, 4)
        assert math.isclose(WEIGHTS[name], expected, abs_tol=1e-4), (
            f"weight {name}: got {WEIGHTS[name]} expected {expected}"
        )
    # Sum of normalised weights must be ≈ 1.0 (modulo per-weight rounding).
    assert math.isclose(sum(WEIGHTS.values()), 1.0, abs_tol=1e-3)


# ---------------------------------------------------------------------------
# (2) Per-signal threshold faithfulness.
# ---------------------------------------------------------------------------


def test_volatility_threshold_pin() -> None:
    """5pp YoY ROA swing — practitioner default."""
    assert _VOLATILITY_THRESHOLD == 0.05


def test_accruals_threshold_pin() -> None:
    """10% of assets — Sloan-1996-style decile cutoff for 'extreme'."""
    assert _ACCRUALS_THRESHOLD == 0.10


def test_mtb_thresholds_pin() -> None:
    """Beaver-Ryan (2005) growth (5.0) / value (0.8) extremity defaults."""
    assert _MTB_HIGH_THRESHOLD == 5.0
    assert _MTB_LOW_THRESHOLD == 0.8


def test_flag_band_thresholds_pin() -> None:
    """Composite flag bands at 0.30 and 0.60 — presentation convention."""
    assert _FLAG_CRITICAL_THRESHOLD == 0.60
    assert _FLAG_HELPFUL_THRESHOLD == 0.30


# ---------------------------------------------------------------------------
# (3) Signal-level monotonicity — synthetic firm-year fixtures.
# ---------------------------------------------------------------------------


def _values(
    *,
    ebit: float | None = 100.0,
    total_assets: float = 1000.0,
    total_liabilities: float = 500.0,
    cfo: float | None = 80.0,
) -> dict[str, float | None]:
    return {
        "ebit": ebit,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "cash_flow_from_operating_activities": cfo,
    }


class _Mve:
    def __init__(self, mve: float) -> None:
        self.mve = mve
        # Other fields used for citation building are not exercised here.
        self.cik = "0000000000"
        self.fiscal_year_end = "2026-12-31"
        self.shares_outstanding = 1
        self.share_price_usd = mve
        self.market_cap_source = None
        self.shares_source_flag = None


def test_loss_signal_fires_when_ebit_negative() -> None:
    cur = _values(ebit=-50.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=None)
    assert sig["loss"] == 1


def test_loss_signal_does_not_fire_when_ebit_positive() -> None:
    cur = _values(ebit=100.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=None)
    assert sig["loss"] == 0


def test_volatility_signal_fires_when_yoy_roa_swings_above_threshold() -> None:
    cur = _values(ebit=200.0, total_assets=1000.0)   # ROA_t = 0.20
    prior = _values(ebit=80.0, total_assets=1000.0)  # ROA_{t-1} = 0.08
    sig = _compute_signals(cur_values=cur, prior_values=prior, mve_entry=None)
    # |0.20 − 0.08| = 0.12 ≥ 0.05 → fires.
    assert sig["volatility"] is not None
    assert sig["volatility"] >= _VOLATILITY_THRESHOLD
    components = _compute_fired_components(sig)
    assert components["volatility_fired"] == 1


def test_volatility_signal_does_not_fire_when_yoy_roa_steady() -> None:
    cur = _values(ebit=100.0, total_assets=1000.0)
    prior = _values(ebit=98.0, total_assets=1000.0)
    sig = _compute_signals(cur_values=cur, prior_values=prior, mve_entry=None)
    # |0.10 − 0.098| = 0.002 < 0.05 → does not fire.
    components = _compute_fired_components(sig)
    assert components["volatility_fired"] == 0


def test_accruals_signal_fires_when_ebit_minus_cfo_above_threshold() -> None:
    cur = _values(ebit=200.0, total_assets=1000.0, cfo=50.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=None)
    # |200 − 50| / 1000 = 0.15 ≥ 0.10 → fires.
    assert sig["accruals"] == pytest.approx(0.15)
    components = _compute_fired_components(sig)
    assert components["accruals_fired"] == 1


def test_accruals_signal_does_not_fire_when_ebit_close_to_cfo() -> None:
    cur = _values(ebit=100.0, total_assets=1000.0, cfo=95.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=None)
    components = _compute_fired_components(sig)
    assert components["accruals_fired"] == 0


def test_mtb_signal_fires_for_growth_firm() -> None:
    cur = _values(total_assets=1000.0, total_liabilities=400.0)  # book_eq=600
    mve = _Mve(mve=4000.0)  # MTB = 4000/600 ≈ 6.67 > 5.0
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=mve)
    assert sig["mtb"] is not None
    assert sig["mtb"] >= _MTB_HIGH_THRESHOLD
    components = _compute_fired_components(sig)
    assert components["mtb_fired"] == 1


def test_mtb_signal_fires_for_value_firm() -> None:
    cur = _values(total_assets=1000.0, total_liabilities=400.0)  # book_eq=600
    mve = _Mve(mve=300.0)  # MTB = 300/600 = 0.5 < 0.8
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=mve)
    assert sig["mtb"] == pytest.approx(0.5)
    components = _compute_fired_components(sig)
    assert components["mtb_fired"] == 1


def test_mtb_signal_does_not_fire_for_typical_firm() -> None:
    cur = _values(total_assets=1000.0, total_liabilities=400.0)
    mve = _Mve(mve=1500.0)  # MTB = 1500/600 = 2.5 (between 0.8 and 5.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=mve)
    components = _compute_fired_components(sig)
    assert components["mtb_fired"] == 0


def test_negative_book_equity_encoded_as_zero_mtb_fires_low_band() -> None:
    """Carvana FY2022 case — book equity is negative; MTB encoded as 0.0."""
    cur = _values(total_assets=1000.0, total_liabilities=1500.0)  # book_eq=-500
    mve = _Mve(mve=400.0)
    sig = _compute_signals(cur_values=cur, prior_values=None, mve_entry=mve)
    assert sig["mtb"] == 0.0
    components = _compute_fired_components(sig)
    assert components["mtb_fired"] == 1


# ---------------------------------------------------------------------------
# (4) Composite arithmetic — weighted sum invariants.
# ---------------------------------------------------------------------------


def test_all_signals_off_score_is_zero() -> None:
    components = {
        "loss_fired": 0,
        "volatility_fired": 0,
        "accruals_fired": 0,
        "mtb_fired": 0,
    }
    score, flag = _compute_score_and_flag(components)
    assert score == 0.0
    assert flag == "context_marginal"


def test_all_signals_on_score_is_one() -> None:
    components = {
        "loss_fired": 1,
        "volatility_fired": 1,
        "accruals_fired": 1,
        "mtb_fired": 1,
    }
    score, flag = _compute_score_and_flag(components)
    # Sum of weights — float-rounded.
    assert math.isclose(score, sum(WEIGHTS.values()), abs_tol=1e-3)
    assert flag == "context_critical"


def test_only_loss_fires_score_equals_loss_weight() -> None:
    components = {
        "loss_fired": 1,
        "volatility_fired": 0,
        "accruals_fired": 0,
        "mtb_fired": 0,
    }
    score, flag = _compute_score_and_flag(components)
    assert math.isclose(score, WEIGHTS["loss"], abs_tol=1e-9)
    # 0.3884 falls in the helpful band [0.30, 0.60).
    assert flag == "context_helpful"


def test_loss_plus_volatility_fires_helpful() -> None:
    components = {
        "loss_fired": 1,
        "volatility_fired": 1,
        "accruals_fired": 0,
        "mtb_fired": 0,
    }
    score, flag = _compute_score_and_flag(components)
    expected = WEIGHTS["loss"] + WEIGHTS["volatility"]
    assert math.isclose(score, expected, abs_tol=1e-9)
    # 0.3884 + 0.2365 = 0.6249 → above 0.60 → context_critical.
    assert flag == "context_critical"


def test_indeterminate_when_both_vol_and_mtb_unevaluable() -> None:
    components = {
        "loss_fired": 0,
        "volatility_fired": None,
        "accruals_fired": 0,
        "mtb_fired": None,
    }
    score, flag = _compute_score_and_flag(components)
    assert score is None
    assert flag == "indeterminate"


def test_one_missing_of_vol_or_mtb_does_not_indeterminate() -> None:
    """Conservative under-count when only one of vol/mtb is missing."""
    components = {
        "loss_fired": 1,
        "volatility_fired": None,  # missing
        "accruals_fired": 1,
        "mtb_fired": 1,
    }
    score, flag = _compute_score_and_flag(components)
    # Missing signal is treated as not-fired → score = w_loss + w_accr + w_mtb.
    expected = WEIGHTS["loss"] + WEIGHTS["accruals"] + WEIGHTS["mtb"]
    assert math.isclose(score, expected, abs_tol=1e-9)
    assert flag == "context_critical"


# ---------------------------------------------------------------------------
# (5) Soft real-filing sanity check on the 5 MVP issuers.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_real_filings_produce_non_null_scores() -> None:
    """All 5 MVP issuers produce a non-null context_importance_score
    (Carvana via the negative-book-equity MTB encoding path) and a
    non-null flag. This catches gross bugs (NaN propagation, type
    errors) without forcing us to pin specific scores — the scores
    depend on the practitioner thresholds documented in the manifest,
    which an accounting expert may legitimately edit in the rule
    template.
    """
    r = _fresh_registry()
    skill = r.get("compute_context_importance_signals")
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
        score = out["context_importance_score"]
        assert score is not None, f"{name}: got null score"
        assert 0.0 <= score <= 1.0, (
            f"{name}: score={score} outside [0, 1]"
        )
        assert out["flag"] in {
            "context_critical",
            "context_helpful",
            "context_marginal",
            "indeterminate",
        }, f"{name}: unexpected flag {out['flag']!r}"


@pytest.mark.requires_live_data
def test_carvana_negative_book_equity_path_produces_marginal_or_higher() -> None:
    """Carvana FY2022 has negative book equity (TA 8.7B vs TL 9.75B);
    the skill encodes MTB as 0.0 and fires the low-extremity band.
    Confirms the documented edge-case path produces a non-indeterminate
    flag, even though EBIT is null and the loss/vol/accruals signals
    are unevaluable."""
    r = _fresh_registry()
    skill = r.get("compute_context_importance_signals")
    out = skill.run({"cik": "0001690820", "fiscal_year_end": "2022-12-31"})
    assert "error" not in out
    assert out["context_importance_score"] is not None
    assert out["flag"] in {
        "context_critical",
        "context_helpful",
        "context_marginal",
    }
    assert out["components"]["mtb_fired"] == 1
    warnings_text = " ".join(out["warnings"])
    assert "mtb_negative_book_equity" in warnings_text
