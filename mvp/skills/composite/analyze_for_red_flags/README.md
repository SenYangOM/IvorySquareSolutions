# analyze_for_red_flags

**Layer:** `composite` (L4)
**Maintainer persona:** `accounting_expert`
**Status:** `alpha` at MVP

Combined earnings-manipulation + bankruptcy-risk screen for a US public
company's 10-K filing. Orchestrates four sub-skills —
`compute_beneish_m_score`, `compute_altman_z_score`,
`interpret_m_score_components`, `interpret_z_score_components` — into a
single agent-facing call.

## Purpose — composition over completeness

This is the MVP's model composite skill. It exists not because
earnings-manipulation and distress-risk are inseparable — they're two
distinct questions that happen to share the same underlying canonical
statements — but because the composite pattern is worth demonstrating
**once** in the MVP, and this is the most natural first use case.

The design rule that matters is `mvp_build_goal.md` §0 P3:
> Composability over completeness. Prefer many small skills the agent
> composes over one omnibus skill that does everything.

This skill follows that rule. The four sub-skills are all independently
callable. A caller who only wants the M-score calls
`compute_beneish_m_score`; a caller who only wants the Z-zone calls
`compute_altman_z_score`; a caller who wants both plus interpretations
calls this composite. The composite does **no** new analytical work —
zero coefficient math, zero band lookup, zero citation generation. It
dispatches through `mvp.skills.registry.default_registry()` (the P3
"single seam"), collects the four sub-skill outputs, merges their
citations, rolls up their warnings, and returns a two-block payload with a
single top-level `provenance` block naming the composite version, the
rule-set version, and every sub-skill version that contributed.

The indirection matters: direct Python imports of
`ComputeBeneishMScore`, `ComputeAltmanZScore`, `InterpretMScoreComponents`,
`InterpretZScoreComponents` would create a second dispatch path that could
drift from the registry's version pinning and audit stamping. Every
skill — CLI, API, MCP, OpenAI — hits the registry. Composites are no
different.

## Inputs

| Field | Type | Description |
|---|---|---|
| `cik` | `string` (10 digits) | Issuer CIK. |
| `fiscal_year_end` | `string` (ISO date) | 10-K fiscal period end. |

That's it — the composite flows these two fields to every sub-skill. The
market-value-of-equity fixture lookup for X4 happens inside
`compute_altman_z_score`; the t-1 prior-year lookup for Beneish happens
inside `compute_beneish_m_score`. The composite doesn't know or care.

## Outputs

| Field | Type | Description |
|---|---|---|
| `m_score_result` | `object` | `{score, flag, components, interpretations, overall_interpretation, citations, confidence, warnings}` — the union of `compute_beneish_m_score` + `interpret_m_score_components` outputs. |
| `z_score_result` | `object` | Same shape, but for Altman Z. |
| `provenance` | `object` | `{composite_skill_id, composite_version, rule_set_version, sub_skill_versions: {...}, build_id, run_at, run_id}`. |

Determinism: two back-to-back runs with identical inputs produce
byte-identical `m_score_result` and `z_score_result` blocks. Only
`provenance.run_at`, `provenance.run_id`, `provenance.build_id`, and the
per-citation `retrieved_at` timestamps move. `test_cli_api_parity.py`
enforces this for the CLI↔API parity gate.

## Typical call

```bash
# the canonical demo case
mvp run analyze_for_red_flags --cik 0001024401 --year 2000-12-31
```

Or via API:

```bash
curl -s -X POST localhost:8000/v1/skills/analyze_for_red_flags \
    -H 'content-type: application/json' \
    -d '{"cik":"0001024401","fiscal_year_end":"2000-12-31"}'
```

## Typical failure modes

Failures propagate from the sub-skills through the composite. Each
sub-skill's typed error becomes the composite's typed error (no wrapping,
no re-raising, no swallowing):

- **`unknown_filing`** — the `(cik, fiscal_year_end)` pair is not in the
  MVP sample set. Returned as a 5-field structured envelope (CLI → stderr
  with exit code 1; API → 400 with JSON body).
- **`missing_market_data`** — the Altman fixture has no row for this
  issuer / FYE. Same envelope shape.
- **`indeterminate` flags** — NOT failures. When a component input is
  null (Carvana FY2022 EBIT, for example), the sub-skill returns
  `flag: indeterminate` cleanly and the composite returns a
  two-block payload where one or both blocks have `flag: indeterminate`.
  This is the correct answer — "the data doesn't support a score" — not
  an error.

## Links

- Manifest: [`manifest.yaml`](manifest.yaml)
- Sub-skills:
  - [`../../paper_derived/compute_beneish_m_score/`](../../paper_derived/compute_beneish_m_score/)
  - [`../../paper_derived/compute_altman_z_score/`](../../paper_derived/compute_altman_z_score/)
  - [`../../interpretation/interpret_m_score_components/`](../../interpretation/interpret_m_score_components/)
  - [`../../interpretation/interpret_z_score_components/`](../../interpretation/interpret_z_score_components/)
- Integration tests: `tests/integration/test_enron_demo.py`,
  `tests/integration/test_cli_api_parity.py`
