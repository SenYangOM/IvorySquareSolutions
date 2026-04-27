"""Deterministic depreciation schedules.

Used by the foundational concept skill
``fnd_accounting_cpa_far_ch02_03_depreciation_methods``.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DepreciationSchedule:
    """Per-year depreciation expense and end-of-year book value."""

    method: str
    annual_expense: tuple[float, ...]
    end_of_year_book_value: tuple[float, ...]


def straight_line(cost: float, salvage: float, life_years: int) -> DepreciationSchedule:
    """Constant per-year depreciation."""
    if life_years <= 0:
        raise ValueError(f"life_years must be > 0, got {life_years!r}")
    annual = (float(cost) - float(salvage)) / float(life_years)
    book = float(cost)
    expenses: list[float] = []
    book_values: list[float] = []
    for _ in range(life_years):
        book -= annual
        expenses.append(annual)
        book_values.append(book)
    return DepreciationSchedule(
        method="straight_line",
        annual_expense=tuple(expenses),
        end_of_year_book_value=tuple(book_values),
    )


def units_of_production(
    cost: float, salvage: float, total_units: float, units_used_per_year: list[float]
) -> DepreciationSchedule:
    """Depreciation tied to actual unit production."""
    if total_units <= 0:
        raise ValueError("total_units must be > 0")
    base = float(cost) - float(salvage)
    book = float(cost)
    expenses: list[float] = []
    book_values: list[float] = []
    for u in units_used_per_year:
        portion = base * (float(u) / float(total_units))
        book -= portion
        expenses.append(portion)
        book_values.append(book)
    return DepreciationSchedule(
        method="units_of_production",
        annual_expense=tuple(expenses),
        end_of_year_book_value=tuple(book_values),
    )


def double_declining_balance(
    cost: float, salvage: float, life_years: int
) -> DepreciationSchedule:
    """Accelerated depreciation; caps book value at salvage."""
    if life_years <= 0:
        raise ValueError(f"life_years must be > 0, got {life_years!r}")
    rate = 2.0 / float(life_years)
    book = float(cost)
    expenses: list[float] = []
    book_values: list[float] = []
    for _ in range(life_years):
        attempted = rate * book
        # Floor book value at salvage.
        if book - attempted < float(salvage):
            attempted = max(0.0, book - float(salvage))
        book -= attempted
        expenses.append(attempted)
        book_values.append(book)
    return DepreciationSchedule(
        method="double_declining_balance",
        annual_expense=tuple(expenses),
        end_of_year_book_value=tuple(book_values),
    )


def sum_of_years_digits(
    cost: float, salvage: float, life_years: int
) -> DepreciationSchedule:
    """SYD: front-loaded expense schedule."""
    if life_years <= 0:
        raise ValueError(f"life_years must be > 0, got {life_years!r}")
    n = life_years
    denom = n * (n + 1) / 2.0
    base = float(cost) - float(salvage)
    book = float(cost)
    expenses: list[float] = []
    book_values: list[float] = []
    for t in range(1, n + 1):
        portion = base * ((n - t + 1) / denom)
        book -= portion
        expenses.append(portion)
        book_values.append(book)
    return DepreciationSchedule(
        method="sum_of_years_digits",
        annual_expense=tuple(expenses),
        end_of_year_book_value=tuple(book_values),
    )


__all__ = [
    "DepreciationSchedule",
    "double_declining_balance",
    "straight_line",
    "sum_of_years_digits",
    "units_of_production",
]
