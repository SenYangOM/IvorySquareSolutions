"""
fcfe_fcff_basics.py
===================
CFA Level 1 Equity – Chapter 3.2: Free Cash Flow to the Firm (FCFF) and
Free Cash Flow to Equity (FCFE) – Basic Closed-Form Computations.

Key relationships
-----------------
FCFF (from net income):
    FCFF = NI + NCC + Int*(1 - tax_rate) - FCInv - WCInv

FCFF (from CFO):
    FCFF = CFO + Int*(1 - tax_rate) - FCInv

FCFE (from FCFF):
    FCFE = FCFF - Int*(1 - tax_rate) + net_borrowing

FCFE (from net income):
    FCFE = NI + NCC - FCInv - WCInv + net_borrowing

FCFE (from CFO):
    FCFE = CFO - FCInv + net_borrowing

Definitions
-----------
NI           : Net income
NCC          : Non-cash charges (depreciation, amortisation, etc.)
Int          : Interest expense (gross, pre-tax)
tax_rate     : Effective corporate tax rate (0 ≤ tax_rate ≤ 1)
FCInv        : Fixed capital investment (net capex = capex – proceeds from
               asset sales)
WCInv        : Working capital investment (increase in net working capital,
               excluding cash and short-term debt)
CFO          : Cash flow from operations (after-tax interest already removed)
net_borrowing: New debt issued minus debt repaid
"""

from __future__ import annotations
from typing import Optional


def fcff(
    *,
    ni: Optional[float] = None,
    cfo: Optional[float] = None,
    ncc: float = 0.0,
    interest: float = 0.0,
    tax_rate: float = 0.0,
    fc_inv: float = 0.0,
    wc_inv: float = 0.0,
) -> float:
    """Compute Free Cash Flow to the Firm (FCFF).

    Exactly one of *ni* (net income) or *cfo* (cash flow from operations)
    must be supplied; the other must be omitted or ``None``.

    Parameters
    ----------
    ni:
        Net income.  Supply this **or** *cfo*, not both.
    cfo:
        Cash flow from operations (interest already deducted on an
        after-tax basis per GAAP/IFRS).  Supply this **or** *ni*, not both.
    ncc:
        Non-cash charges (depreciation, amortisation, impairments, …).
        Only used when *ni* is the starting point.
    interest:
        Gross (pre-tax) interest expense.
    tax_rate:
        Effective corporate tax rate expressed as a decimal (e.g. 0.30).
    fc_inv:
        Fixed capital investment (net capital expenditure).
    wc_inv:
        Working capital investment (increase in net working capital,
        excluding cash and notes payable).

    Returns
    -------
    float
        FCFF value.

    Raises
    ------
    ValueError
        If both *ni* and *cfo* are supplied, or neither is supplied.

    Examples
    --------
    >>> round(fcff(ni=100, ncc=20, interest=10, tax_rate=0.30, fc_inv=30, wc_inv=5), 4)
    92.0
    >>> round(fcff(cfo=120, interest=10, tax_rate=0.30, fc_inv=30), 4)
    97.0
    """
    if ni is not None and cfo is not None:
        raise ValueError("Supply exactly one of 'ni' or 'cfo', not both.")
    if ni is None and cfo is None:
        raise ValueError("Supply exactly one of 'ni' or 'cfo'.")

    after_tax_interest: float = interest * (1.0 - tax_rate)

    if ni is not None:
        # FCFF = NI + NCC + Int*(1-t) - FCInv - WCInv
        return ni + ncc + after_tax_interest - fc_inv - wc_inv
    else:
        # FCFF = CFO + Int*(1-t) - FCInv
        return cfo + after_tax_interest - fc_inv  # type: ignore[operator]


def fcfe(
    *,
    ni: Optional[float] = None,
    cfo: Optional[float] = None,
    fcff_value: Optional[float] = None,
    ncc: float = 0.0,
    interest: float = 0.0,
    tax_rate: float = 0.0,
    fc_inv: float = 0.0,
    wc_inv: float = 0.0,
    net_borrowing: float = 0.0,
) -> float:
    """Compute Free Cash Flow to Equity (FCFE).

    Exactly one of *ni*, *cfo*, or *fcff_value* must be supplied.

    Parameters
    ----------
    ni:
        Net income.
    cfo:
        Cash flow from operations.
    fcff_value:
        Pre-computed FCFF (use when FCFF is already known).
    ncc:
        Non-cash charges.  Used only when *ni* is the starting point.
    interest:
        Gross (pre-tax) interest expense.  Used when *ni* or *fcff_value*
        is the starting point.
    tax_rate:
        Effective corporate tax rate as a decimal.
    fc_inv:
        Fixed capital investment.  Used when *ni* or *cfo* is the starting
        point.
    wc_inv:
        Working capital investment.  Used when *ni* is the starting point.
    net_borrowing:
        New debt issued minus debt repaid during the period.

    Returns
    -------
    float
        FCFE value.

    Raises
    ------
    ValueError
        If more than one or none of the three starting-point arguments are
        supplied.

    Examples
    --------
    >>> round(fcfe(ni=100, ncc=20, interest=10, tax_rate=0.30,
    ...            fc_inv=30, wc_inv=5, net_borrowing=8), 4)
    93.0
    >>> round(fcfe(cfo=120, fc_inv=30, net_borrowing=8), 4)
    98.0
    >>> round(fcfe(fcff_value=92, interest=10, tax_rate=0.30,
    ...            net_borrowing=8), 4)
    93.0
    """
    supplied = sum(x is not None for x in (ni, cfo, fcff_value))
    if supplied != 1:
        raise ValueError(
            "Supply exactly one of 'ni', 'cfo', or 'fcff_value'."
        )

    after_tax_interest: float = interest * (1.0 - tax_rate)

    if fcff_value is not None:
        # FCFE = FCFF - Int*(1-t) + net_borrowing
        return fcff_value - after_tax_interest + net_borrowing

    if ni is not None:
        # FCFE = NI + NCC - FCInv - WCInv + net_borrowing
        return ni + ncc - fc_inv - wc_inv + net_borrowing

    # cfo path
    # FCFE = CFO - FCInv + net_borrowing
    return cfo - fc_inv + net_borrowing  # type: ignore[operator]
