"""Fiscal-period date helpers.

The MVP vertical slice pulls year t and year t-1 data for each issuer; a
recurring papercut is that 10-Ks express fiscal-period-end in half a dozen
formats ("December 31, 2023", "2023-12-31", "Dec. 31, 2023", etc.). This
module centralises the parsing so every caller produces the same
``datetime.date``.

The accepted input shapes are intentionally narrow: ISO ``YYYY-MM-DD`` and
the long-form spellings that actually appear on EDGAR cover pages. We
reject everything else with an :class:`InputValidationError` rather than
silently guessing — per Operating Principle P2 no silent fallback.
"""

from __future__ import annotations

import re
from datetime import date, datetime

from dateutil import parser as _dateutil_parser

from .errors import InputValidationError

# A deliberately conservative match: 4-digit year, 1-2 digit month, 1-2 digit day.
_ISO_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")

# "December 31, 2023", "Dec. 31, 2023", "Dec 31 2023" — use dateutil, but
# only accept inputs that look textual (letters present) to avoid accepting
# "12/31/2023" or "2023/12/31", which EDGAR does not use and which are
# ambiguous across locales.
_LONGFORM_RE = re.compile(r"[A-Za-z]")


def parse_fiscal_period_end(s: str) -> date:
    """Parse a fiscal-period-end string into a :class:`datetime.date`.

    Accepted forms:

    * ISO 8601 date: ``"2023-12-31"``.
    * Long-form English: ``"December 31, 2023"``, ``"Dec. 31, 2023"``,
      ``"December 31 2023"``, ``"Dec 31, 2023"``.

    Raises
    ------
    InputValidationError
        If ``s`` is empty, is not a string, matches neither accepted shape,
        or matches but fails to resolve to a valid calendar date (e.g.
        ``"2023-02-30"``).
    """
    if not isinstance(s, str) or not s.strip():
        raise InputValidationError("fiscal_period_end must be a non-empty string")
    raw = s.strip()

    if _ISO_RE.match(raw):
        try:
            return date.fromisoformat(_normalize_iso(raw))
        except ValueError as exc:
            raise InputValidationError(
                f"fiscal_period_end {raw!r} is not a valid calendar date: {exc}"
            ) from exc

    if _LONGFORM_RE.search(raw):
        try:
            # dateutil's ``default`` must be a ``datetime``; we discard the
            # time portion below.
            parsed = _dateutil_parser.parse(raw, default=datetime(2000, 1, 1))
        except (ValueError, OverflowError) as exc:
            raise InputValidationError(
                f"fiscal_period_end {raw!r} is not a recognised long-form date: {exc}"
            ) from exc
        return parsed.date()

    raise InputValidationError(
        f"fiscal_period_end {raw!r} must be ISO (YYYY-MM-DD) or long-form "
        "English (e.g. 'December 31, 2023')"
    )


def _normalize_iso(raw: str) -> str:
    """Zero-pad month / day so ``date.fromisoformat`` accepts it."""
    y, m, d = raw.split("-")
    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"


def same_fiscal_year(a: date, b: date) -> bool:
    """Return ``True`` iff ``a`` and ``b`` fall in the same calendar year.

    This is the weakest definition of "same fiscal year" and is correct for
    the 5 MVP issuers (all calendar-year filers). Post-MVP issuers with
    non-calendar fiscal years will need a richer definition.
    """
    return a.year == b.year


def prior_year_end(d: date) -> date:
    """Return the calendar date exactly one year before ``d``.

    Handles Feb-29 by falling back to Feb-28 in the prior year. This matches
    SEC practice for leap-year fiscal-period-ends.
    """
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        # Only reachable for Feb 29.
        return d.replace(year=d.year - 1, day=28)
