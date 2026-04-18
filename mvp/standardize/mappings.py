"""XBRL-concept → canonical-line-item mappings.

The MVP's 16 canonical line items (see the Phase 2 build brief, §2) each
map to an ordered list of candidate us-gaap concepts. The standardization
builder tries them in order for each filing and picks the first one that
has a fact in the companyfacts JSON for the filing's fiscal period.

Design notes
------------
* The ordering within each list is intentional — most-specific / most-
  modern concepts come first. E.g. ``RevenueFromContractWithCustomerExcludingAssessedTax``
  is the post-ASC-606 standard; ``Revenues`` is the older / fallback
  aggregator; ``SalesRevenueNet`` and ``SalesRevenueGoodsNet`` are legacy
  tags still used by some pre-2017 filers.
* When a concept in the list is missing, the standardize layer surfaces
  a ``missing_concept`` line in the mapping log and sets ``value_usd=None``
  — per P2 we never substitute zero, and we never fall back to a silently-
  chosen different concept outside this list.
* The lists cover all 16 canonical line items. No placeholders, no stubs.

Future-compat: adding a new candidate to an existing list is a backwards-
compatible change. Re-ordering an existing list is NOT (may pick a
different concept for an old filing) — bump a version pin first.
"""

from __future__ import annotations

from typing import Final


CONCEPT_MAPPINGS: Final[dict[str, tuple[str, ...]]] = {
    # --- Income statement items (duration facts) ----------------------
    "revenue": (
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
        "SalesRevenueGoodsNet",
        "RevenueFromContractWithCustomerIncludingAssessedTax",
    ),
    "cost_of_goods_sold": (
        "CostOfGoodsAndServicesSold",
        "CostOfRevenue",
        "CostOfGoodsSold",
        "CostOfServices",
    ),
    "gross_profit": (
        "GrossProfit",
    ),
    "selling_general_admin_expense": (
        "SellingGeneralAndAdministrativeExpense",
        "GeneralAndAdministrativeExpense",
        "SellingAndMarketingExpense",
    ),
    "depreciation_and_amortization": (
        "DepreciationDepletionAndAmortization",
        "DepreciationAndAmortization",
        "Depreciation",
        "DepreciationAmortizationAndAccretionNet",
    ),
    "ebit": (
        # True EBIT tags are rare; operating income is the practical
        # proxy. "IncomeLossFromContinuingOperationsBeforeIncomeTaxes..."
        # over-includes non-op items but is better than nothing when
        # OperatingIncomeLoss is missing.
        "OperatingIncomeLoss",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
        "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments",
    ),
    # --- Balance sheet items (instant facts) --------------------------
    "trade_receivables_net": (
        "AccountsReceivableNetCurrent",
        "ReceivablesNetCurrent",
        "AccountsNotesAndLoansReceivableNetCurrent",
    ),
    "inventory": (
        "InventoryNet",
        "Inventory",
    ),
    "property_plant_equipment_net": (
        "PropertyPlantAndEquipmentNet",
        # Lessees that capitalise finance-lease ROU alongside owned PP&E
        # (e.g. Carvana 2021+) may only report this combined tag.
        "PropertyPlantAndEquipmentAndFinanceLeaseRightOfUseAssetAfterAccumulatedDepreciationAndAmortization",
    ),
    "total_assets": (
        "Assets",
    ),
    "current_assets": (
        "AssetsCurrent",
    ),
    "current_liabilities": (
        "LiabilitiesCurrent",
    ),
    "long_term_debt": (
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndCapitalLeaseObligations",
    ),
    "total_liabilities": (
        "Liabilities",
    ),
    "retained_earnings": (
        "RetainedEarningsAccumulatedDeficit",
    ),
    # --- Cash flow statement items (duration facts) -------------------
    "cash_flow_from_operating_activities": (
        "NetCashProvidedByUsedInOperatingActivities",
        "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations",
    ),
}


# Which canonical items belong to which statement. Kept here (alongside
# the concept lists) because it's part of the same mapping contract —
# a line item can only live on one statement, and the builder uses this
# to assemble the three :class:`CanonicalStatement` objects.
LINE_ITEM_STATEMENT: Final[dict[str, str]] = {
    "revenue": "income_statement",
    "cost_of_goods_sold": "income_statement",
    "gross_profit": "income_statement",
    "selling_general_admin_expense": "income_statement",
    "depreciation_and_amortization": "income_statement",
    "ebit": "income_statement",
    "trade_receivables_net": "balance_sheet",
    "inventory": "balance_sheet",
    "property_plant_equipment_net": "balance_sheet",
    "total_assets": "balance_sheet",
    "current_assets": "balance_sheet",
    "current_liabilities": "balance_sheet",
    "long_term_debt": "balance_sheet",
    "total_liabilities": "balance_sheet",
    "retained_earnings": "balance_sheet",
    "cash_flow_from_operating_activities": "cash_flow_statement",
}


# Which line items are instant (as-of) vs duration (for-the-year) facts.
# Balance-sheet = instant; income + cash-flow = duration.
IS_INSTANT_ITEM: Final[dict[str, bool]] = {
    name: (role == "balance_sheet") for name, role in LINE_ITEM_STATEMENT.items()
}


assert set(CONCEPT_MAPPINGS.keys()) == set(LINE_ITEM_STATEMENT.keys()), (
    "CONCEPT_MAPPINGS and LINE_ITEM_STATEMENT must cover the same 16 canonical names"
)


__all__ = [
    "CONCEPT_MAPPINGS",
    "IS_INSTANT_ITEM",
    "LINE_ITEM_STATEMENT",
]
