"""Altman paper-replication test.

Altman (1968) Equation I prints the Z-score function directly. We
assert that the shipped coefficients reproduce the paper's equation
and that for Altman's worked zones the shipped implementation
produces Z scores in the expected range.

Altman §V of the paper reports:
    - "all firms having a Z score of greater than 2.99 clearly fall
       into the 'non-bankrupt' sector"
    - "those firms having a Z below 1.81 are all bankrupt"
    - "the area between 1.81 and 2.99 will be defined as the 'zone of
       ignorance' or 'gray area'"

We build three synthetic ratio sets — one firmly safe, one squarely
in the grey zone, and one firmly in distress — and assert the
shipped arithmetic produces zone-consistent Z-scores to within ±0.05.
"""

from __future__ import annotations

import math

from mvp.skills.paper_derived.compute_altman_z_score.skill import _COEF


def _compute_z_from_ratios(ratios: dict[str, float]) -> float:
    """Apply Altman (1968) Equation I: X1-X4 as percentages, X5 as ratio."""
    return (
        _COEF["X1"] * ratios["X1"] * 100
        + _COEF["X2"] * ratios["X2"] * 100
        + _COEF["X3"] * ratios["X3"] * 100
        + _COEF["X4"] * ratios["X4"] * 100
        + _COEF["X5"] * ratios["X5"]
    )


def test_x5_coefficient_is_paper_exact_0999() -> None:
    """The shipped X5 coefficient must be 0.999, not the rounded 1.0."""
    assert _COEF["X5"] == 0.999


def test_coefficients_match_equation_1() -> None:
    assert _COEF == {
        "X1": 0.012,
        "X2": 0.014,
        "X3": 0.033,
        "X4": 0.006,
        "X5": 0.999,
    }


def test_safe_zone_synthetic_firm() -> None:
    """A modestly-liquid, profitable firm with market cap > book debt.

    Expected Z clearly > 2.99.
    """
    ratios = {
        "X1": 0.25,   # 25% working capital / assets
        "X2": 0.30,   # 30% retained earnings / assets
        "X3": 0.15,   # 15% EBIT / assets
        "X4": 2.0,    # market cap 2x liabilities
        "X5": 1.0,    # 1x asset turnover
    }
    z = _compute_z_from_ratios(ratios)
    paper_expected = (
        0.012 * 25 + 0.014 * 30 + 0.033 * 15 + 0.006 * 200 + 0.999 * 1.0
    )
    assert math.isclose(z, paper_expected, abs_tol=0.05)
    assert z > 2.99, f"safe-zone synthetic produced Z={z}, expected > 2.99"


def test_grey_zone_synthetic_firm() -> None:
    """A firm with middling ratios — Z should sit in [1.81, 2.99]."""
    ratios = {
        "X1": 0.10,
        "X2": 0.10,
        "X3": 0.05,
        "X4": 1.0,
        "X5": 0.8,
    }
    z = _compute_z_from_ratios(ratios)
    paper_expected = (
        0.012 * 10 + 0.014 * 10 + 0.033 * 5 + 0.006 * 100 + 0.999 * 0.8
    )
    assert math.isclose(z, paper_expected, abs_tol=0.05)
    assert 1.81 <= z <= 2.99, f"grey-zone synthetic produced Z={z}"


def test_distress_zone_synthetic_firm() -> None:
    """A stressed firm — negative WC, accumulated losses, thin MVE cushion."""
    ratios = {
        "X1": -0.20,
        "X2": -0.30,
        "X3": -0.05,
        "X4": 0.1,
        "X5": 0.3,
    }
    z = _compute_z_from_ratios(ratios)
    paper_expected = (
        0.012 * -20 + 0.014 * -30 + 0.033 * -5 + 0.006 * 10 + 0.999 * 0.3
    )
    assert math.isclose(z, paper_expected, abs_tol=0.05)
    assert z < 1.81, f"distress-zone synthetic produced Z={z}"
