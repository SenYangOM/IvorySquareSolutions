"""
basic_diluted_eps.py
====================
IvorySquare reference implementation for CPA FAR §3.2 – Basic vs. Diluted EPS.

Formulae
--------
Basic EPS
    = (Net Income − Preferred Dividends) / Weighted-Average Common Shares Outstanding

Diluted EPS
    = (Net Income − Preferred Dividends + Convertible Preferred Dividends
       + After-tax Interest on Convertible Debt)
      / (Weighted-Average Common Shares + Dilutive Potential Common Shares)

Only dilutive securities (those that *reduce* EPS) are included in the
diluted calculation.  This module accepts the already-computed incremental
shares and earnings adjustments for each potentially dilutive instrument and
applies the treasury-stock / if-converted method totals passed in by the
caller.

All monetary amounts are in the same currency unit (e.g. USD).
All share counts are in the same unit (e.g. thousands of shares).
"""

from __future__ import annotations

import math
from typing import Sequence, Tuple


def basic_eps(
    net_income: float,
    preferred_dividends: float,
    weighted_avg_common_shares: float,
) -> float:
    """Compute Basic Earnings Per Share.

    Parameters
    ----------
    net_income:
        Net income (loss) for the period.  May be negative (loss).
    preferred_dividends:
        Dividends declared on preferred stock during the period.
        Use 0.0 if none.
    weighted_avg_common_shares:
        Weighted-average number of common shares outstanding during the period.
        Must be strictly positive.

    Returns
    -------
    float
        Basic EPS.  Returns ``math.nan`` when *weighted_avg_common_shares*
        is zero (undefined).

    Examples
    --------
    >>> basic_eps(1_000_000, 50_000, 500_000)
    1.9
    """
    if weighted_avg_common_shares == 0.0:
        return math.nan

    income_available = net_income - preferred_dividends
    return income_available / weighted_avg_common_shares


def diluted_eps(
    net_income: float,
    preferred_dividends: float,
    weighted_avg_common_shares: float,
    dilutive_instruments: Sequence[Tuple[float, float]] = (),
) -> float:
    """Compute Diluted Earnings Per Share using the if-converted / treasury-stock method.

    The function iterates over each potentially dilutive instrument in
    *dilutive_instruments*, adds it only when it is actually dilutive (i.e.
    the instrument's incremental EPS ≤ current running EPS), and returns the
    final diluted EPS.

    Parameters
    ----------
    net_income:
        Net income (loss) for the period.
    preferred_dividends:
        Dividends declared on preferred stock (excluded from numerator for
        basic EPS but may be added back for convertible preferred).
    weighted_avg_common_shares:
        Weighted-average common shares outstanding (basic denominator).
    dilutive_instruments:
        Sequence of ``(earnings_adjustment, incremental_shares)`` tuples,
        one per potentially dilutive security.

        * ``earnings_adjustment`` – amount added back to the numerator if the
          instrument is converted / exercised (e.g. after-tax interest saved on
          convertible debt, or preferred dividends on convertible preferred).
          Use 0.0 for options / warrants (treasury-stock method adds no
          earnings).
        * ``incremental_shares`` – net additional shares assumed issued
          (e.g. shares from conversion minus treasury shares repurchased for
          options).  Must be ≥ 0.

        Instruments should be ordered from most dilutive to least dilutive
        (lowest incremental EPS first) so that the sequential test is applied
        correctly per ASC 260.

    Returns
    -------
    float
        Diluted EPS.  Returns ``math.nan`` when the diluted share count is
        zero.  When there is a loss (basic EPS < 0), all potentially dilutive
        instruments are anti-dilutive and diluted EPS equals basic EPS.

    Examples
    --------
    >>> diluted_eps(1_000_000, 50_000, 500_000, [(0.0, 20_000)])
    1.8076923076923077
    """
    if weighted_avg_common_shares == 0.0:
        return math.nan

    basic = basic_eps(net_income, preferred_dividends, weighted_avg_common_shares)

    # Under a net loss, no instrument is dilutive (would reduce the loss per share).
    if basic < 0.0:
        return basic

    running_numerator = net_income - preferred_dividends
    running_denominator = weighted_avg_common_shares

    for earnings_adj, inc_shares in dilutive_instruments:
        if inc_shares < 0.0:
            raise ValueError(
                f"incremental_shares must be >= 0; got {inc_shares}"
            )
        # Incremental EPS for this instrument
        if inc_shares == 0.0:
            # No new shares → only affects numerator; always dilutive if adj < 0,
            # anti-dilutive if adj > 0 with no share increase.
            incremental_eps = math.inf if earnings_adj >= 0.0 else -math.inf
        else:
            incremental_eps = earnings_adj / inc_shares

        candidate_eps = (running_numerator + earnings_adj) / (
            running_denominator + inc_shares
        )

        # Include only if dilutive (candidate ≤ running EPS)
        if candidate_eps <= running_numerator / running_denominator:
            running_numerator += earnings_adj
            running_denominator += inc_shares

    if running_denominator == 0.0:
        return math.nan

    return running_numerator / running_denominator
