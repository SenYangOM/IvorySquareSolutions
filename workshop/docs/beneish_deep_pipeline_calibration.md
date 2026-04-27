# Beneish 1999 — Deep Pipeline Calibration Report

Calibration run of the IvorySquare deep paper-to-skill pipeline against the already-shipped `compute_beneish_m_score` artifacts. Live LLM calls go to `claude-sonnet-4-6` with extended thinking enabled at `budget_tokens=5000`.

**Run id:** `beneish_1999__20260427T043039Z`
**Final verdict:** `revise`
**Audit log directory:** `/mnt/nvme2/iv/research/IvorySquare/mvp/agents/audit_log/beneish_1999__20260427T043039Z`

## Per-stage spend

Token totals are reported twice: the cost-tracking module records each persona call as both a `raw_llm` and a `persona_runtime` event, so the naive `summarize` total double-counts. The `raw_llm`-only column is the actual API spend; the cost-tracker line is what `mvp.lib.cost_tracking.summarize` returns today.

| Stage | Target | n_calls (raw_llm) | input | output | total (raw_llm) | total (cost-tracker, doubled) |
|-------|--------|-------------------|-------|--------|-----------------|-------------------------------|
| `A1_extract` |   500,000 |   1 |  3,047 |  4,690 |   7,737 |  15,474 |
| `A2_digest` | 1,000,000 |   2 |  8,677 | 14,543 |  23,220 |  46,440 |
| `A3_implementation` | 1,000,000 |   1 |  6,957 | 16,999 |  23,956 |  47,912 |
| `A4_unit_tests` |   500,000 |   1 |  6,377 | 12,552 |  18,929 |  37,858 |
| `A5_replication` |   500,000 |   2 | 12,969 | 11,510 |  24,479 |  48,958 |
| `A6_verification` | 1,500,000 |   2 |  4,794 |  7,200 |  11,994 |  23,988 |
| **Total** | — | 9 | 42,821 | 67,494 | 110,315 | 220,630 |

## Stage verdicts

- **A1_extract** — verdict: `go` (persona: quant_finance_methodologist). Extracted 18 formula hits and 0 TOC entries from beneish_1999.pdf; methodologist review verdict: go.
- **A2_digest** — verdict: `go` (persona: accounting_expert). Digest produced (19497 chars); audit produced (16667 chars); verdict: go.
- **A3_implementation** — verdict: `revise` (persona: accounting_expert). skill.py compile=True; manifest validates=False; rule_template absent; verdict: revise.
- **A4_unit_tests** — verdict: `revise` (persona: evaluation_agent). Authored 0 test functions; compile=True; verdict: revise.
- **A5_replication** — verdict: `go` (persona: evaluation_agent). Replication report (23401 chars); implementation_decisions block present; verdict: go.
- **A6_verification** — verdict: `go` (persona: evaluation_agent). 3-persona verification: citation_auditor=go, accounting_expert=go, evaluation_agent=go; composite: go.

## Delta against shipped artifacts

### `skill.py`
- drafted_present: `True`
- shipped_present: `True`
- drafted_size: `27903`
- drafted_lines: `663`
- shipped_size: `14999`
- shipped_lines: `412`
- size_delta_bytes: `12904`
- line_delta: `251`

### `manifest.yaml`
- drafted_keys: `[]`
- shipped_keys: `['citation_contract', 'confidence', 'cost_estimate', 'dependencies', 'description_for_llm', 'evaluation', 'examples', 'implementation_decisions', 'inputs', 'layer', 'limitations', 'maintainer_persona', 'outputs', 'provenance', 'skill_id', 'status', 'version']`
- only_in_drafted: `[]`
- only_in_shipped: `['citation_contract', 'confidence', 'cost_estimate', 'dependencies', 'description_for_llm', 'evaluation', 'examples', 'implementation_decisions', 'inputs', 'layer', 'limitations', 'maintainer_persona', 'outputs', 'provenance', 'skill_id', 'status', 'version']`
- intersection: `[]`

- gold cases shipped (count): `5`
- implementation_decisions drafted by deep pipeline: `10`

## Notes

- The deep pipeline writes its drafted artifacts under `mvp/agents/audit_log/<run_id>/A3_implementation/` rather than overwriting the production `mvp/skills/paper_derived/compute_beneish_m_score/` directory. `mvp eval` is therefore unaffected by calibration runs.
- Stages run with `claude-sonnet-4-6` and `extended_thinking={budget_tokens=5000}`; the runtime's effective `max_tokens` is `12,000 + 5,000 = 17,000` so visible-text generation has 12,000 tokens of headroom on top of the thinking budget.
- A3 emitted a 663-line `skill.py` (27,903 bytes) that compiles cleanly. Its `revise` verdict reflects two structural artifacts of the orchestrator's regex-based extraction rather than substantive defects: (a) the response's manifest YAML block was truncated when the 17,000-token output ceiling was reached after the long `skill.py` block, so `manifest.yaml` did not parse as valid YAML; (b) `_GATE_VERDICT_RE` did not find a fenced JSON gate verdict block in the implementation response (drivers don't always emit one) and the audit step's verdict defaulted to `revise` once the manifest validation failed.
- A4 emitted a 897-line pytest file (`test_beneish_1999.py`) with 58 test functions, all written as methods inside `class TestX:` containers per pytest convention. The orchestrator's regex `^def\s+test_` only matches top-level functions, so the count read as zero and the gate emitted `revise`. Compile passed.
- A5 replication report covers Beneish's worked-example firms with arithmetic walked through against the drafted skill, and produces an `A5_implementation_decisions.yaml` block with ten entries (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA receivables-treatment, TATA sign-convention, threshold semantics).
- A6 verification produced a `go` composite verdict: citation_auditor `go`, accounting_expert skipped (no rule template; the M-Score is L1, not L2/L3), evaluation_agent `go` with gold-case YAMLs covering the worked examples.
- Cost-log records appear twice per call (one `raw_llm` event, one `persona_runtime` event); `mvp.lib.cost_tracking.summarize` aggregates both and therefore reports double the actual API spend. The `raw_llm`-only column above is the truth.
