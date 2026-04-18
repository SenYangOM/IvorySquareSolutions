# `mvp/agents/` — LLM-persona runtime

This directory holds the **engineering-layer** runtime that loads the
four MVP persona configurations from `mvp/human_layer/personas/` and
invokes them with a standard LLM interface. Nothing in this directory
contains accounting, finance, evaluation, or audit text — all of that
lives in the YAML configs under `human_layer/personas/`. That split is
Operating Principle P1 (see `../mvp_build_goal.md` §0).

## Files

| File | Purpose |
|---|---|
| `persona_runtime.py` | `Persona` / `PersonaResponse` / `PersonaRuntime` / `load_persona`. The generic loader + dispatcher. |
| `accounting_expert.py` | Thin wrapper — `PERSONA_ID = "accounting_expert"` + one-line `call()`. |
| `quant_finance_methodologist.py` | Thin wrapper. |
| `evaluation_agent.py` | Thin wrapper. |
| `citation_auditor.py` | Thin wrapper. |
| `audit_log/` | Write-target for per-call audit JSON. See below. |

A wrapper module is ~10 lines of Python: it holds a `PERSONA_ID`
constant, creates a module-level `PersonaRuntime` instance, and
delegates `call(user_message, *, cache_dir=None)` to it. No
persona-specific logic in the wrappers.

## The four personas (role, owned artifacts, contract)

### `accounting_expert`

- **Role.** Stern accounting PhD with forensic-accounting practice.
- **Model.** `claude-opus-4-7` (depth on judgment work).
- **Owned artifacts.**
  - `mvp/rules/ontology.yaml`
  - `mvp/rules/templates/m_score_components.yaml`
  - `mvp/rules/templates/z_score_components.yaml`
  - `mvp/eval/gold/beneish/*.yaml` (substantive expectations)
  - `mvp/eval/gold/altman/*.yaml` (substantive expectations)
  - Per-filing L2 interpretation text produced by
    `skills/interpretation/interpret_{m,z}_score_components/skill.py`
    (Phase 4).
- **Input format.** Two kinds of task. (a) A rule-template authoring
  task: paper summary + 16 canonical line-item names + component
  distribution over the MVP's 5 issuers → authored YAML. (b) An L2
  interpretation task: component name, computed value, underlying
  line-item values for year t and year t-1 → 2-4 sentences of
  accountant-voice interpretation with inline citations.
- **Output format.** Either a populated YAML file (task a) or a short
  natural-language passage with explicit citations (task b).
- **What a real expert would do here.** A real Stern-trained accounting
  PhD would author the same rule templates using the same paper, the
  same canonical names, and the same severity vocabulary. The
  replacement path is: replace `mvp/human_layer/personas/accounting_expert.yaml`'s
  `system_prompt` with the expert's own style guide; the runtime and
  wrapper never change. Or: the human bypasses the persona entirely
  and writes to the declarative artifacts directly — rule templates,
  gold cases, audit comments. Either way, no Python involved.

### `quant_finance_methodologist`

- **Role.** Quant-finance PhD, forensic-finance specialty. Paper
  replication specialist.
- **Model.** `claude-opus-4-7`.
- **Owned artifacts.**
  - `provenance` and `implementation_decisions` blocks of
    `mvp/skills/paper_derived/**/manifest.yaml` (Phase 4).
  - Paper-summary markdown under `mvp/skills/paper_derived/**/README.md`
    (Phase 4).
  - Replication-harness outputs that compare skill values against the
    paper's published worked examples (Phase 4/5).
- **Input format.** Four kinds. (1) Populate a provenance block from a
  PDF + skill identity. (2) Write a paper summary for the accounting
  expert. (3) Run a replication against our canonical statements and
  write up deviations. (4) Answer a focused methodology question.
- **Output format.** Precise, cited YAML or markdown. Every numeric
  claim carries a paper-page / line / table reference. Every
  implementation choice the paper leaves open is named and resolved
  with a documented rationale.
