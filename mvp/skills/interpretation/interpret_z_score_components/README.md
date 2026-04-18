# interpret_z_score_components

**Layer:** `interpretation` (L2)
**Maintainer persona:** `accounting_expert`
**Status:** `alpha` at MVP

Interpret the five Altman (1968) Z-score components — X1 (working capital
/ total assets), X2 (retained earnings / total assets), X3 (EBIT / total
assets), X4 (market value of equity / total liabilities), X5 (sales / total
assets) — for a specific US public-company 10-K filing, in accountant voice,
with per-component severity bands and paper-anchored interpretation text.

## Purpose

The Altman Z-score's discriminant power comes from the combination of all
five ratios, but the component-level story is what tells an analyst which
balance-sheet fact actually moved the score. A Z of 2.51 for Enron FY2000
sits right in the grey zone — but if X3 (EBIT/TA) is barely positive while
X4 (MVE/TL) is elevated, the story is different from an issuer with weak
X4 and strong X3. The interpretation skill tells the reader which
components carry the current reading and what line items produced each.

Like `interpret_m_score_components`, this skill is **deterministic
templated substitution** — it looks up each component's value in
`mvp/rules/templates/z_score_components.yaml`, substitutes the real ratio
and the underlying canonical line-item values into the template's
interpretation text, attaches citations, and returns the result. No LLM,
no randomness, no temperature. The text is the accountant's voice as
authored in the template.

The three Altman zones (distress Z<1.81, grey 1.81-2.99, safe Z>2.99) are
paper-anchored thresholds — they live in the rule template, not in Python.
X4's numerator (market value of equity) is an exogenous input from the
`data/market_data/equity_values.yaml` fixture; the citation for X4
resolves against `market_data::<cik>::<fye>` rather than a filing locator.
`engine.citation_validator.resolve_citation` handles both schemes. The
`interpret_z_score_components` overall narrative names the zone, the
closest-to-threshold component, and any `market_value_estimated` or
`pre_ixbrl_manual_extraction` warnings propagated from the upstream
skill.

## Inputs

| Field | Type | Description |
|---|---|---|
| `cik` | `string` (10 digits) | Issuer CIK. |
| `fiscal_year_end` | `string` (ISO date) | 10-K fiscal period end. |
| `components` | `object` | The 5 Altman X1–X5 component values (typically piped from `compute_altman_z_score`). |
| `z_score` | `number` (optional) | Composite Z, for the overall-narrative zone context. |
| `z_zone` | `string` (optional) | The Altman zone enum. |
| `source_confidence` | `number` (optional) | Confidence carried through from the paper-derived skill. |

## Outputs

| Field | Type | Description |
|---|---|---|
| `interpretations` | `array` | One record per component: `{component, value, band_matched, interpretation_text, follow_up_questions, citations}`. |
| `overall_interpretation` | `string` | 2–4 sentence narrative naming the zone and the closest-to-threshold component. |
| `citations` | `array` | Rolled-up line-item + fixture citations. |
| `confidence` | `number` | Aggregate confidence. |
| `warnings` | `array` | `market_value_estimated`, `pre_ixbrl_manual_extraction`, etc. |

## Typical call

As with the M-score sibling, the composite is the usual caller. Standalone:

```bash
mvp run interpret_z_score_components \
    --cik 0000320193 --year 2023-09-30 \
    --json /path/to/components.json
```

## Typical failure modes

- **Null component** (most often X3 EBIT-null for Carvana FY2022) → the
  interpretation for that component reads "indeterminate — component not
  available," the overall narrative notes the gap, and the skill returns
  a sensible degraded output rather than crashing.
- **Fixture row missing for X4** — if `data/market_data/equity_values.yaml`
  has no row for `(cik, fiscal_year_end)`, the upstream skill raises
  `missing_market_data` before this skill is called. Exit cleanly.
- **Unknown filing** → `unknown_filing`.

## Links

- Manifest: [`manifest.yaml`](manifest.yaml)
- Rule template: [`../../../rules/templates/z_score_components.yaml`](../../../rules/templates/z_score_components.yaml)
- Paper-derived sibling: [`../../paper_derived/compute_altman_z_score/`](../../paper_derived/compute_altman_z_score/)
- Market-data fixture: [`../../../data/market_data/equity_values.yaml`](../../../data/market_data/equity_values.yaml)
- Unit tests: `tests/unit/skills/test_interpret_z_score_components.py`
