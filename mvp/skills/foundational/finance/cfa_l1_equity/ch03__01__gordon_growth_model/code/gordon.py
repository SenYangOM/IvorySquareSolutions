"""Deterministic Gordon growth model price computation.

Used by the foundational concept skill
``fnd_finance_cfa_l1_equity_ch03_01_gordon_growth_model``.
"""

from __future__ import annotations


def gordon_price(d1: float, required_return: float, growth_rate: float) -> float:
    """Compute the Gordon-model fair price ``P_0 = D_1 / (r - g)``.

    Raises :class:`ValueError` when ``growth_rate >= required_return``.
    """
    if growth_rate >= required_return:
        raise ValueError(
            f"growth_rate {growth_rate!r} must be strictly less than "
            f"required_return {required_return!r} for the Gordon model "
            "to converge"
        )
    return float(d1) / (float(required_return) - float(growth_rate))


def gordon_price_from_d0(
    d0: float, required_return: float, growth_rate: float
) -> float:
    """Gordon-model price using the current-period dividend ``D_0``."""
    d1 = float(d0) * (1.0 + float(growth_rate))
    return gordon_price(d1, required_return, growth_rate)


def implied_growth_rate(
    price: float, d1: float, required_return: float
) -> float:
    """Solve for the growth rate implied by a Gordon-model price."""
    if price == 0:
        raise ValueError("price must be nonzero to imply a growth rate")
    return float(required_return) - float(d1) / float(price)


__all__ = ["gordon_price", "gordon_price_from_d0", "implied_growth_rate"]
