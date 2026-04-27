"""Deterministic net present value computation.

Used by the foundational concept skill ``fnd_finance_cfa_l1_corp_ch02_01_npv_definition``
to provide a closed-form reference for NPV calculations.
"""

from __future__ import annotations

from typing import Sequence


def npv(cash_flows: Sequence[float], discount_rate: float) -> float:
    """Compute the net present value of a stream of cash flows.

    Parameters
    ----------
    cash_flows:
        Sequence of cash flows starting at time 0. Outflows are
        represented as negative numbers, inflows as positive.
    discount_rate:
        Per-period discount rate as a decimal (0.05 == 5%).

    Returns
    -------
    The NPV computed as ``sum_t CF_t / (1 + r)^t``.
    """
    if discount_rate <= -1.0:
        raise ValueError(
            f"discount_rate {discount_rate!r} <= -100%; growth factor non-positive"
        )
    flows = list(map(float, cash_flows))
    if not flows:
        return 0.0
    factor = 1.0 + float(discount_rate)
    total = 0.0
    multiplier = 1.0
    for cf in flows:
        total += cf / multiplier
        multiplier *= factor
    return total


def present_value(cash_flow: float, discount_rate: float, period: int) -> float:
    """Discount one cash flow at ``period`` to time 0."""
    if period < 0:
        raise ValueError(f"period must be nonnegative, got {period!r}")
    if discount_rate <= -1.0:
        raise ValueError("discount_rate <= -100% is not a valid growth factor")
    return float(cash_flow) / (1.0 + float(discount_rate)) ** int(period)


__all__ = ["npv", "present_value"]
