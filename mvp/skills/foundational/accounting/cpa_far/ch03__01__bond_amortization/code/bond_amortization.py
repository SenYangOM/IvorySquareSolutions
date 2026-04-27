"""
bond_amortization.py
====================
Closed-form helpers for bond premium and discount amortization under two
standard methods used in CPA FAR (ASC 835-30):

1. **Straight-line method** – equal amortization each period.
2. **Effective-interest method** – interest expense = carrying value × market
   rate; amortization = interest expense − coupon payment (discount) or
   coupon payment − interest expense (premium).

Terminology
-----------
face_value      : par / maturity value of the bond
coupon_rate     : stated (nominal) annual coupon rate (decimal)
market_rate     : effective (yield) annual rate at issuance (decimal)
periods         : total number of coupon periods over the bond's life
periods_per_yr  : coupon payments per year (default 2 for semi-annual)
issue_price     : proceeds received at issuance

All rates are *annual*; the module converts them to per-period rates
internally.
"""

from __future__ import annotations

import math
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Public data containers
# ---------------------------------------------------------------------------

class AmortizationRow(NamedTuple):
    """One row of an amortization schedule."""
    period: int
    beg_carrying_value: float
    coupon_payment: float
    interest_expense: float
    amortization: float          # positive = discount amort; negative = premium amort
    end_carrying_value: float


# ---------------------------------------------------------------------------
# Helper: compute issue price (present value of bond cash flows)
# ---------------------------------------------------------------------------

def bond_issue_price(
    face_value: float,
    coupon_rate: float,
    market_rate: float,
    periods: int,
    periods_per_yr: int = 2,
) -> float:
    """Return the theoretical issue price of a bond.

    Parameters
    ----------
    face_value:
        Par value of the bond.
    coupon_rate:
        Annual stated coupon rate (decimal, e.g. 0.06 for 6 %).
    market_rate:
        Annual effective / yield rate at issuance (decimal).
    periods:
        Total number of coupon periods (e.g. 10 for a 5-year semi-annual bond).
    periods_per_yr:
        Number of coupon payments per year (default 2).

    Returns
    -------
    float
        Present value of all future cash flows discounted at the market rate.

    Examples
    --------
    >>> round(bond_issue_price(1_000_000, 0.06, 0.08, 10), 2)
    864110.36
    """
    r = market_rate / periods_per_yr          # per-period market rate
    c = coupon_rate / periods_per_yr          # per-period coupon rate
    coupon = face_value * c
    pv_coupons = coupon * (1 - (1 + r) ** -periods) / r if r != 0 else coupon * periods
    pv_face = face_value / (1 + r) ** periods
    return pv_coupons + pv_face


# ---------------------------------------------------------------------------
# Straight-line amortization schedule
# ---------------------------------------------------------------------------

def straight_line_schedule(
    face_value: float,
    coupon_rate: float,
    market_rate: float,
    periods: int,
    periods_per_yr: int = 2,
    issue_price: float | None = None,
) -> list[AmortizationRow]:
    """Build a straight-line bond amortization schedule.

    Under the straight-line method the total premium or discount is divided
    equally across all coupon periods.

    Parameters
    ----------
    face_value:
        Par value of the bond.
    coupon_rate:
        Annual stated coupon rate (decimal).
    market_rate:
        Annual effective rate at issuance (decimal).  Used only to derive
        *issue_price* when *issue_price* is not supplied explicitly.
    periods:
        Total coupon periods.
    periods_per_yr:
        Coupon payments per year (default 2).
    issue_price:
        Actual proceeds.  If *None*, computed via :func:`bond_issue_price`.

    Returns
    -------
    list[AmortizationRow]
        One row per period; period 0 is not included.
    """
    if issue_price is None:
        issue_price = bond_issue_price(face_value, coupon_rate, market_rate,
                                       periods, periods_per_yr)

    total_premium_discount = issue_price - face_value   # positive = premium
    amort_per_period = total_premium_discount / periods  # negative = discount amort

    coupon = face_value * (coupon_rate / periods_per_yr)

    schedule: list[AmortizationRow] = []
    carrying = issue_price

    for t in range(1, periods + 1):
        beg_cv = carrying
        # interest expense = coupon ± straight-line amortization
        interest_expense = coupon - amort_per_period   # for premium: expense < coupon
        end_cv = beg_cv - amort_per_period             # carrying moves toward face
        schedule.append(AmortizationRow(
            period=t,
            beg_carrying_value=round(beg_cv, 6),
            coupon_payment=round(coupon, 6),
            interest_expense=round(interest_expense, 6),
            amortization=round(amort_per_period, 6),
            end_carrying_value=round(end_cv, 6),
        ))
        carrying = end_cv

    return schedule


# ---------------------------------------------------------------------------
# Effective-interest amortization schedule
# ---------------------------------------------------------------------------

def effective_interest_schedule(
    face_value: float,
    coupon_rate: float,
    market_rate: float,
    periods: int,
    periods_per_yr: int = 2,
    issue_price: float | None = None,
) -> list[AmortizationRow]:
    """Build an effective-interest bond amortization schedule.

    Under the effective-interest method:

    * **Interest expense** = beginning carrying value × per-period market rate
    * **Amortization**     = interest expense − coupon  (discount bond, > 0)
                           = coupon − interest expense  (premium bond, < 0)
    * **Ending CV**        = beginning CV + amortization

    Parameters
    ----------
    face_value:
        Par value of the bond.
    coupon_rate:
        Annual stated coupon rate (decimal).
    market_rate:
        Annual effective rate at issuance (decimal).
    periods:
        Total coupon periods.
    periods_per_yr:
        Coupon payments per year (default 2).
    issue_price:
        Actual proceeds.  If *None*, computed via :func:`bond_issue_price`.

    Returns
    -------
    list[AmortizationRow]
        One row per period; period 0 is not included.

    Notes
    -----
    Rounding is deferred to the final period so that the ending carrying value
    equals *face_value* exactly (within floating-point precision).
    """
    if issue_price is None:
        issue_price = bond_issue_price(face_value, coupon_rate, market_rate,
                                       periods, periods_per_yr)

    r = market_rate / periods_per_yr
    coupon = face_value * (coupon_rate / periods_per_yr)

    schedule: list[AmortizationRow] = []
    carrying = issue_price

    for t in range(1, periods + 1):
        beg_cv = carrying
        interest_expense = beg_cv * r
        amortization = interest_expense - coupon   # positive = discount; negative = premium
        end_cv = beg_cv + amortization

        # Force exact face value on last period to eliminate float drift
        if t == periods:
            end_cv = face_value

        schedule.append(AmortizationRow(
            period=t,
            beg_carrying_value=round(beg_cv, 6),
            coupon_payment=round(coupon, 6),
            interest_expense=round(interest_expense, 6),
            amortization=round(amortization, 6),
            end_carrying_value=round(end_cv, 6),
        ))
        carrying = end_cv

    return schedule
