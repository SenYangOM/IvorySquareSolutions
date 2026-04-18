"""One-shot author script for the four pre-iXBRL manual-extraction YAMLs.

Usage
-----
Run this once to (re)generate the four YAML fixtures at
``data/manual_extractions/<cik>/<accession>.yaml``. The entries embed the
fiscal-period-end dates and the verbatim source excerpts; this script
computes the correct ``excerpt_hash`` for each and writes the files.

Running the script is idempotent: it is purely a function of the inline
tables in this file.

Why this lives here (not in ``data/``)
--------------------------------------
The YAML fixtures are the declarative artifact a domain expert would
review (per P1). This script is the *engineering* path for (re)authoring
them — an accounting expert editing values should edit the YAML directly
and not need to re-run this script. The script exists so the initial
authoring (which requires sha256 hashing) is reproducible and
verifiable, not as an ongoing dependency.

After this script is run once, the YAML files are the source of truth;
the script is kept in-tree as documentation / a re-run path.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from mvp.lib.hashing import hash_excerpt

_MVP_ROOT = Path(__file__).resolve().parent.parent
_OUT_DIR = _MVP_ROOT / "data" / "manual_extractions"

# Thousand-based → fully scaled multipliers. All four filings report in
# millions, per the statement table captions ``(In Millions)`` /
# ``(In millions)``.
MILLIONS = 1_000_000


# Each entry is (canonical_name, statement_role, value_millions|None,
# source_excerpt, notes|None). value_millions=None means "not reported in
# this filing" — we preserve the line so downstream consumers see the
# intent to standardize it, with value_usd=null.
#
# Period handling:
#   * income_statement + cash_flow_statement line items span the FY (start
#     is the prior-year fiscal-period-end + 1 day; end is the FPE).
#   * balance_sheet line items are instants at the FPE.
#
# Instead of encoding that in every row, we set a per-line-item "kind"
# (duration vs instant) implicitly via ``statement_role``: IS + CF are
# always durations, BS is always an instant. The YAML just carries the
# raw values + excerpts; facts_store and statements.py re-derive the
# periods from the filing's FPE.

# --- Enron FY2000 (10-K filed 2001-04-02, FPE 2000-12-31) -------------

ENRON_2000: dict[str, Any] = {
    "filing_id": "0001024401/0001024401-01-500010",
    "cik": "0001024401",
    "accession": "0001024401-01-500010",
    "fiscal_period_end": "2000-12-31",
    "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
    "notes": (
        "Values manually extracted from Enron Corp's FY2000 10-K (filed "
        "2001-04-02), Consolidated Income Statement / Balance Sheet / "
        "Statement of Cash Flows, all stated in millions of US dollars. "
        "These are the as-originally-filed numbers; the subsequent 2001 "
        "restatement of 1997-2000 financials is a separate filing (see "
        "restatements.py log)."
    ),
    "line_items": [
        # Income statement (all in millions, year ended 2000-12-31)
        (
            "revenue",
            "income_statement",
            100_789,
            "Total revenues 100,789 40,112 31,260",
            "Line 'Total revenues' in the Consolidated Income Statement.",
        ),
        (
            "cost_of_goods_sold",
            "income_statement",
            94_517,
            "Cost of gas, electricity, metals and other products 94,517 34,761 26,381",
            "Enron reports a single COGS-equivalent line 'Cost of gas, electricity, metals and other products'; the paper-Beneish trade-cost concept maps to this.",
        ),
        (
            "gross_profit",
            "income_statement",
            100_789 - 94_517,  # = 6,272
            "Total revenues 100,789 ... Cost of gas, electricity, metals and other products 94,517",
            "Derived as Total revenues - COGS; Enron does not report a gross-profit subtotal.",
        ),
        (
            "selling_general_admin_expense",
            "income_statement",
            3_184,
            "Operating expenses 3,184 3,045 2,473",
            "Enron does not break out a separate SG&A line; 'Operating expenses' is the closest functional equivalent (includes SG&A-type costs below COGS). Flagged for downstream M-Score SGAI component caveats.",
        ),
        (
            "depreciation_and_amortization",
            "income_statement",
            855,
            "Depreciation, depletion and amortization 855 870 827",
            "Reported as 'Depreciation, depletion and amortization' (includes depletion given Enron's upstream oil & gas operations).",
        ),
        (
            "ebit",
            "income_statement",
            2_482,
            "Income Before Interest, Minority Interests and Income Taxes 2,482 1,995 1,582",
            "Enron reports this as the sub-total 'Income Before Interest, Minority Interests and Income Taxes' — the paper-Beneish EBIT concept maps to this; 'Operating Income' of 1,953 excludes equity-method and non-operating income.",
        ),
        # Balance sheet (all in millions, as of 2000-12-31)
        (
            "trade_receivables_net",
            "balance_sheet",
            10_396,
            "Trade receivables (net of allowance for doubtful accounts of $133 and $40, respectively) 10,396 3,030",
            "Net of allowance for doubtful accounts. 'Other receivables' of 1,874 is deliberately excluded per the Beneish receivables definition.",
        ),
        (
            "inventory",
            "balance_sheet",
            953,
            "Inventories 953 598",
            "Single-line 'Inventories' on the Consolidated Balance Sheet.",
        ),
        (
            "property_plant_equipment_net",
            "balance_sheet",
            11_743,
            "Property, plant and equipment, net 11,743 10,681",
            "Net of accumulated depreciation, depletion and amortization of 3,716.",
        ),
        (
            "total_assets",
            "balance_sheet",
            65_503,
            "Total Assets $65,503 $33,381",
            None,
        ),
        (
            "current_assets",
            "balance_sheet",
            30_381,
            "Total current assets 30,381 7,255",
            None,
        ),
        (
            "current_liabilities",
            "balance_sheet",
            28_406,
            "Total current liabilities 28,406 6,759",
            None,
        ),
        (
            "long_term_debt",
            "balance_sheet",
            8_550,
            "Long-Term Debt 8,550 7,151",
            "Reported as a single-line 'Long-Term Debt' below current liabilities.",
        ),
        (
            "total_liabilities",
            "balance_sheet",
            50_715,  # Current liab 28,406 + LT debt 8,550 + Def/Other 13,759 = 50,715
            "Total current liabilities 28,406 ... Long-Term Debt 8,550 ... Total deferred credits and other liabilities 13,759",
            "Enron does not report a single 'Total liabilities' line; derived as current liabilities + long-term debt + deferred-credits-and-other-liabilities. Minority interests (2,414) and company-obligated preferred securities (904) are kept outside total liabilities (mezzanine).",
        ),
        (
            "retained_earnings",
            "balance_sheet",
            3_226,
            "Retained earnings 3,226 2,698",
            None,
        ),
        # Cash flow statement (duration, year ended 2000-12-31)
        (
            "cash_flow_from_operating_activities",
            "cash_flow_statement",
            4_779,
            "Net Cash Provided by Operating Activities 4,779 1,228 1,640",
            None,
        ),
    ],
}


# --- Enron FY1999 (10-K filed 2000-03-30, FPE 1999-12-31) -------------

ENRON_1999: dict[str, Any] = {
    "filing_id": "0001024401/0001024401-00-000002",
    "cik": "0001024401",
    "accession": "0001024401-00-000002",
    "fiscal_period_end": "1999-12-31",
    "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
    "notes": (
        "Values manually extracted from Enron Corp's FY1999 10-K (filed "
        "2000-03-30), Consolidated Income Statement / Balance Sheet / "
        "Statement of Cash Flows, all stated in millions of US dollars. "
        "This is the as-originally-filed filing; predates the 2001 "
        "restatement."
    ),
    "line_items": [
        # Income statement (year ended 1999-12-31)
        (
            "revenue",
            "income_statement",
            40_112,
            "Total revenues 40,112 31,260 20,273",
            None,
        ),
        (
            "cost_of_goods_sold",
            "income_statement",
            34_761,
            "Cost of gas, electricity and other products 34,761 26,381 17,311",
            "Label differs slightly from FY2000 (no 'metals'); same concept.",
        ),
        (
            "gross_profit",
            "income_statement",
            40_112 - 34_761,  # = 5,351
            "Total revenues 40,112 ... Cost of gas, electricity and other products 34,761",
            "Derived as Total revenues - COGS.",
        ),
        (
            "selling_general_admin_expense",
            "income_statement",
            2_996,
            "Operating expenses 2,996 2,352 1,406",
            "Reported as 'Operating expenses'; see FY2000 note on mapping to paper-Beneish SG&A.",
        ),
        (
            "depreciation_and_amortization",
            "income_statement",
            870,
            "Depreciation, depletion and amortization 870 827 600",
            None,
        ),
        (
            "ebit",
            "income_statement",
            1_995,
            "Income Before Interest, Minority Interests and Income Taxes 1,995 1,582 565",
            "Same mapping as FY2000 — 'Operating Income' of 802 excludes equity-method and non-operating income.",
        ),
        # Balance sheet (as of 1999-12-31)
        (
            "trade_receivables_net",
            "balance_sheet",
            3_030,
            "Trade receivables (net of allowance for doubtful accounts of $40 and $14, respectively) 3,030 2,060",
            None,
        ),
        (
            "inventory",
            "balance_sheet",
            598,
            "Inventories 598 514",
            None,
        ),
        (
            "property_plant_equipment_net",
            "balance_sheet",
            10_681,
            "Property, plant and equipment, net 10,681 10,657",
            None,
        ),
        (
            "total_assets",
            "balance_sheet",
            33_381,
            "Total Assets $33,381 $29,350",
            None,
        ),
        (
            "current_assets",
            "balance_sheet",
            7_255,
            "Total current assets 7,255 5,933",
            None,
        ),
        (
            "current_liabilities",
            "balance_sheet",
            6_759,
            "Total current liabilities 6,759 6,107",
            None,
        ),
        (
            "long_term_debt",
            "balance_sheet",
            7_151,
            "Long-Term Debt 7,151 7,357",
            None,
        ),
        (
            "total_liabilities",
            "balance_sheet",
            20_381,  # 6,759 + 7,151 + 6,471 = 20,381
            "Total current liabilities 6,759 ... Long-Term Debt 7,151 ... Total deferred credits and other liabilities 6,471",
            "Derived: current + LT debt + deferred credits & other liabilities. Excludes minority interests (2,430) and company-obligated preferred securities (1,000).",
        ),
        (
            "retained_earnings",
            "balance_sheet",
            2_698,
            "Retained earnings 2,698 2,226",
            None,
        ),
        # Cash flow statement
        (
            "cash_flow_from_operating_activities",
            "cash_flow_statement",
            1_228,
            "Net Cash Provided by Operating Activities 1,228 1,640 211",
            None,
        ),
    ],
}


# --- WorldCom FY2001 (10-K filed 2002-03-13, FPE 2001-12-31) ----------

WORLDCOM_2001: dict[str, Any] = {
    "filing_id": "0000723527/0001005477-02-001226",
    "cik": "0000723527",
    "accession": "0001005477-02-001226",
    "fiscal_period_end": "2001-12-31",
    "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
    "notes": (
        "Values manually extracted from WorldCom, Inc.'s FY2001 10-K405 "
        "(filed 2002-03-13, accession 0001005477-02-001226), all stated "
        "in millions of US dollars. This is the as-originally-filed "
        "filing reflecting pre-restatement numbers; the 2004 10-K/A "
        "contains the restated 1999-2001 figures (not ingested at MVP)."
    ),
    "line_items": [
        # Income statement (year ended 2001-12-31)
        (
            "revenue",
            "income_statement",
            35_179,
            "Revenues $ 35,908 $ 39,090 $ 35,179",
            "The three columns are 1999, 2000, 2001 left-to-right; 35,179 is the FY2001 figure.",
        ),
        (
            "cost_of_goods_sold",
            "income_statement",
            14_739,
            "Line costs 14,739 15,462 14,739",
            "WorldCom reports 'Line costs' as the direct-cost-of-revenue-equivalent line; no separate COGS. FY2001 figure is 14,739 (third column, 2001).",
        ),
        (
            "gross_profit",
            "income_statement",
            35_179 - 14_739,  # = 20,440
            "Revenues $ 35,179 ... Line costs 14,739",
            "Derived as Revenues - Line costs; not reported as a subtotal.",
        ),
        (
            "selling_general_admin_expense",
            "income_statement",
            11_046,
            "Selling, general and administrative 8,935 10,597 11,046",
            "FY2001 figure is 11,046 (third column).",
        ),
        (
            "depreciation_and_amortization",
            "income_statement",
            5_880,
            "Depreciation and amortization 4,354 4,878 5,880",
            "FY2001 figure is 5,880 (third column).",
        ),
        (
            "ebit",
            "income_statement",
            3_514,
            "Operating income 7,888 8,153 3,514",
            "WorldCom reports Operating income; no separately disclosed pre-interest/pre-tax subtotal above it. FY2001 figure is 3,514.",
        ),
        # Balance sheet (as of 2001-12-31)
        (
            "trade_receivables_net",
            "balance_sheet",
            5_308,
            "Accounts receivable, net of allowance for bad debts of $1,532 in 2000 and $1,086 in 2001 6,815 5,308",
            "Columns are 2000, 2001. 5,308 is 2001.",
        ),
        (
            "inventory",
            "balance_sheet",
            None,
            "(no separate inventory line; WorldCom is a services business)",
            "not reported in this filing",
        ),
        (
            "property_plant_equipment_net",
            "balance_sheet",
            38_809,
            "Property and equipment ... 44,627 48,661 ... Accumulated depreciation (7,204) (9,852) ... 37,423 38,809",
            "Net PP&E (after accumulated depreciation). 2001 column is 38,809.",
        ),
        (
            "total_assets",
            "balance_sheet",
            103_914,
            "$ 98,903 $ 103,914",
            "Totals column rows sum to the balance-sheet total; 2001 total is 103,914.",
        ),
        (
            "current_assets",
            "balance_sheet",
            9_205,
            "Total current assets 9,755 9,205",
            "Columns are 2000, 2001.",
        ),
        (
            "current_liabilities",
            "balance_sheet",
            9_210,
            "Total current liabilities 17,673 9,210",
            None,
        ),
        (
            "long_term_debt",
            "balance_sheet",
            30_038,
            "Long-term debt 17,696 30,038",
            None,
        ),
        (
            "total_liabilities",
            "balance_sheet",
            43_890,  # 9,210 + 34,680 = 43,890 (current + LT liabilities)
            "Total current liabilities 9,210 ... Total long-term liabilities 22,431 34,680",
            "Derived: total current liabilities (9,210) + total long-term liabilities (34,680) for 2001. WorldCom does not report a single 'Total liabilities' line; minority interests (101) and redeemable preferred (1,993) are mezzanine and excluded.",
        ),
        (
            "retained_earnings",
            "balance_sheet",
            4_400,
            "Retained earnings 3,160 4,400",
            None,
        ),
        # Cash flow statement (year ended 2001-12-31)
        (
            "cash_flow_from_operating_activities",
            "cash_flow_statement",
            7_994,
            "Net cash provided by operating activities 11,005 7,666 7,994",
            "Columns are 1999, 2000, 2001. FY2001 figure is 7,994.",
        ),
    ],
}


# --- WorldCom FY2000 (10-K filed 2001-03-30, FPE 2000-12-31) ----------

WORLDCOM_2000: dict[str, Any] = {
    "filing_id": "0000723527/0000912057-01-505916",
    "cik": "0000723527",
    "accession": "0000912057-01-505916",
    "fiscal_period_end": "2000-12-31",
    "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
    "notes": (
        "Values manually extracted from WorldCom, Inc.'s FY2000 10-K405 "
        "(filed 2001-03-30, accession 0000912057-01-505916), all stated "
        "in millions of US dollars. As-originally-filed; predates the "
        "2002 disclosure of the line-cost-capitalization fraud."
    ),
    "line_items": [
        # Income statement (year ended 2000-12-31)
        (
            "revenue",
            "income_statement",
            39_090,
            "Revenues $17,617 $35,908 $39,090",
            "Columns are 1998, 1999, 2000. FY2000 figure is 39,090.",
        ),
        (
            "cost_of_goods_sold",
            "income_statement",
            15_462,
            "Line costs 7,982 14,739 15,462",
            "WorldCom's 'Line costs' maps to direct-cost-of-revenue. FY2000 figure is 15,462.",
        ),
        (
            "gross_profit",
            "income_statement",
            39_090 - 15_462,  # = 23,628
            "Revenues $39,090 ... Line costs 15,462",
            "Derived as Revenues - Line costs.",
        ),
        (
            "selling_general_admin_expense",
            "income_statement",
            10_597,
            "Selling, general and administrative 4,563 8,935 10,597",
            "FY2000 figure is 10,597.",
        ),
        (
            "depreciation_and_amortization",
            "income_statement",
            4_878,
            "Depreciation and amortization 2,289 4,354 4,878",
            None,
        ),
        (
            "ebit",
            "income_statement",
            8_153,
            "Operating income (loss) (942) 7,888 8,153",
            "Reported as 'Operating income (loss)'; FY2000 is 8,153.",
        ),
        # Balance sheet (as of 2000-12-31)
        (
            "trade_receivables_net",
            "balance_sheet",
            6_815,
            "Accounts receivable, net of allowance for bad debts of $1,122 in 1999 and $1,532 in 2000 5,746 6,815",
            "Columns are 1999, 2000. 6,815 is 2000.",
        ),
        (
            "inventory",
            "balance_sheet",
            None,
            "(no separate inventory line; WorldCom is a services business)",
            "not reported in this filing",
        ),
        (
            "property_plant_equipment_net",
            "balance_sheet",
            37_423,
            "Property and equipment ... 33,728 44,627 ... Accumulated depreciation (5,110) (7,204) ... 28,618 37,423",
            "Net PP&E after accumulated depreciation; 2000 column is 37,423.",
        ),
        (
            "total_assets",
            "balance_sheet",
            98_903,
            "$91,072 $98,903",
            None,
        ),
        (
            "current_assets",
            "balance_sheet",
            9_755,
            "Total current assets 10,324 9,755",
            None,
        ),
        (
            "current_liabilities",
            "balance_sheet",
            17_673,
            "Total current liabilities 17,209 17,673",
            None,
        ),
        (
            "long_term_debt",
            "balance_sheet",
            17_696,
            "Long-term debt 13,128 17,696",
            None,
        ),
        (
            "total_liabilities",
            "balance_sheet",
            40_104,  # 17,673 + 22,431 = 40,104
            "Total current liabilities 17,673 ... Total long-term liabilities 19,228 22,431",
            "Derived: current liabilities (17,673) + long-term liabilities (22,431) for 2000. Minority interests (2,592) and mandatorily redeemable preferred (798) are mezzanine and excluded.",
        ),
        (
            "retained_earnings",
            "balance_sheet",
            3_160,
            "Retained earnings (deficit) (928) 3,160",
            "Columns are 1999 (deficit of 928) and 2000 (positive 3,160).",
        ),
        # Cash flow statement (year ended 2000-12-31)
        (
            "cash_flow_from_operating_activities",
            "cash_flow_statement",
            7_666,
            "Net cash provided by operating activities 4,182 11,005 7,666",
            "Columns are 1998, 1999, 2000. FY2000 figure is 7,666.",
        ),
    ],
}


def build_entry(
    name: str,
    role: str,
    value_millions: int | None,
    excerpt: str,
    notes: str | None,
) -> dict[str, Any]:
    """Produce one ``line_items`` entry with computed hash + locator."""
    if value_millions is None:
        value_usd: int | None = None
    else:
        value_usd = value_millions * MILLIONS
    excerpt_h = hash_excerpt(excerpt)
    entry: dict[str, Any] = {
        "name": name,
        "statement_role": role,
        "value_usd": value_usd,
        "unit": "USD",
        "source_excerpt": excerpt,
        "excerpt_hash": excerpt_h,
    }
    if notes is not None:
        entry["notes"] = notes
    return entry


def write_one(data: dict[str, Any]) -> Path:
    out_path = _OUT_DIR / data["cik"] / f"{data['accession']}.yaml"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [build_entry(*li) for li in data["line_items"]]
    payload = {
        "filing_id": data["filing_id"],
        "cik": data["cik"],
        "accession": data["accession"],
        "fiscal_period_end": data["fiscal_period_end"],
        "data_quality_flag": data["data_quality_flag"],
        "notes": data["notes"],
        "line_items": rows,
    }
    out_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, width=120, allow_unicode=True),
        encoding="utf-8",
    )
    return out_path


def main() -> int:
    fixtures = (ENRON_2000, ENRON_1999, WORLDCOM_2001, WORLDCOM_2000)
    for fx in fixtures:
        p = write_one(fx)
        print(f"wrote {p} ({len(fx['line_items'])} line items)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
