"""Unit tests for :mod:`mvp.standardize.mappings`.

These are sanity tests on the mapping tables themselves — no I/O, no
network. If a canonical line-item name drifts between ``mappings.py``
and the rest of the codebase, these tests catch it.
"""

from __future__ import annotations

from mvp.standardize.mappings import (
    CONCEPT_MAPPINGS,
    IS_INSTANT_ITEM,
    LINE_ITEM_STATEMENT,
)

_EXPECTED_CANONICAL_NAMES = {
    "revenue",
    "cost_of_goods_sold",
    "gross_profit",
    "selling_general_admin_expense",
    "depreciation_and_amortization",
    "ebit",
    "trade_receivables_net",
    "inventory",
    "property_plant_equipment_net",
    "total_assets",
    "current_assets",
    "current_liabilities",
    "long_term_debt",
    "total_liabilities",
    "retained_earnings",
    "cash_flow_from_operating_activities",
}


def test_covers_all_sixteen_canonical_names() -> None:
    assert set(CONCEPT_MAPPINGS.keys()) == _EXPECTED_CANONICAL_NAMES
    assert set(LINE_ITEM_STATEMENT.keys()) == _EXPECTED_CANONICAL_NAMES
    assert set(IS_INSTANT_ITEM.keys()) == _EXPECTED_CANONICAL_NAMES


def test_every_canonical_has_at_least_one_candidate() -> None:
    for name, candidates in CONCEPT_MAPPINGS.items():
        assert len(candidates) >= 1, name


def test_candidate_lists_are_strings() -> None:
    for name, candidates in CONCEPT_MAPPINGS.items():
        for c in candidates:
            assert isinstance(c, str) and c and not c.startswith(" ")


def test_candidate_lists_have_no_duplicates() -> None:
    for name, candidates in CONCEPT_MAPPINGS.items():
        assert len(set(candidates)) == len(candidates), name


def test_statement_role_values_are_valid() -> None:
    allowed = {"income_statement", "balance_sheet", "cash_flow_statement"}
    for name, role in LINE_ITEM_STATEMENT.items():
        assert role in allowed, f"{name} has bad statement_role {role}"


def test_instant_flag_matches_statement_role() -> None:
    for name, is_instant in IS_INSTANT_ITEM.items():
        expected = LINE_ITEM_STATEMENT[name] == "balance_sheet"
        assert is_instant == expected, name


def test_revenue_preferred_candidate_is_asc606() -> None:
    # ASC 606 tag should come first so post-2017 filings use it over the
    # older umbrella tag.
    assert (
        CONCEPT_MAPPINGS["revenue"][0]
        == "RevenueFromContractWithCustomerExcludingAssessedTax"
    )


def test_long_term_debt_includes_noncurrent() -> None:
    assert "LongTermDebtNoncurrent" in CONCEPT_MAPPINGS["long_term_debt"]


def test_property_plant_equipment_includes_finance_lease_variant() -> None:
    # Without this, Carvana (finance-lease lessee) can't produce a PP&E
    # value from companyfacts.
    assert any(
        "FinanceLeaseRightOfUseAsset" in c
        for c in CONCEPT_MAPPINGS["property_plant_equipment_net"]
    )
