"""
fcfe_fcff_definition.py
=======================
IvorySquare reference implementation – CFA L1 Corporate Finance, Chapter 2.1
Topic : Project free cash flow definitions
Subsection: fcfe_fcff_definition

Closed-form definitions
-----------------------
FCFF (Free Cash Flow to the Firm)
    FCFF = EBIT * (1 - tax_rate)
         + depreciation_amortization
         - capital_expenditures
         - change_in_working_capital

FCFE (Free Cash Flow to Equity)
    FCFE = net_income
         + depreciation_amortization
         - capital_expenditures
         - change_in_working_capital
         + net_borrowing

Relationship between FCFF and FCFE
    FCFE = FCFF
         - interest_expense * (1 - tax_rate)
         + net_borrowing

All monetary inputs are assumed to be in the same currency unit.
Positive change_in_working_capital means working capital *increased*
(a cash outflow), consistent with standard CFA convention.
"""

from __future__ import annotations

from typing import Union

Number = Union[int, float]


def fcff(
    ebit: Number,
    tax_rate: Number,
    depreciation_amortization: Number,
    capital_expenditures: Number,
    change_in_working_capital: Number,
) -> float:
    """Compute Free Cash Flow to the Firm (FCFF).

    Parameters
    ----------
    ebit : Number
        Earnings Before Interest and Taxes.
    tax_rate : Number
        Effective corporate tax rate expressed as a decimal in [0, 1].
    depreciation_amortization : Number
        Non-cash D&A charges added back (positive value).
    capital_expenditures : Number
        Cash spent on capital expenditures (positive value = outflow).
    change_in_working_capital : Number
        Increase (+) or decrease (−) in net working capital.
        A positive value represents a cash outflow.

    Returns
    -------
    float
        FCFF in the same currency unit as the inputs.

    Raises
    ------
    ValueError
        If tax_rate is outside [0, 1].

    Examples
    --------
    >>> round(fcff(1000, 0.30, 200, 300, 50), 6)
    550.0
    """
    if not (0.0 <= float(tax_rate) <= 1.0):
        raise ValueError(f"tax_rate must be in [0, 1]; got {tax_rate!r}")

    nopat: float = float(ebit) * (1.0 - float(tax_rate))
    return (
        nopat
        + float(depreciation_amortization)
        - float(capital_expenditures)
        - float(change_in_working_capital)
    )


def fcfe(
    net_income: Number,
    depreciation_amortization: Number,
    capital_expenditures: Number,
    change_in_working_capital: Number,
    net_borrowing: Number,
) -> float:
    """Compute Free Cash Flow to Equity (FCFE).

    Parameters
    ----------
    net_income : Number
        Net income available to common shareholders.
    depreciation_amortization : Number
        Non-cash D&A charges added back (positive value).
    capital_expenditures : Number
        Cash spent on capital expenditures (positive value = outflow).
    change_in_working_capital : Number
        Increase (+) or decrease (−) in net working capital.
        A positive value represents a cash outflow.
    net_borrowing : Number
        New debt issued minus debt repaid during the period.
        Positive = net new borrowing (cash inflow).

    Returns
    -------
    float
        FCFE in the same currency unit as the inputs.

    Examples
    --------
    >>> round(fcfe(700, 200, 300, 50, 100), 6)
    650.0
    """
    return (
        float(net_income)
        + float(depreciation_amortization)
        - float(capital_expenditures)
        - float(change_in_working_capital)
        + float(net_borrowing)
    )
