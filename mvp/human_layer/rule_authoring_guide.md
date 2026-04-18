# Rule-authoring guide

This guide is for an accounting expert (PhD or senior practitioner) who
is authoring or amending one of the rule templates under
`mvp/rules/templates/*.yaml`, or the domain vocabulary under
`mvp/rules/ontology.yaml`. It assumes no Python knowledge.

The engineering counterpart — how the rule executor actually consumes
these files — is documented in `mvp/rules/README.md`.

## The three files you edit

| File | What it is | When to edit |
|---|---|---|
| `mvp/rules/ontology.yaml` | Domain vocabulary — the domains, sub-concepts, canonical line items, and severity definitions that the rule templates reference. | When a new domain, sub-concept, or canonical line item needs to enter the project. Rarely. |
| `mvp/rules/templates/m_score_components.yaml` | Per-component interpretation rules for the 8 Beneish M-Score ratios + the composite threshold. | Whenever a threshold needs tightening or an interpretation needs re-wording to reflect new practitioner experience. |
| `mvp/rules/templates/z_score_components.yaml` | Per-component interpretation rules for the 5 Altman Z-Score ratios + the three-zone thresholds. | Same as above. |

## Structural shape of a rule template

Every rule template has the same shape:

```yaml
template_version: "0.1.0"
paper: "Full citation of the source paper."
paper_pdf_sha256: "..."    # pins the exact PDF version

components:
  - component: <SHORT_NAME>
    full_name: "..."
    description: "..."
    formula: "..."
    canonical_inputs: [...]
    paper_reference:
      source: "..."
      table: "..."
      page: "..."
    interpretation_rules:
      - condition: "value > X"
        interpretation: "..."
        severity: low|medium|high|critical
        follow_up_questions: [...]
        citations_required: [...]
      # ... more conditions, partitioning the real line with NO GAPS
    contextual_caveats: [...]

# Paper-derived skills also carry a composite-threshold block:
m_score_threshold:       # or z_score_thresholds
  value: <NUMBER>
  source: "..."
  notes: "..."
  flag_logic: [...]
```

## The `condition` DSL

The rule executor evaluates each `condition` string as a boolean
expression with exactly one bound variable: `value` (the computed
component value, a Python float). Supported operators:

- Comparison: `>`, `>=`, `<`, `<=`, `==`, `!=`.
- Logical: `and`, `or`, `not`.
- Grouping: parentheses.
- Numeric literals: integers and decimals; negatives allowed.

Examples:
- `value > 1.465`
- `1.1 < value <= 1.465`
- `value < 0.0`
- `value > 2.0 or value < -2.0`  (rarely needed; prefer splitting into
  separate conditions)

**Rules are evaluated top-to-bottom; first match wins.** Order your
conditions from most-severe to least-severe so the reader can read
them as a narrative.

**Conditions must partition the full real line with no gaps.** The
schema test in `tests/unit/rules/test_rule_template_schema.py`
explicitly checks this: if your four conditions leave a gap (e.g., the
top condition is `value > 1.1` and the next is `value < 0.9`, leaving
`[0.9, 1.1]` uncovered), the test fails. The eight existing M-Score
components are a working reference.

## Severity

Every rule carries exactly one severity from the set defined in
`ontology.yaml` under `value_interpretation_severities`: `low`,
`medium`, `high`, `critical`.

- `low` — Neutral or benign band. No action beyond logging.
- `medium` — Off-neutral but within non-manipulator / non-distress
  ranges. Note and read on.
- `high` — In the paper's manipulator / distressed-firm range. Ask a
  specific follow-up question.
- `critical` — Beyond the worst of the paper's distribution, or a
  degenerate input that makes the standard interpretation misleading.
  Stop and require a management representation.

Severity interacts with the composite flag in two ways (enforced by
the engine, not the rule author):

1. Every `medium`, `high`, or `critical` rule MUST have at least 2
   `follow_up_questions`. A `low` rule MAY have zero. The schema test
   enforces this.
2. A `critical` reading on a required component forces the composite
   flag to `indeterminate` regardless of the headline score, and
   emits a warning into the skill's output `warnings` array.

## `citations_required`

Every rule's `citations_required` list names the canonical line items
the rule's interpretation depends on. These names must exactly match
`mvp/standardize/mappings.py`'s canonical names. The current 16 names
are:

- Income statement: `revenue`, `cost_of_goods_sold`, `gross_profit`,
  `selling_general_admin_expense`, `depreciation_and_amortization`,
  `ebit`.
