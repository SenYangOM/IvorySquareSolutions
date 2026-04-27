IvorySquare's paper-to-skill pipeline is a six-stage LLM-orchestrated
flow — extraction, long-form digest, implementation, unit-test
authoring, replication harness, and three-persona verification — with
explicit per-stage token budgets that target ≈5M tokens per paper. Each
stage is wrapped in a cost-tracking context manager that records
per-call token counts to a per-run JSONL log; aggregation surfaces
per-stage, per-persona, and per-model totals through
`mvp.lib.cost_tracking.summarize` and the `mvp skills cost <skill_id>`
CLI. Stages are gated by structured persona verdicts — `go` / `revise`
/ `block` — written into a per-run audit-log directory under
`mvp/agents/audit_log/<run_id>/`; an upstream stage cannot proceed
until its gate persona signs off, and a `block` halts the run with a
typed `revisions_needed[]` block the caller can act on.

The four LLM persona configurations — accounting expert,
quant-finance methodologist, evaluation agent, citation auditor — each
carry the contracts they fulfil at every pipeline stage in declarative
YAML under `mvp/human_layer/personas/`, so the human-layer surface
remains disjoint from the engineering layer. The orchestrator runs in
two modes: a calibration mode that re-processes an already-onboarded
paper and emits a structured delta against the shipped artifacts, and a
fresh mode that produces a new paper-derived skill ready for promotion
into the registry. Acceptance gates encoded in `success_criteria.md`
§14 require per-stage spend within ±20% of target, paper-replication
tolerance on every worked example or a documented
`implementation_decisions[]` entry, an intact citation contract under
the citation-auditor's review, and gold cases authored for every worked
example by the evaluation agent.
