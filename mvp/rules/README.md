# `mvp/rules/` — the rule set (declarative knowledge, L3a)

This directory holds the **declarative knowledge layer** of the MVP's
interpretation engine. Three artifacts live here:

- `ontology.yaml` — the domain vocabulary (domains, sub-concepts, the 16
  canonical line items, severity levels).
- `templates/m_score_components.yaml` — interpretation rules for the 8
  Beneish (1999) M-Score components + the composite M-score threshold.
- `templates/z_score_components.yaml` — interpretation rules for the 5
  Altman (1968) Z-Score components + the three-zone thresholds.

Everything in this directory is YAML. An accounting expert can read,
review, and amend these files with no Python knowledge. That is by
design (Operating Principle P1 — see `../../CLAUDE.md` and
`../mvp_build_goal.md` §0).

## How the engine consumes these files

The interpretation engine (`mvp/engine/rule_executor.py`, built in
Phase 4) takes:

1. A canonical statement bundle produced by `mvp/standardize/` — i.e.,
   the 16 canonical line-item values for year t and year t-1.
2. A rule template — one of the two files under `templates/`.

For each component in the template, the executor:

1. Computes the numeric value of the component from the named canonical
   inputs.
2. Walks the component's `interpretation_rules` in file order, matches
   the first `condition` whose expression evaluates true against the
   computed value, and emits the matched rule's `interpretation`,
   `severity`, and `follow_up_questions`.
3. Resolves each canonical name in the rule's `citations_required` to a
   `Citation` object against the standardized statements, including
   `doc_id`, `locator`, `excerpt_hash`, and value. A missing citation
   fails the skill's output before it ships (P3 — structured errors,
   never silent drops).
4. For paper-derived skills (M-Score, Z-Score), additionally applies the
   composite-threshold block at the bottom of the template to turn the
   set of component values into an overall score and a categorical flag.

Engine-side failure modes — **not** the rule author's concern:
- Missing canonical line item (e.g., Carvana has no EBIT concept):
  engine returns `null` for the component and flags `indeterminate`.
- Division by zero in a formula: engine returns `null` with reason.
- Locator resolution failure: engine raises; the skill's error wrapper
  maps it to a typed error envelope.

## How to read a rule template

Every rule template follows the same shape:

```yaml
template_version: "0.1.0"
paper: "Authoritative citation of the source paper."
paper_pdf_sha256: "..."  # pins the exact PDF the thresholds came from

components:
  - component: <SHORT_NAME>          # e.g. DSRI, X1
    full_name: "..."
    description: "..."               # what the ratio measures and why it's included
    formula: "..."                   # algebra over canonical line items
    canonical_inputs: [...]          # canonical line-item names this ratio needs
    paper_reference:                 # where in the paper the thresholds come from
      source: "..."
      table: "..."
      page: "..."
    interpretation_rules:
      - condition: "value > 1.465"
        interpretation: "..."        # 2-3 sentences, accountant voice
        severity: low|medium|high|critical
        follow_up_questions: [...]
        citations_required: [...]    # canonical line items used in the formula
      # ... more conditions covering the full real line with no gaps
    contextual_caveats: [...]        # when this component misleads

# At the bottom of paper-derived skill templates only:
m_score_threshold:                   # or z_score_thresholds
  value: -1.78
  source: "..."
  notes: "..."
  flag_logic: [...]                  # the engine applies these as a cascade
```

## Version bumping

Bump `template_version` whenever:
- You change a numeric threshold (e.g., tightening the DSRI high-severity cutoff).
- You re-word an interpretation string materially (small copy-edits are fine without a bump).
- You add, remove, or reorder a condition within a component.
- You change the composite-threshold block.

The Phase 4 skill manifests record the rule-template version they were
built against; a template bump forces re-review of the paired skill
manifest's `provenance.rule_version` pin.

## Authoring workflow for humans

See `../../human_layer/rule_authoring_guide.md` for the full authoring
workflow, including:

- A worked example of adding a new severity band.
- The DSL supported inside a `condition` field.
- How `severity` interacts with the composite Z / M score's flag.
- How `citations_required` interlocks with the engine's citation-
  integrity check.

## Current files

| File | Authored by | Components | Threshold |
|---|---|---|---|
| `ontology.yaml` | accounting_expert (2026-04-17) | n/a | n/a |
| `templates/m_score_components.yaml` | accounting_expert (2026-04-17) | 8 (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) | M > -1.78 ⇒ manipulator_likely |
| `templates/z_score_components.yaml` | accounting_expert (2026-04-17) | 5 (X1, X2, X3, X4, X5) | Z < 1.81 distress / 1.81–2.99 grey / Z > 2.99 safe |

## Load-bearing threshold choices

The rule templates encode two paper-fidelity choices that diverge from
earlier project docs; both are explained inline in the template files:

- **M-Score threshold is -1.78**, not -2.22. The -2.22 cutoff is from
  Beneish, Lee & Nichols (2013), a later paper. The 1999 paper — which
  this project implements — reports -1.78 as the optimal cutoff at the
  20:1–30:1 error-cost ratio the paper recommends for investors
  (Beneish 1999 p. 16). See `templates/m_score_components.yaml`
  `m_score_threshold.notes`.
- **Altman X5 coefficient is 0.999**, not the rounded 1.0. The paper's
  Equation (I) (Altman 1968 p. 597) prints the value as 0.999. See
  `templates/z_score_components.yaml` X5 `coefficient_notes`.

Both are discussed further in the skill manifests'
`implementation_decisions` blocks (Phase 4).
