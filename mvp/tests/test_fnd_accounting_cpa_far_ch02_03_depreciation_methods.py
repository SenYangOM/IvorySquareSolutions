"""Unit tests for the depreciation-method code reference."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


def _load():
    code_path = (
        Path(__file__).resolve().parent.parent
        / "skills"
        / "foundational"
        / "accounting"
        / "cpa_far"
        / "ch02__03__depreciation_methods"
        / "code"
        / "depreciation.py"
    )
    name = "depreciation_module_under_test"
    spec = importlib.util.spec_from_file_location(name, code_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load module at {code_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


depr = _load()


def test_straight_line_constant_expense() -> None:
    sch = depr.straight_line(cost=10000, salvage=1000, life_years=5)
    assert all(e == pytest.approx(1800, abs=1e-9) for e in sch.annual_expense)
    assert sch.end_of_year_book_value[-1] == pytest.approx(1000, abs=1e-9)


def test_double_declining_balance_caps_at_salvage() -> None:
    sch = depr.double_declining_balance(cost=10000, salvage=1000, life_years=5)
    # Year 1 expense is 0.40 * 10000 = 4000.
    assert sch.annual_expense[0] == pytest.approx(4000, abs=1e-9)
    # Final book value should equal salvage.
    assert sch.end_of_year_book_value[-1] == pytest.approx(1000, abs=1e-6)


def test_sum_of_years_digits_textbook() -> None:
    sch = depr.sum_of_years_digits(cost=10000, salvage=1000, life_years=5)
    expected = (3000, 2400, 1800, 1200, 600)
    for got, want in zip(sch.annual_expense, expected):
        assert got == pytest.approx(want, abs=1e-9)


def test_units_of_production() -> None:
    sch = depr.units_of_production(
        cost=10000, salvage=0, total_units=1000, units_used_per_year=[200, 200, 600]
    )
    assert sch.annual_expense == pytest.approx((2000, 2000, 6000), abs=1e-9)
    assert sch.end_of_year_book_value[-1] == pytest.approx(0.0, abs=1e-9)


def test_invalid_life_raises() -> None:
    with pytest.raises(ValueError):
        depr.straight_line(cost=100, salvage=10, life_years=0)
    with pytest.raises(ValueError):
        depr.double_declining_balance(cost=100, salvage=10, life_years=-1)
