"""
working_capital_metrics.py
==========================
CFA Level 1 Corporate Finance – Chapter 3.1
Cash Conversion Cycle and Working Capital Metrics

Closed-form, pure-arithmetic implementations of the key working-capital
efficiency ratios and the cash conversion cycle (CCC).

Definitions
-----------
Days Sales Outstanding (DSO)   = (Accounts Receivable / Revenue) * Days
Days Inventory Outstanding (DIO) = (Inventory / COGS) * Days
Days Payable Outstanding (DPO) = (Accounts Payable / COGS) * Days
Cash Conversion Cycle (CCC)    = DSO + DIO - DPO

All "Days" arguments default to 365 (annual).  Pass 360 for a 360-day
convention if required.
"""

from __future__ import annotations

from typing import NamedTuple


class WorkingCapitalMetrics(NamedTuple):
    """Container for all working-capital efficiency metrics."""

    days_sales_outstanding: float       # DSO  (days)
    days_inventory_outstanding: float   # DIO  (days)
    days_payable_outstanding: float     # DPO  (days)
    cash_conversion_cycle: float        # CCC  (days)


def cash_conversion_cycle(
    accounts_receivable: float,
    revenue: float,
    inventory: float,
    cogs: float,
    accounts_payable: float,
    days: int = 365,
) -> float:
    """Return the Cash Conversion Cycle (CCC) in days.

    Parameters
    ----------
    accounts_receivable:
        Average (or ending) accounts receivable balance.
    revenue:
        Net revenue (sales) for the period.
    inventory:
        Average (or ending) inventory balance.
    cogs:
        Cost of goods sold for the period.
    accounts_payable:
        Average (or ending) accounts payable balance.
    days:
        Number of days in the period (365 or 360).

    Returns
    -------
    float
        CCC = DSO + DIO − DPO  (in days).

    Raises
    ------
    ValueError
        If any denominator is zero or any input is negative.
    """
    metrics = working_capital_metrics(
        accounts_receivable=accounts_receivable,
        revenue=revenue,
        inventory=inventory,
        cogs=cogs,
        accounts_payable=accounts_payable,
        days=days,
    )
    return metrics.cash_conversion_cycle


def working_capital_metrics(
    accounts_receivable: float,
    revenue: float,
    inventory: float,
    cogs: float,
    accounts_payable: float,
    days: int = 365,
) -> WorkingCapitalMetrics:
    """Compute DSO, DIO, DPO, and CCC for a given period.

    Parameters
    ----------
    accounts_receivable:
        Average (or ending) accounts receivable balance.
    revenue:
        Net revenue (sales) for the period.
    inventory:
        Average (or ending) inventory balance.
    cogs:
        Cost of goods sold for the period.
    accounts_payable:
        Average (or ending) accounts payable balance.
    days:
        Number of days in the period (365 or 360).

    Returns
    -------
    WorkingCapitalMetrics
        Named tuple with DSO, DIO, DPO, and CCC (all in days).

    Raises
    ------
    ValueError
        If revenue or cogs is zero (division by zero), or if any
        balance-sheet input is negative, or if *days* is not positive.
    """
    if days <= 0:
        raise ValueError(f"days must be a positive integer, got {days!r}.")
    if revenue <= 0:
        raise ValueError(f"revenue must be positive, got {revenue!r}.")
    if cogs <= 0:
        raise ValueError(f"cogs must be positive, got {cogs!r}.")
    for name, value in (
        ("accounts_receivable", accounts_receivable),
        ("inventory", inventory),
        ("accounts_payable", accounts_payable),
    ):
        if value < 0:
            raise ValueError(f"{name} must be non-negative, got {value!r}.")

    dso: float = (accounts_receivable / revenue) * days
    dio: float = (inventory / cogs) * days
    dpo: float = (accounts_payable / cogs) * days
    ccc: float = dso + dio - dpo

    return WorkingCapitalMetrics(
        days_sales_outstanding=dso,
        days_inventory_outstanding=dio,
        days_payable_outstanding=dpo,
        cash_conversion_cycle=ccc,
    )
