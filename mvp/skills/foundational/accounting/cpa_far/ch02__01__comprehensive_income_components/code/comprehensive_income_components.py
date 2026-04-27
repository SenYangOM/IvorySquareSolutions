"""
comprehensive_income_components.py
===================================
CPA FAR § 2.1 – Net Income vs. Other Comprehensive Income

Closed-form helpers for decomposing total comprehensive income into its
two primary components:

  Total Comprehensive Income = Net Income + Other Comprehensive Income (OCI)

OCI items (US GAAP ASC 220) include:
  1. Unrealised gains/losses on available-for-sale (AFS) debt securities
  2. Foreign currency translation adjustments (CTA)
  3. Pension / post-retirement benefit adjustments
  4. Effective portion of cash-flow hedge gains/losses

All amounts are expressed in the same currency unit (e.g. USD).
Positive values represent income/gains; negative values represent
losses/charges.
"""

from __future__ import annotations

from typing import NamedTuple


class OCIComponents(NamedTuple):
    """Itemised OCI inputs (all optional, default 0)."""

    unrealised_afs_gain_loss: float = 0.0
    foreign_currency_translation: float = 0.0
    pension_adjustment: float = 0.0
    cash_flow_hedge: float = 0.0


class ComprehensiveIncomeResult(NamedTuple):
    """Decomposed comprehensive income statement."""

    net_income: float
    other_comprehensive_income: float
    total_comprehensive_income: float


def compute_oci(components: OCIComponents) -> float:
    """Return the algebraic sum of all OCI line items.

    Parameters
    ----------
    components:
        An :class:`OCIComponents` named-tuple whose fields represent the
        four standard OCI categories under US GAAP ASC 220.

    Returns
    -------
    float
        Total Other Comprehensive Income (positive = net gain,
        negative = net loss).

    Examples
    --------
    >>> oci = OCIComponents(unrealised_afs_gain_loss=5_000,
    ...                     foreign_currency_translation=-2_000,
    ...                     pension_adjustment=-1_500,
    ...                     cash_flow_hedge=800)
    >>> compute_oci(oci)
    2300.0
    """
    return float(
        components.unrealised_afs_gain_loss
        + components.foreign_currency_translation
        + components.pension_adjustment
        + components.cash_flow_hedge
    )


def compute_comprehensive_income(
    net_income: float,
    oci_components: OCIComponents | None = None,
) -> ComprehensiveIncomeResult:
    """Compute total comprehensive income and its components.

    Implements the closed-form identity:

        Total Comprehensive Income = Net Income + OCI

    where OCI is the algebraic sum of the four standard OCI categories.

    Parameters
    ----------
    net_income:
        Bottom-line net income (loss) from the income statement.
    oci_components:
        An :class:`OCIComponents` instance.  Defaults to all-zero OCI
        (i.e. total comprehensive income equals net income).

    Returns
    -------
    ComprehensiveIncomeResult
        Named-tuple with ``net_income``, ``other_comprehensive_income``,
        and ``total_comprehensive_income``.

    Raises
    ------
    TypeError
        If *oci_components* is not ``None`` or an :class:`OCIComponents`.

    Examples
    --------
    >>> result = compute_comprehensive_income(
    ...     net_income=50_000,
    ...     oci_components=OCIComponents(unrealised_afs_gain_loss=5_000,
    ...                                  foreign_currency_translation=-2_000))
    >>> result.total_comprehensive_income
    53000.0
    """
    if oci_components is not None and not isinstance(oci_components, OCIComponents):
        raise TypeError(
            f"oci_components must be an OCIComponents instance, got {type(oci_components)}"
        )

    if oci_components is None:
        oci_components = OCIComponents()

    oci: float = compute_oci(oci_components)
    total: float = float(net_income) + oci

    return ComprehensiveIncomeResult(
        net_income=float(net_income),
        other_comprehensive_income=oci,
        total_comprehensive_income=total,
    )