- **What a real expert would do here.** A real quant-finance PhD (or
  the author of a third-party replication of the paper) would produce
  the same provenance blocks with the same citations. Replacement is
  the same pattern: edit the YAML `system_prompt`, or bypass and write
  the manifests' provenance blocks directly.

### `evaluation_agent`

- **Role.** QA / eval engineer.
- **Model.** `claude-sonnet-4-6` (cost-managed for high-volume
  verification work per `mvp_build_goal.md` §13 decision 1).
- **Owned artifacts.**
  - `mvp/eval/gold/**/*.yaml` (the YAML shape — substantive expectations
    come from `accounting_expert`).
  - `mvp/eval/reports/*.md` (Phase 5).
  - `calibration_status` decisions on every skill manifest's
    `confidence` block (Phase 4/5).
- **Input format.** Gold-case authoring task, eval-report review task,
  or failing-case diagnosis task.
- **Output format.** Terse YAML or numeric-report markdown. Every
  claim carries a tolerance and a sample size. No calibration claims
  at n < 50.
- **What a real expert would do here.** A real QA lead would (a) author
  the gold-case YAMLs in the same shape, (b) run the eval harness
  after each code change, and (c) refuse to promote a skill's
  `calibration_status` to `"calibrated"` without ≥50 reviewed gold
  cases and a correlation check. Replacement path: same as above.

### `citation_auditor`

- **Role.** Audit / compliance reviewer.
- **Model.** `claude-sonnet-4-6`.
- **Owned artifacts.**
  - `mvp/eval/reports/integrity/*.json` (Phase 5): the integrity-report
    structure for each skill run.
  - Sampling notes under `mvp/agents/audit_log/_review_notes/` (Phase 5+).
- **Input format.** A skill-output JSON + a doc-store handle, or a
  time range to sample from `agents/audit_log/`, or a single filing
  to spot-check hash-chain continuity.
- **Output format.** Fixed-shape integrity reports. Severity is
  blocker / major / minor. Citation integrity failures are always
  blocker.
- **What a real expert would do here.** A real internal-audit partner
  would run the same integrity checks and sign the same reports. The
  checklist voice in the YAML `system_prompt` is what a real auditor
  would also use.

## Audit logging

Every call through `PersonaRuntime` writes one JSON record to
`audit_log/<YYYY-MM-DD>_<persona_id>_<short_hash>.json`. The record
captures:
- `persona_id`, `persona_version`, `persona_config_hash`
- `model`, `temperature`, `max_tokens`
- the exact `system_prompt` and `user_message` sent
- the full `response_text`
- `input_tokens`, `output_tokens`, `cache_hit`
- `called_at` (UTC ISO-8601)

The directory is never hand-edited. Reviewers sample it per
`../human_layer/audit_review_guide.md`. The `citation_auditor` persona
owns the sampling rhythm.

## Graceful no-API-key behavior

Per Phase 3 build-brief requirement:
- The runtime is importable and the four wrappers are instantiable
  without `ANTHROPIC_API_KEY`.
- A `PersonaRuntime.call()` that hits the cache succeeds without a key.
- A `PersonaRuntime.call()` that misses the cache raises
  `PersonaCallError(error_code="missing_api_key", retry_safe=False)`
  with `suggested_remediation = "Set ANTHROPIC_API_KEY or prime the
  cache via a previous recorded call."`

Tests in `tests/unit/agents/test_persona_runtime.py` cover the missing-
key path hermetically.

## Error model (Operating Principle P3)

Every error raised by this package is a typed
`mvp.lib.errors.PersonaCallError` (a `LibError` subclass) with:
- `error_code`: `persona_not_found`, `persona_schema_invalid`,
  `missing_api_key`, or `llm_call_error`.
- `error_category`: mapped to the public error envelope.
- `retry_safe`: `False` for auth / validation, `True` for upstream LLM
  transient failures.
- `persona_id`: the persona involved.
- `reason`: a short token discriminating within `error_code`.

The skill boundary (Phase 4) catches these and formats them into the
public `{error_code, error_category, human_message, retry_safe,
suggested_remediation}` envelope.
