"""
pension_obligations.py
======================
IvorySquare reference implementation – CPA FAR §3.1
Branch: accounting | Chapter: Defined Benefit Pension Components

Closed-form computation of the two primary defined-benefit pension
obligation measures:

* **Accumulated Benefit Obligation (ABO)**
  PV of benefits earned to date using *current* compensation levels.

* **Projected Benefit Obligation (PBO)**
  PV of benefits earned to date using *projected* (future) compensation
  levels; always >= ABO.

Both measures discount the expected future benefit payment back to the
measurement date using the settlement (discount) rate.

Formula
-------
For a single employee (or homogeneous cohort):

    benefit_at_retirement = years_of_service * benefit_rate_per_year * salary

    obligation = benefit_at_retirement * annuity_factor
               * (1 + discount_rate) ** (-years_to_retirement)

where *salary* is either the current salary (ABO) or the projected
salary at retirement (PBO), and *annuity_factor* is the present value
of a level annuity-due or annuity-immediate for the expected benefit
payment period.

For simplicity this module uses a **level-annuity-immediate** factor:

    annuity_factor = [1 - (1 + r)^(-n)] / r      (r != 0)
    annuity_factor = n                             (r == 0)

All monetary inputs are in consistent currency units; rates are
expressed as decimals (e.g. 0.06 for 6 %).
"""

from __future__ import annotations

import math
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _pv_annuity_immediate(rate: float, periods: int) -> float:
    """Return the present-value factor for a level annuity-immediate.

    Parameters
    ----------
    rate:
        Periodic interest / discount rate (decimal).  May be 0.
    periods:
        Number of payment periods (non-negative integer).

    Returns
    -------
    float
        PV annuity factor  a_{n|r}.
    """
    if periods < 0:
        raise ValueError("periods must be >= 0")
    if periods == 0:
        return 0.0
    if math.isclose(rate, 0.0, abs_tol=1e-15):
        return float(periods)
    return (1.0 - (1.0 + rate) ** (-periods)) / rate


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class PensionObligations(NamedTuple):
    """Computed pension obligation measures for a single employee / cohort.

    Attributes
    ----------
    abo : float
        Accumulated Benefit Obligation (current salary basis).
    pbo : float
        Projected Benefit Obligation (projected salary basis).
    vested_benefit_obligation : float
        Vested Benefit Obligation – ABO restricted to *vested* service only.
    """

    abo: float
    pbo: float
    vested_benefit_obligation: float


# ---------------------------------------------------------------------------
# Main computation
# ---------------------------------------------------------------------------

