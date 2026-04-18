"""Unit tests for mvp.lib.periods."""

from __future__ import annotations

from datetime import date

import pytest

from mvp.lib.errors import InputValidationError
from mvp.lib.periods import parse_fiscal_period_end, prior_year_end, same_fiscal_year


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("2023-12-31", date(2023, 12, 31)),
        ("2023-1-5", date(2023, 1, 5)),
        ("December 31, 2023", date(2023, 12, 31)),
        ("Dec. 31, 2023", date(2023, 12, 31)),
        ("Dec 31 2023", date(2023, 12, 31)),
        ("September 30, 2023", date(2023, 9, 30)),
    ],
)
def test_parse_fiscal_period_end_accepted(raw: str, expected: date) -> None:
    assert parse_fiscal_period_end(raw) == expected


@pytest.mark.parametrize(
    "raw",
    ["", "   ", "not a date", "12/31/2023", "2023/12/31", "2023-02-30", "garbage-xx-yy"],
)
def test_parse_fiscal_period_end_rejects(raw: str) -> None:
    with pytest.raises(InputValidationError):
        parse_fiscal_period_end(raw)


def test_parse_fiscal_period_end_type_error() -> None:
    with pytest.raises(InputValidationError):
        parse_fiscal_period_end(20231231)  # type: ignore[arg-type]


def test_same_fiscal_year_true() -> None:
    assert same_fiscal_year(date(2023, 1, 1), date(2023, 12, 31)) is True


def test_same_fiscal_year_false() -> None:
    assert same_fiscal_year(date(2023, 12, 31), date(2024, 1, 1)) is False


def test_prior_year_end_standard() -> None:
    assert prior_year_end(date(2023, 12, 31)) == date(2022, 12, 31)


def test_prior_year_end_leap() -> None:
    # 2020-02-29 → 2019-02-28 (2019 is not a leap year).
    assert prior_year_end(date(2020, 2, 29)) == date(2019, 2, 28)
