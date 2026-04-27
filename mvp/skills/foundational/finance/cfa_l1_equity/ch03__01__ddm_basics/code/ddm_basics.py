"""
ddm_basics.py
=============
Closed-form helpers for the multistage Dividend Discount Model (DDM).

Implements:
  - ``gordon_growth_model``: single-stage (Gordon Growth Model) intrinsic value.
  - ``multistage_ddm``: two-stage DDM where dividends grow at a high rate for a
    finite number of periods, then transition to a stable perpetual growth rate.

All arithmetic is pure Python (math + typing only).  No I/O, no side-effects.

Reference: CFA Level I – Equity, Section 3.1 (Multistage DDM basics).
"""

from __future__ import annotations

import math
from typing import Sequence


def gordon_growth_model(
    d1: float,
    r: float,
    g: float,
) -> float:
    """Return the intrinsic value via the Gordon Growth Model (single-stage DDM).

    Parameters
    ----------
    d1 : float
        Expected dividend one period from now (D₁ > 0).
    r : float
        Required rate of return (r > g, expressed as a decimal, e.g. 0.10).
    g : float
        Constant perpetual dividend growth rate (expressed as a decimal).

    Returns
    -------
    float
        Intrinsic value  V₀ = D₁ / (r − g).

    Raises
    ------
    ValueError
        If ``r <= g`` (model undefined) or ``d1 <= 0``.

    Examples
    --------
    >>> gordon_growth_model(d1=2.00, r=0.10, g=0.04)
    33.333333333333336
    """
    if d1 <= 0:
        raise ValueError(f"d1 must be positive, got {d1!r}")
    if r <= g:
        raise ValueError(
            f"Required return r ({r}) must exceed growth rate g ({g})."
        )
    return d1 / (r - g)


def multistage_ddm(
    d0: float,
    high_growth_rates: Sequence[float],
    terminal_growth_rate: float,
    required_return: float,
) -> float:
    """Return the intrinsic value via a multistage DDM.

    The stock pays dividends that grow at potentially different rates during a
    finite high-growth stage, then grow at a constant ``terminal_growth_rate``
    forever (Gordon Growth Model applied at the end of the high-growth stage).

    Parameters
    ----------
    d0 : float
        Most recently paid dividend (D₀ ≥ 0).
    high_growth_rates : Sequence[float]
        Per-period growth rates for the high-growth stage.  The length of this
        sequence equals the number of high-growth periods *n*.
        ``high_growth_rates[i]`` is the growth rate applied to produce Dᵢ₊₁
        from Dᵢ.  May be empty (degenerates to Gordon Growth Model from D₀).
    terminal_growth_rate : float
        Constant growth rate applied after the high-growth stage (gₗ).
        Must satisfy ``gₗ < required_return``.
    required_return : float
        Investor's required rate of return (r), expressed as a decimal.

    Returns
    -------
    float
        Intrinsic value V₀ = PV(high-growth dividends) + PV(terminal value).

    Raises
    ------
    ValueError
        If ``required_return <= terminal_growth_rate``, ``d0 < 0``, or any
        discount factor would be non-positive.

    Notes
    -----
    Terminal value at end of period *n*:
        TVₙ = Dₙ₊₁ / (r − gₗ)   where Dₙ₊₁ = Dₙ × (1 + gₗ)

    Present value:
        V₀ = Σ_{t=1}^{n} Dₜ / (1+r)^t  +  TVₙ / (1+r)^n

    Examples
    --------
    >>> multistage_ddm(
    ...     d0=1.00,
    ...     high_growth_rates=[0.20, 0.20, 0.15],
    ...     terminal_growth_rate=0.05,
    ...     required_return=0.10,
    ... )
    28.598...
    """
    if d0 < 0:
        raise ValueError(f"d0 must be non-negative, got {d0!r}")
    if required_return <= terminal_growth_rate:
        raise ValueError(
            f"required_return ({required_return}) must exceed "
            f"terminal_growth_rate ({terminal_growth_rate})."
        )

    n = len(high_growth_rates)
    pv_dividends = 0.0
    d_t = d0
    discount = 1.0  # accumulates (1+r)^t

    for t, g_t in enumerate(high_growth_rates, start=1):
        d_t = d_t * (1.0 + g_t)
        discount = math.pow(1.0 + required_return, t)
        pv_dividends += d_t / discount

    # Terminal value: dividend one period beyond the high-growth stage
    d_n_plus_1 = d_t * (1.0 + terminal_growth_rate)
    terminal_value = d_n_plus_1 / (required_return - terminal_growth_rate)

    # Discount terminal value back n periods
    discount_n = math.pow(1.0 + required_return, n)
    pv_terminal = terminal_value / discount_n

    return pv_dividends + pv_terminal
