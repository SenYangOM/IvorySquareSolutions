"""
valuation_allowance.py
======================
IvorySquare reference implementation – CPA FAR §4.1
Deferred Tax Valuation Allowance

A valuation allowance is recorded against a deferred tax asset (DTA) when it
is *more likely than not* (probability > 50 %) that some or all of the DTA
will not be realised.

Closed-form rules
-----------------
* ``required_allowance`` – the portion of the gross DTA that must be offset by
  a valuation allowance, given the estimated realisable fraction.

      required_allowance = gross_dta * (1 - realisable_fraction)

  where ``realisable_fraction`` ∈ [0, 1].

* ``net_dta`` – the carrying amount of the deferred tax asset after the
  valuation allowance:

      net_dta = gross_dta - required_allowance
              = gross_dta * realisable_fraction

Both functions validate their inputs and raise ``ValueError`` for out-of-range
arguments.
"""

from __future__ import annotations

import math
from typing import NamedTuple


class ValuationAllowanceResult(NamedTuple):
    """Structured result returned by :func:`compute_valuation_allowance`."""

    gross_dta: float
    realisable_fraction: float
    required_allowance: float
    net_dta: float


def required_allowance(
    gross_dta: float,
    realisable_fraction: float,
) -> float:
    """Return the valuation allowance that must be recorded against a DTA.

    Parameters
    ----------
    gross_dta:
        The gross deferred tax asset before any valuation allowance.
        Must be ≥ 0.
    realisable_fraction:
        The proportion of the DTA management expects to realise, expressed as
        a decimal in [0, 1].  A value of 1.0 means full realisation is
        expected (no allowance needed); 0.0 means none is expected (full
        allowance required).

    Returns
    -------
    float
        The valuation allowance amount (≥ 0).

    Raises
    ------
    ValueError
        If ``gross_dta`` < 0 or ``realisable_fraction`` is outside [0, 1].

    Examples
    --------
    >>> required_allowance(100_000, 0.60)
    40000.0
    >>> required_allowance(100_000, 1.0)
    0.0
    >>> required_allowance(100_000, 0.0)
    100000.0
    """
    if math.isnan(gross_dta) or gross_dta < 0.0:
        raise ValueError(f"gross_dta must be >= 0; got {gross_dta!r}")
    if math.isnan(realisable_fraction) or not (0.0 <= realisable_fraction <= 1.0):
        raise ValueError(
            f"realisable_fraction must be in [0, 1]; got {realisable_fraction!r}"
        )

    allowance: float = gross_dta * (1.0 - realisable_fraction)
    # Guard against floating-point noise producing tiny negatives
    return max(0.0, allowance)


def compute_valuation_allowance(
    gross_dta: float,
    realisable_fraction: float,
) -> ValuationAllowanceResult:
    """Compute the full valuation-allowance schedule for a deferred tax asset.

    Parameters
    ----------
    gross_dta:
        The gross deferred tax asset before any valuation allowance (≥ 0).
    realisable_fraction:
        The proportion of the DTA expected to be realised, in [0, 1].

    Returns
    -------
    ValuationAllowanceResult
        A named tuple containing:

        * ``gross_dta`` – the input gross DTA.
        * ``realisable_fraction`` – the input realisable fraction.
        * ``required_allowance`` – the valuation allowance to record.
        * ``net_dta`` – the DTA carrying amount after the allowance.

    Raises
    ------
    ValueError
        If inputs are out of range (delegated to :func:`required_allowance`).

    Examples
    --------
    >>> r = compute_valuation_allowance(200_000, 0.75)
    >>> r.required_allowance
    50000.0
    >>> r.net_dta
    150000.0
    """
    allowance = required_allowance(gross_dta, realisable_fraction)
    net = gross_dta - allowance  # == gross_dta * realisable_fraction

    return ValuationAllowanceResult(
        gross_dta=gross_dta,
        realisable_fraction=realisable_fraction,
        required_allowance=allowance,
        net_dta=net,
    )