def compute_pension_obligations(
    *,
    years_of_service: float,
    vested_years: float,
    benefit_rate_per_year: float,
    current_salary: float,
    projected_salary: float,
    discount_rate: float,
    years_to_retirement: float,
    benefit_payment_periods: int,
) -> PensionObligations:
    """Compute ABO, PBO, and VBO for a defined-benefit pension plan.

    Parameters
    ----------
    years_of_service:
        Total credited service years to the measurement date (>= 0).
    vested_years:
        Portion of *years_of_service* that is fully vested (0 <= vested_years
        <= years_of_service).
    benefit_rate_per_year:
        Annual benefit accrual expressed as a fraction of salary per year of
        service (e.g. 0.015 for a 1.5 % final-pay plan).
    current_salary:
        Employee's current annual compensation (>= 0).
    projected_salary:
        Expected annual compensation at retirement (>= current_salary for
        typical plans, but not enforced).
    discount_rate:
        Annual settlement / discount rate used to present-value the
        obligation (>= 0, decimal).
    years_to_retirement:
        Remaining years until the employee is expected to retire (>= 0).
    benefit_payment_periods:
        Expected number of annual benefit payments during retirement (>= 0).

    Returns
    -------
    PensionObligations
        Named tuple with fields ``abo``, ``pbo``, and
        ``vested_benefit_obligation``.

    Raises
    ------
    ValueError
        If any parameter violates its domain constraint.

    Examples
    --------
    >>> obs = compute_pension_obligations(
    ...     years_of_service=20,
    ...     vested_years=20,
    ...     benefit_rate_per_year=0.015,
    ...     current_salary=80_000,
    ...     projected_salary=120_000,
    ...     discount_rate=0.06,
    ...     years_to_retirement=10,
    ...     benefit_payment_periods=15,
    ... )
    >>> round(obs.abo, 2)
    185_185.19  # illustrative – actual value computed below
    """
    # --- validation --------------------------------------------------------
    if years_of_service < 0:
        raise ValueError("years_of_service must be >= 0")
    if not (0.0 <= vested_years <= years_of_service):
        raise ValueError(
            "vested_years must satisfy 0 <= vested_years <= years_of_service"
        )
    if benefit_rate_per_year < 0:
        raise ValueError("benefit_rate_per_year must be >= 0")
    if current_salary < 0:
        raise ValueError("current_salary must be >= 0")
    if projected_salary < 0:
        raise ValueError("projected_salary must be >= 0")
    if discount_rate < 0:
        raise ValueError("discount_rate must be >= 0")
    if years_to_retirement < 0:
        raise ValueError("years_to_retirement must be >= 0")
    if benefit_payment_periods < 0:
        raise ValueError("benefit_payment_periods must be >= 0")

    # --- annuity factor at retirement date ---------------------------------
    annuity_factor: float = _pv_annuity_immediate(discount_rate, benefit_payment_periods)

    # --- discount factor back to measurement date --------------------------
    if math.isclose(discount_rate, 0.0, abs_tol=1e-15):
        pv_discount: float = 1.0
    else:
        pv_discount = (1.0 + discount_rate) ** (-years_to_retirement)

    # --- annual benefit at retirement (earned portion only) ----------------
    # ABO uses current salary; PBO uses projected salary
    annual_benefit_abo: float = years_of_service * benefit_rate_per_year * current_salary
    annual_benefit_pbo: float = years_of_service * benefit_rate_per_year * projected_salary
    annual_benefit_vbo: float = vested_years * benefit_rate_per_year * current_salary

    # --- present value of obligation ---------------------------------------
    abo: float = annual_benefit_abo * annuity_factor * pv_discount
    pbo: float = annual_benefit_pbo * annuity_factor * pv_discount
    vbo: float = annual_benefit_vbo * annuity_factor * pv_discount

    return PensionObligations(abo=abo, pbo=pbo, vested_benefit_obligation=vbo)


def service_cost(
    *,
    benefit_rate_per_year: float,
    projected_salary: float,
    discount_rate: float,
    years_to_retirement: float,
    benefit_payment_periods: int,
) -> float:
    """Return the **service cost** for one additional year of credited service.

    Service cost is the PBO attributable to employee service rendered during
    the *current* period – i.e. the PBO for exactly one year of service.

    Parameters
    ----------
    benefit_rate_per_year:
        Annual benefit accrual rate (fraction of salary per year of service).
    projected_salary:
        Expected annual compensation at retirement.
    discount_rate:
        Annual settlement / discount rate (decimal, >= 0).
    years_to_retirement:
        Remaining years until retirement (>= 0).
    benefit_payment_periods:
        Expected number of annual benefit payments during retirement (>= 0).

    Returns
    -------
    float
        Service cost for one year of service (present value).
    """
    result = compute_pension_obligations(
        years_of_service=1,
        vested_years=0,          # vesting irrelevant for service cost
        benefit_rate_per_year=benefit_rate_per_year,
        current_salary=projected_salary,   # service cost always uses projected
        projected_salary=projected_salary,
        discount_rate=discount_rate,
        years_to_retirement=years_to_retirement,
        benefit_payment_periods=benefit_payment_periods,
    )
    return result.pbo
