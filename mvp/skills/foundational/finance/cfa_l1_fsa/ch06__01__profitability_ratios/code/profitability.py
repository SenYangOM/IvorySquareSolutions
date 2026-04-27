"""Deterministic profitability-ratio computation.

Used by the foundational concept skill
``fnd_finance_cfa_l1_fsa_ch06_01_profitability_ratios``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ProfitabilityRatios:
    """Computed profitability ratios for one fiscal period."""

    gross_margin: Optional[float]
    operating_margin: Optional[float]
    ebitda_margin: Optional[float]
    net_margin: Optional[float]
    warnings: tuple[str, ...]


def compute_profitability_ratios(
    *,
    revenue: float | None,
    cogs: float | None,
    sga: float | None = None,
    da: float | None = None,
    operating_income: float | None = None,
    net_income: float | None = None,
) -> ProfitabilityRatios:
    """Compute gross / operating / EBITDA / net margins.

    Parameters
    ----------
    revenue, cogs, sga, da:
        Income-statement line items (Revenue, Cost of Goods Sold, SG&A,
        Depreciation & Amortization). ``None`` permitted when not
        applicable; the corresponding margin is ``None`` and a warning
        is emitted.
    operating_income, net_income:
        Optional explicit overrides. When ``None``, ``operating_income``
        is computed as ``revenue - cogs - sga - da``.

    Returns
    -------
    :class:`ProfitabilityRatios` with per-margin fractions plus a
    ``warnings`` tuple naming any inputs that were missing.
    """
    warnings: list[str] = []

    if revenue is None or revenue == 0:
        warnings.append("missing_or_zero_revenue")
        return ProfitabilityRatios(
            gross_margin=None,
            operating_margin=None,
            ebitda_margin=None,
            net_margin=None,
            warnings=tuple(warnings),
        )

    rev = float(revenue)

    gm: Optional[float]
    if cogs is None:
        gm = None
        warnings.append("missing_cogs")
    else:
        gm = (rev - float(cogs)) / rev

    op_inc = None
    if operating_income is not None:
        op_inc = float(operating_income)
    elif cogs is not None and sga is not None and da is not None:
        op_inc = rev - float(cogs) - float(sga) - float(da)
    else:
        warnings.append("operating_income_underivable_from_inputs")

    om: Optional[float] = None if op_inc is None else op_inc / rev

    ebitda_margin: Optional[float] = None
    if op_inc is not None and da is not None:
        ebitda_margin = (op_inc + float(da)) / rev
    elif op_inc is None or da is None:
        warnings.append("ebitda_margin_unavailable")

    nm: Optional[float] = None
    if net_income is not None:
        nm = float(net_income) / rev
    else:
        warnings.append("missing_net_income")

    return ProfitabilityRatios(
        gross_margin=gm,
        operating_margin=om,
        ebitda_margin=ebitda_margin,
        net_margin=nm,
        warnings=tuple(warnings),
    )


__all__ = ["ProfitabilityRatios", "compute_profitability_ratios"]
