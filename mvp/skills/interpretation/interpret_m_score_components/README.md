# interpret_m_score_components

**Layer:** `interpretation` (L2)
**Maintainer persona:** `accounting_expert`
**Status:** `alpha` at MVP

Interpret the eight Beneish (1999) ratio components — DSRI, GMI, AQI, SGI,
DEPI, SGAI, LVGI, TATA — for a specific US public-company 10-K filing, in
accountant voice, with per-component severity bands and paper-anchored
interpretation text.

## Purpose

A scalar M-score of `-0.24` for Enron FY2000 is almost useless to a reader
in isolation. What the reader needs is the eight-component breakdown plus
the reason each component sits where it does, anchored in the specific
line items that produced it. DSRI=1.37 means trade receivables grew
materially faster than sales year over year — is that because Enron
expanded credit terms? Because a trading-mark-to-market receivable
concentrated at year-end? Because a contract with extended payment terms
closed in December? The rule template's DSRI high band names those
possibilities in the interpretation text and lists the follow-up questions
an analyst would ask next.

Every band's interpretation is authored by the `accounting_expert` persona
(or the human who replaces it) in
`mvp/rules/templates/m_score_components.yaml` — declarative YAML, no Python
required. The skill's job is to look up each component's value in the
template, substitute in the real line-item values, attach the citations,
and return the result. No LLM call — determinism is the contract per
`success_criteria.md` §4.4. The text *is* the accountant's voice; passing
it through a rewriter would dilute it.

The 2–4 sentence overall narrative names the issuer, enumerates the
flagged components by severity, identifies any `indeterminate` (null)
components, and closes with the -1.78 threshold context. The threshold
lives in the rule template, not in Python — that's P1 again.

## Inputs

| Field | Type | Description |
|---|---|---|
| `cik` | `string` (10 digits) | Issuer CIK. |
| `fiscal_year_end` | `string` (ISO date) | 10-K fiscal period end. |
| `components` | `object` | The 8 Beneish component values (typically piped from `compute_beneish_m_score`'s output). |
| `m_score` | `number` (optional) | The composite M-score, for the overall-narrative threshold context. |
| `source_confidence` | `number` (optional) | Confidence carried through from the upstream paper-derived skill. |

## Outputs

| Field | Type | Description |
|---|---|---|
| `interpretations` | `array` | One interpretation record per component: `{component, value, band_matched, interpretation_text, follow_up_questions, citations}`. |
| `overall_interpretation` | `string` | 2–4 sentence narrative naming flagged components. |
| `citations` | `array` | All line-item citations rolled up. |
| `confidence` | `number` | Aggregate confidence, capped by data-quality flags. |
| `warnings` | `array` | Surfaces any `tata_approximation`, `pre_ixbrl_manual_extraction`, or `sga_combined_with_opex` flags. |

## Typical call

The composite (`analyze_for_red_flags`) is the usual caller — it pipes
`compute_beneish_m_score`'s output into this skill. Standalone:

```bash
mvp run interpret_m_score_components \
    --cik 0000320193 --year 2023-09-30 \
    --json /path/to/components.json
```

## Typical failure modes

- **Missing component value** (the upstream M-score returned null for a
  component like TATA because its input line items were null) → the
  interpretation for that component reads "indeterminate — component not
  available" and the composite narrative notes the gap. No crash.
- **Component value outside any band's condition range** — the rule
  template's bands must partition the real line with no gaps; a missing
  band is a rule-template bug (caught by
  `tests/unit/rules/test_rule_template_schema.py`).
- **Unknown filing** → `unknown_filing` — the skill still needs to
  resolve line-item citations, so the filing must be in the sample set.

## Links

- Manifest: [`manifest.yaml`](manifest.yaml)
- Rule template: [`../../../rules/templates/m_score_components.yaml`](../../../rules/templates/m_score_components.yaml)
- Rule-authoring guide: [`../../../human_layer/rule_authoring_guide.md`](../../../human_layer/rule_authoring_guide.md)
- Paper-derived sibling: [`../../paper_derived/compute_beneish_m_score/`](../../paper_derived/compute_beneish_m_score/)
- Unit tests: `tests/unit/skills/test_interpret_m_score_components.py`
