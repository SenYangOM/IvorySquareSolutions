# extract_canonical_statements

**Layer:** `fundamental` (L1)
**Maintainer persona:** `quant_finance_methodologist`
**Status:** `alpha` at MVP

Return the three canonical financial statements (income statement, balance
sheet, cash flow) for a US public company's 10-K filing, with per-line-item
citations to the source XBRL fact (or to a hand-authored manual-extraction
YAML for pre-iXBRL SGML filings).

## Purpose

This is the single standardization seam between the L0 ingestion layer and
every downstream skill. The 16 canonical line items — `revenue`,
`cost_of_goods_sold`, `gross_profit`, `selling_general_admin_expense`,
`depreciation_and_amortization`, `ebit`, `trade_receivables_net`, `inventory`,
`property_plant_equipment_net`, `total_assets`, `current_assets`,
`current_liabilities`, `long_term_debt`, `total_liabilities`,
`retained_earnings`, `cash_flow_from_operating_activities` — are named
consistently across issuers and fiscal years, and the mapping from
issuer-specific XBRL concepts to these canonical names is governed by
`mvp/standardize/mappings.py`. A downstream paper-derived skill can trust
that `revenue` means the same thing for Apple FY2023 as it does for Enron
FY2000, because the methodology is pinned in the mapping table and every
value carries a resolvable citation back to its source passage.

Per Operating Principle P3, a missing concept returns `null` — never a
zero-imputed value. Downstream skills treat null as indeterminate (the
Carvana FY2022 EBIT null is the model case: Altman X3 is undefined, the
skill returns `flag: indeterminate` cleanly).

## Inputs

| Field | Type | Description |
|---|---|---|
| `cik` | `string` (10 digits) | Zero-padded SEC CIK for the issuer. |
| `fiscal_year_end` | `string` (ISO date) | The 10-K's fiscal period end, e.g. `"2000-12-31"`. |
| `statement_role` | `string` (optional) | Filter to one statement: `income_statement | balance_sheet | cash_flow_statement | all`. Default `all`. |

## Outputs

| Field | Type | Description |
|---|---|---|
| `statements` | `array` | List of canonical statement objects (up to three). Each carries `filing_id`, `statement_role`, `fiscal_period_end`, `data_quality_flag`, and a `line_items` array with per-item value, unit, period dates, and a Citation. |
| `citations` | `array` | Flat deduplicated Citation list across all line items — convenience view for MCP clients and the citation auditor. |
| `warnings` | `array` | Free-form warning strings (e.g. `"filing_not_ingested"`). |

## Typical call

```bash
mvp run extract_canonical_statements --cik 0000320193 --year 2023-09-30
```

Or via API:

```bash
curl -s -X POST localhost:8000/v1/skills/extract_canonical_statements \
    -H 'content-type: application/json' \
    -d '{"cik":"0000320193","fiscal_year_end":"2023-09-30"}' | jq .
```

## Typical failure modes

- **Filing not in the MVP sample set** → `unknown_filing` error (the 10
  filings are hardcoded in `mvp/ingestion/filings_ingest.py::_SAMPLE_FILINGS`).
  Expansion is a `workshop/coverage/` task.
- **iXBRL companyfacts cache missing** → automatic fetch via
  `mvp.lib.edgar.EdgarClient` at ≤10 req/s. If the fetch fails, a typed
  `IngestionError(reason="companyfacts_fetch_failed")` propagates.
- **Pre-iXBRL SGML filing without a manual-extraction YAML** →
  `StoreError(reason="manual_extraction_not_found")`. The 4 MVP pre-iXBRL
  filings (Enron FY1999/FY2000, WorldCom FY2000/FY2001) ship with
  hand-authored fixtures at `data/manual_extractions/<cik>/<accession>.yaml`.
- **Line item missing from the filing** (e.g. Carvana FY2022 has no EBIT
  tag) → the line item's `value_usd` is `null` with an explanatory note.
  Downstream skills return `indeterminate` on null-propagating formulas.

## Links

- Manifest: [`manifest.yaml`](manifest.yaml)
- Mapping table: [`../../../standardize/mappings.py`](../../../standardize/mappings.py)
- Unit tests: `tests/unit/standardize/test_statements.py`,
  `tests/unit/skills/test_extract_canonical_statements.py`
