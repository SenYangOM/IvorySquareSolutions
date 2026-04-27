"""
cfs_categorization.py
=====================
IvorySquare reference implementation for CPA FAR §2.2:
Operating, Investing, and Financing Classification of Cash-Flow Statement items.

Closed-form classification logic follows US GAAP ASC 230 rules:

Operating activities
    - Cash effects of transactions that enter into the determination of net income
      (collections from customers, payments to suppliers/employees, interest paid*,
      dividends received*, taxes paid).
    * Under US GAAP, interest paid and dividends received are classified as
      operating by default (ASC 230-10-45-17).

Investing activities
    - Acquisition/disposal of long-term assets and investments not considered
      cash equivalents (purchase/sale of PP&E, purchase/sale of investments,
      loans made/collected).

Financing activities
    - Transactions with owners and creditors that relate to raising capital or
      repaying debt (issuance/repayment of debt, issuance/repurchase of equity,
      dividends paid*).
    * Dividends paid are financing under US GAAP (ASC 230-10-45-15).

The module exposes two pure-arithmetic / pure-logic functions:
    classify_item  – returns the category string for a single labelled item.
    net_by_category – aggregates a list of (label, amount) pairs into
                      {operating, investing, financing} net totals.
"""

from __future__ import annotations

import math
from typing import Dict, List, Literal, Tuple

# ---------------------------------------------------------------------------
# Type aliases
# ---------------------------------------------------------------------------
Category = Literal["operating", "investing", "financing"]

# ---------------------------------------------------------------------------
# Canonical keyword mapping (lower-cased substrings → category)
# Order matters: more-specific patterns are checked first.
# ---------------------------------------------------------------------------
_RULES: List[Tuple[str, Category]] = [
    # --- Financing ---
    ("dividends paid",          "financing"),
    ("dividend paid",           "financing"),
    ("repurchase of stock",     "financing"),
    ("stock repurchase",        "financing"),
    ("buyback",                 "financing"),
    ("issuance of stock",       "financing"),
    ("stock issuance",          "financing"),
    ("issuance of debt",        "financing"),
    ("proceeds from debt",      "financing"),
    ("proceeds from borrowing", "financing"),
    ("repayment of debt",       "financing"),
    ("debt repayment",          "financing"),
    ("repayment of loan",       "financing"),
    ("loan repayment",          "financing"),
    ("proceeds from bond",      "financing"),
    ("bond repayment",          "financing"),
    ("payment of dividend",     "financing"),
    # --- Investing ---
    ("purchase of property",    "investing"),
    ("purchase of equipment",   "investing"),
    ("purchase of ppe",         "investing"),
    ("capital expenditure",     "investing"),
    ("capex",                   "investing"),
    ("sale of property",        "investing"),
    ("sale of equipment",       "investing"),
    ("sale of ppe",             "investing"),
    ("purchase of investment",  "investing"),
    ("sale of investment",      "investing"),
    ("acquisition of",          "investing"),
    ("proceeds from sale of",   "investing"),
    ("loan made",               "investing"),
    ("loan collected",          "investing"),
    ("collection of loan",      "investing"),
    ("purchase of securities",  "investing"),
    ("sale of securities",      "investing"),
    # --- Operating ---
    ("collection from customer","operating"),
    ("cash received from customer","operating"),
    ("payment to supplier",     "operating"),
    ("payment to employee",     "operating"),
    ("wages paid",              "operating"),
    ("salaries paid",           "operating"),
    ("interest paid",           "operating"),
    ("interest received",       "operating"),
    ("dividends received",      "operating"),
    ("dividend received",       "operating"),
    ("taxes paid",              "operating"),
    ("income tax paid",         "operating"),
    ("rent paid",               "operating"),
    ("insurance paid",          "operating"),
    ("net income",              "operating"),
    ("depreciation",            "operating"),
    ("amortization",            "operating"),
    ("change in accounts receivable", "operating"),
    ("change in inventory",     "operating"),
    ("change in accounts payable",    "operating"),
    ("change in accrued",       "operating"),
    ("operating",               "operating"),   # catch-all last
]


def classify_item(label: str) -> Category:
    """Return the cash-flow statement category for a single line-item label.

    Parameters
    ----------
    label:
        A human-readable description of the cash-flow item, e.g.
        ``"Purchase of equipment"`` or ``"Dividends paid"``.

    Returns
    -------
    Category
        One of ``"operating"``, ``"investing"``, or ``"financing"``.

    Raises
    ------
    ValueError
        If the label cannot be matched to any known category.

    Notes
    -----
    Matching is case-insensitive substring search applied in priority order
    (financing > investing > operating).  The function contains no I/O and
    no floating-point arithmetic; it is purely deterministic string logic.

    Examples
    --------
    >>> classify_item("Purchase of equipment")
    'investing'
    >>> classify_item("Dividends paid")
    'financing'
    >>> classify_item("Interest paid")
    'operating'
    """
    normalised = label.strip().lower()
    for keyword, category in _RULES:
        if keyword in normalised:
            return category
    raise ValueError(
        f"Cannot classify cash-flow item: {label!r}. "
        "Provide a more descriptive label or extend _RULES."
    )


def net_by_category(
    items: List[Tuple[str, float]],
) -> Dict[Category, float]:
    """Aggregate a list of labelled cash-flow items into net totals per category.

    Parameters
    ----------
    items:
        A list of ``(label, amount)`` pairs where *amount* is positive for
        cash inflows and negative for cash outflows (direct-method sign
        convention).

    Returns
    -------
    dict
        ``{"operating": float, "investing": float, "financing": float}``
        Each value is the algebraic sum of all amounts in that category.
        Categories with no items have a net of ``0.0``.

    Raises
    ------
    ValueError
        If any label cannot be classified (propagated from :func:`classify_item`).
    TypeError
        If *amount* is not a real number.

    Examples
    --------
    >>> items = [
    ...     ("Collection from customer", 50_000.0),
    ...     ("Payment to supplier",     -30_000.0),
    ...     ("Purchase of equipment",   -20_000.0),
    ...     ("Issuance of stock",        10_000.0),
    ... ]
    >>> net_by_category(items)
    {'operating': 20000.0, 'investing': -20000.0, 'financing': 10000.0}
    """
    totals: Dict[Category, float] = {"operating": 0.0, "investing": 0.0, "financing": 0.0}
    for label, amount in items:
        if not isinstance(amount, (int, float)) or math.isnan(amount):
            raise TypeError(f"Amount for {label!r} must be a finite real number, got {amount!r}.")
        if math.isinf(amount):
            raise TypeError(f"Amount for {label!r} must be finite, got {amount!r}.")
        cat = classify_item(label)
        totals[cat] += float(amount)
    return totals
