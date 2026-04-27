"""
deferred_tax_basics.py
======================
IvorySquare reference implementation – CPA FAR §4.1
Deferred Tax Assets and Liabilities (Basic Closed-Form Computations)

Key concepts
------------
* Temporary difference  = tax basis of asset/liability  −  book (GAAP) basis
* Deferred tax liability (DTL): taxable temporary difference × enacted tax rate
  Arises when book income > taxable income in current period (tax payment deferred).
* Deferred tax asset (DTA): deductible temporary difference × enacted tax rate
  Arises when taxable income > book income in current period (prepaid tax benefit).
* Net deferred tax position = DTA − DTL  (positive ⟹ net DTA; negative ⟹ net DTL)

All monetary inputs are assumed to be in the same currency unit (e.g., USD).
Tax rate must be expressed as a decimal (e.g., 0.21 for 21 %).
"""

from __future__ import annotations

import math
from typing import NamedTuple


class DeferredTaxResult(NamedTuple):
    """Structured result returned by :func:`compute_deferred_tax_position`."""

    taxable_temporary_difference: float   # positive ⟹ future taxable amount
    deductible_temporary_difference: float  # positive ⟹ future deductible amount
    deferred_tax_liability: float          # DTL  (≥ 0)
    deferred_tax_asset: float              # DTA  (≥ 0)
    net_deferred_tax_position: float       # DTA − DTL (+ ⟹ net DTA, − ⟹ net DTL)


def compute_temporary_difference(
    book_basis: float,
    tax_basis: float,
    is_asset: bool = True,
) -> float:
    """Return the temporary difference for a single balance-sheet item.

    Parameters
    ----------
    book_basis:
        GAAP carrying amount of the asset or liability.
    tax_basis:
        Tax basis of the asset or liability.
    is_asset:
        ``True`` (default) if the item is an *asset*; ``False`` if a *liability*.

    Returns
    -------
    float
        Signed temporary difference.

        * For an **asset**:  ``book_basis − tax_basis``
          - Positive ⟹ taxable temporary difference (future taxable amount → DTL)
          - Negative ⟹ deductible temporary difference (future deduction → DTA)

        * For a **liability**: ``tax_basis − book_basis``
          - Positive ⟹ taxable temporary difference (→ DTL)
          - Negative ⟹ deductible temporary difference (→ DTA)

    Examples
    --------
    >>> compute_temporary_difference(book_basis=100_000, tax_basis=60_000, is_asset=True)
    40000.0
    >>> compute_temporary_difference(book_basis=50_000, tax_basis=80_000, is_asset=False)
    30000.0
    """
    book_basis = float(book_basis)
    tax_basis = float(tax_basis)

    if is_asset:
        return book_basis - tax_basis
    else:
        return tax_basis - book_basis


def compute_deferred_tax_position(
    taxable_temporary_differences: float,
    deductible_temporary_differences: float,
    enacted_tax_rate: float,
) -> DeferredTaxResult:
    """Compute the deferred tax asset, liability, and net position.

    Parameters
    ----------
    taxable_temporary_differences:
        Aggregate *taxable* temporary differences (amounts that will increase
        future taxable income).  Must be ≥ 0.
    deductible_temporary_differences:
        Aggregate *deductible* temporary differences (amounts that will decrease
        future taxable income).  Must be ≥ 0.
    enacted_tax_rate:
        The currently enacted statutory tax rate as a decimal (0 < rate ≤ 1).

    Returns
    -------
    DeferredTaxResult
        Named tuple with DTL, DTA, and net deferred tax position.

    Raises
    ------
    ValueError
        If ``enacted_tax_rate`` is not in the open interval (0, 1], or if
        either temporary-difference argument is negative.

    Examples
    --------
    >>> r = compute_deferred_tax_position(40_000, 10_000, 0.21)
    >>> r.deferred_tax_liability
    8400.0
    >>> r.deferred_tax_asset
    2100.0
    >>> r.net_deferred_tax_position   # negative ⟹ net DTL
    -6300.0
    """
    taxable_temporary_differences = float(taxable_temporary_differences)
    deductible_temporary_differences = float(deductible_temporary_differences)
    enacted_tax_rate = float(enacted_tax_rate)

    if not (0 < enacted_tax_rate <= 1.0):
        raise ValueError(
            f"enacted_tax_rate must be in (0, 1]; got {enacted_tax_rate!r}"
        )
    if taxable_temporary_differences < 0:
        raise ValueError(
            "taxable_temporary_differences must be ≥ 0; "
            f"got {taxable_temporary_differences!r}"
        )
    if deductible_temporary_differences < 0:
        raise ValueError(
            "deductible_temporary_differences must be ≥ 0; "
            f"got {deductible_temporary_differences!r}"
        )

    dtl = taxable_temporary_differences * enacted_tax_rate
    dta = deductible_temporary_differences * enacted_tax_rate
    net = dta - dtl

    return DeferredTaxResult(
        taxable_temporary_difference=taxable_temporary_differences,
        deductible_temporary_difference=deductible_temporary_differences,
        deferred_tax_liability=dtl,
        deferred_tax_asset=dta,
        net_deferred_tax_position=net,
    )