- Balance sheet: `trade_receivables_net`, `inventory`,
  `property_plant_equipment_net`, `total_assets`, `current_assets`,
  `current_liabilities`, `long_term_debt`, `total_liabilities`,
  `retained_earnings`.
- Cash flow: `cash_flow_from_operating_activities`.

Every entry is either `"<line_item> (period=t)"` or `"<line_item>
(period=t-1)"`, corresponding to the current-year or prior-year filing.

The engine resolves each entry to a `Citation` object (with a
locator, excerpt hash, and value) when it emits the output. A missing
citation fails the skill before it ships.

## Worked example — authoring a new severity band for DSRI

Suppose, after reviewing a cohort of 2024 filings, you want to split
the existing DSRI high band (`value > 1.465`) into a standard high
band and a new `critical` band for values above 2.0 (i.e., doubled
DSO in one year, which Beneish's sample tails rarely hit).

Current entry (abbreviated):

```yaml
- condition: "value > 1.465"
  interpretation: |
    Trade receivables expanded materially faster than sales... [full text]
  severity: "high"
  follow_up_questions: [...]
  citations_required: [...]
```

Amended entries:

```yaml
- condition: "value > 2.0"
  interpretation: |
    DSRI above 2.0 — trade receivables-to-sales has roughly doubled
    year over year. This tail is beyond the Beneish 1999 manipulator
    sample's interquartile range (Table 2, manipulator mean 1.465,
    median 1.281). A reading this high is very rarely produced by
    legitimate growth alone; the most common sources are (1) a large
    non-recurring receivable from a contract with extended payment
    terms, (2) channel-stuffing of a scale that materially distorts
    the fiscal-year-end snapshot, or (3) a structural break in
    receivables composition (e.g., energy-trading mark-to-market
    receivables, as in Enron FY2000). Proceed only after the firm
    has disclosed the specific driver.
  severity: "critical"
  follow_up_questions:
    - "Has the firm quantitatively decomposed the receivables increase by customer, by vintage, and by product line?"
    - "What does the aging schedule of receivables look like at period-end (>90 days, >180 days as % of total)?"
    - "Is there a disclosed change in business mix that introduces a new category of receivables not comparable to the prior-year balance?"
  citations_required:
    - "trade_receivables_net (period=t)"
    - "trade_receivables_net (period=t-1)"
    - "revenue (period=t)"
    - "revenue (period=t-1)"

- condition: "1.465 < value <= 2.0"
  interpretation: |
    Trade receivables expanded materially faster than sales... [original high-band text]
  severity: "high"
  follow_up_questions: [...]        # original list
  citations_required: [...]         # original list
```

Then:

1. Bump `template_version` from `0.1.0` → `0.2.0` at the top of the
   file.
2. Note the change in your PR description (or commit message, if
   working locally).
3. The engineering counterpart will re-validate the schema test
   (`tests/unit/rules/test_rule_template_schema.py`) and confirm the
   eval harness still passes on the 5 gold cases.

No Python edit is required on your side. The engineer only touches the
Python if the change breaks a test; in that case they tell you which
gold case's expected value needs updating.

## Contextual caveats — when to add one

Add a `contextual_caveats` entry when:

- The component's value in a band will mislead for a specific, real
  business situation (e.g., ASC 842 adoption inflating LVGI).
- The threshold band is extrapolated beyond what the paper reports —
  say so explicitly.
- A subset of the 5 MVP sample issuers is a known edge case (e.g.,
  WorldCom's line-cost capitalization producing an anomalously low
  GMI).

Each caveat is one sentence. Over time the caveats become the
institutional memory of the rule set.

## What **not** to do

- Do not add a rule whose `interpretation` is less than two sentences.
  The schema test enforces ≥30 characters; in practice aim for 2-4
  sentences of accountant voice.
- Do not leave a gap between adjacent conditions. Partition the full
  real line.
- Do not reference a canonical line item that is not in
  `mvp/standardize/mappings.py`.
- Do not use `severity: "medium"` as a fallback when you haven't
  figured out which band a value belongs in — that's the "vacuous
  placeholder" pattern the project's negative gate (`success_criteria.md`
  §8) specifically forbids. If you don't know the severity, write
  nothing yet.
- Do not bump the threshold on `m_score_threshold.value` away from
  -1.78 or on the Altman three-zone thresholds away from 1.81 / 2.99
  without a documented reason; these are paper-anchored and there are
  tests that guard them (`test_beneish_threshold_is_1978.py`,
  `test_altman_x5_is_0999.py`).
