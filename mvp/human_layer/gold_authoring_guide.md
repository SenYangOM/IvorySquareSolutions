# Gold-case authoring guide

This guide is for the `evaluation_agent` persona (or the human who
replaces it) and for the `accounting_expert` who contributes the
substantive expectations. It explains how to author one gold-standard
eval case under `mvp/eval/gold/<skill>/<issuer>_<year>.yaml`.

Gold cases are how the MVP verifies that the paper-derived skills
behave correctly on known filings. At MVP there are 10 gold cases — 5
issuers × 2 skills (Beneish M + Altman Z). Each is a single YAML file.

## Structural shape of a gold case

```yaml
# mvp/eval/gold/beneish/apple_2023.yaml — example

skill_id: compute_beneish_m_score
skill_version: "0.1.0"

case_id: "apple_2023"
issuer:
  name: "Apple Inc."
  cik: "0000320193"
  ticker: "AAPL"
filing:
  accession: "0000320193-23-000106"
  filing_type: "10-K"
  fiscal_period_end: "2023-09-30"

inputs:
  cik: "0000320193"
  fiscal_year_end: "2023-09-30"
  use_restated_if_available: false

expected:
  m_score:
    range: [-3.20, -2.60]        # within the skill's ±0.10 tolerance of a point estimate
    point_estimate: -2.90        # author's best single number; optional
    rationale: |
      Apple is a high-margin, stable-cash-flow mega-cap with low
      accruals. 2023 was a modest revenue-contraction year (SGI < 1)
      and gross margin expanded (GMI < 1). All eight Beneish
      components point toward non-manipulator behavior; widely-
      reproduced post-hoc M-score for Apple's recent filings is in
      the [-3.5, -2.5] band.
  flag: "manipulator_unlikely"
  components:
    DSRI:
      range: [0.90, 1.10]
    GMI:
      range: [0.95, 1.05]
    AQI:
      range: [0.90, 1.15]
    SGI:
      range: [0.90, 1.10]
    DEPI:
      range: [0.90, 1.10]
    SGAI:
      range: [0.95, 1.10]
    LVGI:
      range: [0.95, 1.15]
    TATA:
      range: [-0.05, 0.05]
  citation_expectations:
    must_cite:
      - "trade_receivables_net (period=t)"
      - "trade_receivables_net (period=t-1)"
      - "revenue (period=t)"
      - "revenue (period=t-1)"
      - "cost_of_goods_sold (period=t)"
      - "cost_of_goods_sold (period=t-1)"
      - "total_assets (period=t)"
      - "total_assets (period=t-1)"
      - "current_assets (period=t)"
      - "current_assets (period=t-1)"
      - "current_liabilities (period=t)"
      - "current_liabilities (period=t-1)"
      - "property_plant_equipment_net (period=t)"
      - "property_plant_equipment_net (period=t-1)"
      - "depreciation_and_amortization (period=t)"
      - "depreciation_and_amortization (period=t-1)"
      - "selling_general_admin_expense (period=t)"
      - "selling_general_admin_expense (period=t-1)"
      - "long_term_debt (period=t)"
      - "long_term_debt (period=t-1)"
    must_resolve: true           # every cited locator resolves in the doc store
  confidence:
    min: 0.75
    max: 1.00
    rationale: |
      Apple's 10-K is fully iXBRL-tagged, all 16 canonical line items
      populate, and there are no data-quality flags. Confidence should
      be high.

notes:
  source_of_expected: "Author judgment + cross-reference to widely-reproduced Apple M-scores; no official replication table for 2023 exists."
  data_quality_caveats:
    - "Apple's cover-page share count is reported 3 weeks post-FYE; Altman X4 (not this skill) uses market cap derived from it."
  last_reviewed_at: 2026-04-17
  last_reviewed_by: "evaluation_agent persona, Phase 3 build"
```

## Fields — requirements

- **`skill_id` / `skill_version`.** Must match a registered skill. If
  the skill has shipped multiple versions, name the version this gold
  case was authored against.
- **`case_id`.** Short, snake_case, stable. Used by the eval runner to
  route outputs.
- **`issuer` / `filing`.** Identify the filing precisely. `accession`
  must be a real accession in `data/filings/`.
- **`inputs`.** The skill's `inputs` block — these are the arguments
  the eval harness passes to `skill.run(...)`.
- **`expected`.** The substantive expectations. Every scalar is
  expressed as a range whose width is ≥ the skill's tolerance. Flags
  are expressed as a single expected enum value (or, for indeterminate
  cases, `"indeterminate"` is a valid expected value).
- **`expected.citation_expectations.must_cite`.** The list of canonical
  line items that MUST appear in the output's citations array for the
  case to count as passing citation integrity.
- **`notes`.** Where the expected value came from, any known data-
  quality caveats, the date and authorship of the last review.

## How to author a new gold case — workflow

1. **Identify the filing.** Confirm the accession exists under
   `data/filings/<cik>/<accession>/` and that the prior-year filing
   also exists (Beneish needs t-1).
2. **Talk to the accounting expert.** The `accounting_expert` persona
   (or human) gives you the expected score range, flag, and any
   caveats about the filing. For the 5 MVP cases this came directly
   out of the paper-replication expectations documented in
   `BUILD_REFS.md` §4.4 (Beneish) and §5.4 (Altman).
3. **Build the YAML.** Copy an existing gold case and adapt. Keep
   `range` widths conservative at first — the harness can flag a case
   as passing inside-range but trending near the edge.
4. **Verify the must-cite list.** For each canonical line item the
   component formulas use, add an entry to `must_cite`. Use the
   `(period=t)` / `(period=t-1)` convention from the rule templates.
5. **Register it.** The eval harness auto-discovers gold YAMLs under
   `mvp/eval/gold/<skill>/`. No registration step is required.

## What counts as "gold-pass" for a case

The eval harness reports a case as passing when ALL of the following
hold:

- Score is inside `expected.<score>.range`.
- Flag equals `expected.flag` exactly.
- Every component value is inside its `expected.components.<name>.range`.
- Every `must_cite` line item appears in the output's `citations` array.
- Every cited locator resolves in the doc store (`must_resolve: true`).
- Confidence is inside `expected.confidence.[min, max]`.

A single failure on any of the above reports the case as failing. The
failure message names the specific sub-check that failed.

## Indeterminate cases

For filings where the skill legitimately cannot compute (e.g., Carvana
2022 Altman Z with null EBIT), the gold case expresses this:

```yaml
expected:
  z_score:
    value: null
  flag: "indeterminate"
  components:
    X3:
      value: null
    # ...
  warnings_must_include:
    - "ebit_not_available"
```

The harness matches the `null` scores and `"indeterminate"` flag, and
confirms that the skill's `warnings` array contains the named warning.

## What **not** to do

- Do not author a gold case you cannot justify. The `notes.source_of_expected`
  field must be specific.
- Do not set a `range` narrower than the skill's stated tolerance. If
  the skill targets ±0.10 on M-score, a range of `[-2.85, -2.90]`
  (width 0.05) is too narrow.
- Do not omit `must_cite`. An eval that doesn't check citations isn't
  checking the MVP's most important property.
- Do not leave `last_reviewed_at` stale. If you touch the file, update
  it.
- Do not skip the prior-year expectations. Beneish needs both years;
  if `inputs.fiscal_year_end` is 2023-09-30, the case implicitly
  consumes the FY2022 filing as well, and the must-cite list names
  both.
