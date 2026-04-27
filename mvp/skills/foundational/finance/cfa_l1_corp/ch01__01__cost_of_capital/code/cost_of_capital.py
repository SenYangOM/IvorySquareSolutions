"""
cost_of_capital.py
==================
IvorySquare reference implementation for CFA L1 Corporate Finance, Chapter 1.1:
Components of Cost of Capital.

Provides closed-form computations for the three primary cost-of-capital components:

* **Cost of Debt** (after-tax):  k_d * (1 - tax_rate)
* **Cost of Preferred Stock**:   D_ps / P_ps
* **Cost of Equity** (CAPM):     r_f + beta * (r_m - r_f)
* **WACC** (Weighted Average Cost of Capital):
      w_d * k_d_at + w_ps * k_ps + w_e * k_e

All inputs and outputs are expressed as decimals (e.g. 0.05 for 5 %).
"""

from __future__ import annotations

import math
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Individual component functions
# ---------------------------------------------------------------------------

def cost_of_debt_after_tax(pretax_cost_of_debt: float, tax_rate: float) -> float:
    """Return the after-tax cost of debt.

    Parameters
    ----------
    pretax_cost_of_debt:
        The yield-to-maturity (or coupon rate) on the firm's debt, as a
        decimal (e.g. 0.06 for 6 %).
    tax_rate:
        The marginal corporate tax rate as a decimal (e.g. 0.30 for 30 %).

    Returns
    -------
    float
        After-tax cost of debt = pretax_cost_of_debt * (1 - tax_rate).

    Raises
    ------
    ValueError
        If pretax_cost_of_debt < 0, or tax_rate not in [0, 1].
    """
    if pretax_cost_of_debt < 0:
        raise ValueError(
            f"pretax_cost_of_debt must be non-negative; got {pretax_cost_of_debt}"
        )
    if not (0.0 <= tax_rate <= 1.0):
        raise ValueError(f"tax_rate must be in [0, 1]; got {tax_rate}")

    return pretax_cost_of_debt * (1.0 - tax_rate)


def cost_of_preferred_stock(annual_dividend: float, price: float) -> float:
    """Return the cost of preferred stock.

    Parameters
    ----------
    annual_dividend:
        Fixed annual dividend per share (currency units, e.g. 5.00).
    price:
        Current market price (or net proceeds) per preferred share.

    Returns
    -------
    float
        Cost of preferred stock = annual_dividend / price.

    Raises
    ------
    ValueError
        If annual_dividend < 0 or price <= 0.
    """
    if annual_dividend < 0:
        raise ValueError(
            f"annual_dividend must be non-negative; got {annual_dividend}"
        )
    if price <= 0:
        raise ValueError(f"price must be positive; got {price}")

    return annual_dividend / price


def cost_of_equity_capm(
    risk_free_rate: float,
    beta: float,
    expected_market_return: float,
) -> float:
    """Return the cost of equity using the Capital Asset Pricing Model (CAPM).

    Parameters
    ----------
    risk_free_rate:
        Risk-free rate of return as a decimal (e.g. 0.03 for 3 %).
    beta:
        Systematic risk coefficient of the equity (dimensionless).
    expected_market_return:
        Expected return on the broad market portfolio as a decimal.

    Returns
    -------
    float
        Cost of equity = risk_free_rate + beta * (expected_market_return - risk_free_rate).

    Raises
    ------
    ValueError
        If risk_free_rate < 0 or expected_market_return < 0.
    """
    if risk_free_rate < 0:
        raise ValueError(
            f"risk_free_rate must be non-negative; got {risk_free_rate}"
        )
    if expected_market_return < 0:
        raise ValueError(
            f"expected_market_return must be non-negative; got {expected_market_return}"
        )

    equity_risk_premium = expected_market_return - risk_free_rate
    return risk_free_rate + beta * equity_risk_premium


class WACCResult(NamedTuple):
    """Container for WACC decomposition."""

    wacc: float
    weighted_cost_of_debt: float
    weighted_cost_of_preferred: float
    weighted_cost_of_equity: float


def wacc(
    weight_debt: float,
    pretax_cost_of_debt: float,
    tax_rate: float,
    weight_preferred: float,
    annual_dividend_preferred: float,
    price_preferred: float,
    weight_equity: float,
    risk_free_rate: float,
    beta: float,
    expected_market_return: float,
) -> WACCResult:
    """Compute the Weighted Average Cost of Capital (WACC).

    WACC = w_d * k_d*(1-t) + w_ps * k_ps + w_e * k_e

    All weights must sum to 1.0 (within a small floating-point tolerance).

    Parameters
    ----------
    weight_debt:
        Market-value weight of debt in the capital structure.
    pretax_cost_of_debt:
        Pre-tax yield on debt as a decimal.
    tax_rate:
        Marginal corporate tax rate as a decimal.
    weight_preferred:
        Market-value weight of preferred stock.
    annual_dividend_preferred:
        Annual preferred dividend per share.
    price_preferred:
        Market price (net proceeds) per preferred share.
    weight_equity:
        Market-value weight of common equity.
    risk_free_rate:
        Risk-free rate as a decimal.
    beta:
        Equity beta.
    expected_market_return:
        Expected market return as a decimal.

    Returns
    -------
    WACCResult
        Named tuple with ``wacc`` and the three weighted component costs.

    Raises
    ------
    ValueError
        If any weight is negative, or weights do not sum to 1.0 (±1e-9).
    """
    for name, w in (
        ("weight_debt", weight_debt),
        ("weight_preferred", weight_preferred),
        ("weight_equity", weight_equity),
    ):
        if w < 0:
            raise ValueError(f"{name} must be non-negative; got {w}")

    weight_sum = weight_debt + weight_preferred + weight_equity
    if not math.isclose(weight_sum, 1.0, abs_tol=1e-9):
        raise ValueError(
            f"Weights must sum to 1.0; got {weight_sum}"
        )

    k_d_at = cost_of_debt_after_tax(pretax_cost_of_debt, tax_rate)
    k_ps = cost_of_preferred_stock(annual_dividend_preferred, price_preferred)
    k_e = cost_of_equity_capm(risk_free_rate, beta, expected_market_return)

    w_kd = weight_debt * k_d_at
    w_kps = weight_preferred * k_ps
    w_ke = weight_equity * k_e

    return WACCResult(
        wacc=w_kd + w_kps + w_ke,
        weighted_cost_of_debt=w_kd,
        weighted_cost_of_preferred=w_kps,
        weighted_cost_of_equity=w_ke,
    )
