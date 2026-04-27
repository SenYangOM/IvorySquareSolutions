# Success Criteria — MVP

This document defines **how we know the MVP worked**. Companion: `mvp_build_goal.md` defines **what we're building**.

The MVP is built with LLM-subagent personas standing in for human experts. "Success" therefore has two faces: (a) the system *operates* correctly end-to-end (a runtime contract), and (b) the artifacts the personas produce are *reviewable* by a real human expert without rework (a handoff contract). Both must hold.

---

## 1. Top-line definition of done

The MVP is done when **all five** of the following are simultaneously true:

1. **End-to-end demo works on the canonical case.** A single CLI command (`mvp run analyze_for_red_flags --cik 0001024401 --year 2000`) computes **both** the Beneish M-Score and the Altman Z-Score for Enron's 2000 10-K, returns flags for each, returns per-component values, returns interpretations citing source line items, and produces a JSON output that matches the published schema in `mvp_build_goal.md` §6.
2. **The eval harness reports green on ≥4 of 5 sample filings for both paper-derived skills.** Of the 5 sample issuers, at least 4 produce M-Score values within ±0.10 of gold and the correct categorical flag, **and** at least 4 produce Altman Z values within ±0.10 of gold and the correct distress-zone classification. Any failure (in either skill) has a documented, explainable cause (e.g., known data-availability gap for pre-iXBRL filings; missing market-cap point).
3. **Every output claim resolves to a real source passage.** `eval/citation_check.py` reports 100% citation resolution across all production runs of the 5 cases. Zero fabricated locators. Zero broken hashes.
4. **A reviewer can replace any subagent persona with a human expert without changing the contracts.** Each persona's role doc, prompt, input format, and output format is sufficient that a real PhD could be onboarded in under one hour to do the same job. This is verified by §6.
5. **A clean clone runs the demo in under 30 minutes.** A fresh checkout, plus following `mvp/README.md`, plus an Anthropic API key, results in a working Enron analysis. No undocumented manual steps.
6. **Operating principles P1, P2, P3 verifiably hold** per the gate sections below (§11 Build-quality, §12 Agent-accessibility). These are not ornaments; the MVP is not done until all three pass their explicit checks.

If any of the six fails, the MVP is not done.

---

## 2. Functional acceptance

### Required end-to-end flow

A user (human or AI agent) can:

```
$ mvp ingest filings --cik 0001024401 --years 1999,2000
$ mvp ingest paper --id beneish_1999
$ mvp ingest paper --id altman_1968
$ mvp run analyze_for_red_flags --cik 0001024401 --year 2000
```

…and receive a JSON document with two top-level result blocks (`m_score_result` and `z_score_result`), each containing:

- `score`: a real number (M-score or Z-score respectively)
- `flag`: M-Score → `manipulator_likely | manipulator_unlikely | indeterminate`; Z-Score → `safe | grey_zone | distress | indeterminate`
- `components`: named ratio values (8 for M, 5 for Z) — or null with reason
- `interpretations`: per-component natural-language explanations citing specific line items in the source filing
- `citations`: an array of `(filing_id, statement_role, line_item, value, sha256)` tuples
- `confidence`: a numeric score with a textual rationale
- `warnings`: an array of any data-quality flags raised

Plus a top-level `provenance: {composite_skill_id, composite_version, rule_set_version, build_id, run_at, sub_skill_versions: {...}}` block.

And the same call via the FastAPI stub (`POST /v1/skills/analyze_for_red_flags`) returns the identical payload.

### Required reproducibility

Re-running the same call with the same inputs and the same code state produces a byte-identical output (modulo the `run_at` timestamp). LLM-involved skills (the L2 interpretation skill) achieve this either via temperature=0 + cached responses, or by recording the LLM response in the output's `provenance.llm_runs[]` block. Determinism is a contract, not an aspiration.

### Required failure modes

When inputs are missing or malformed, the skill returns a structured error rather than crashing or guessing:

- Missing prior-year filing → `flag = indeterminate`, `m_score = null`, warning explains why.
- Missing cash-flow statement → TATA component returns null with `reason: "missing_cfo"`; M-Score returns null; flag = `indeterminate`.
- iXBRL parse failure → standardization layer raises a typed exception that is caught at the skill boundary and returned as a warning, not a 500.

---

## 3. Coverage acceptance

| Item | Target | Notes |
|---|---|---|
| Filings ingested | 10 (5 issuers × 2 years) | Year t and t-1 for each |
| Papers ingested | 2 | Beneish (1999) + Altman (1968) |
| Market-cap fixture entries | 5 | One per sample issuer at fiscal year-end (Altman Z input) |
| Skills implemented (manifests + working code) | 7 | 2 fundamental, 2 interpretation, 2 paper-derived, 1 composite |
| Rule template files | 2 | `m_score_components.yaml` and `z_score_components.yaml` |
| Gold-standard cases | 10 | 5 issuers × 2 paper-derived skills (`eval/gold/beneish/` + `eval/gold/altman/`) |
| Subagent personas with documented contracts | 4 | accounting_expert, quant_finance_methodologist, evaluation_agent, citation_auditor |
| End-to-end demo cases | ≥1 (Enron 2000) | Composite call must produce both M-Score and Z-Score blocks |

No more than this is required. Adding a sixth filing or a second paper-derived skill is **out of MVP scope** and should be rejected as scope creep unless explicitly authorized.

---

## 4. Quality acceptance

### 4.1 Computational fidelity (against the source papers)

- `compute_beneish_m_score` must reproduce Beneish's published worked examples within **±0.05 on M-score** and **±2% on each component ratio**. Verified by `tests/integration/test_beneish_paper_replication.py` against the paper's reported numbers as oracle values.
- `compute_altman_z_score` must reproduce Altman's published worked examples within **±0.10 on Z-score** and **±2% on each component ratio**. Verified by `tests/integration/test_altman_paper_replication.py` against the paper's reported numbers (the matched-pair sample from Table 1 of the 1968 paper, where individual firm Z-scores are reported).

If either implementation cannot reproduce its paper's numbers, the cause must be documented in the manifest's `implementation_decisions` block — *not* silently fixed via fudge factors.

### 4.2 Eval pass rate (against gold standard)

| Metric | Target | Measured by |
|---|---|---|
| `m_score_within_0.10` | ≥ 4/5 cases | `eval/runner.py` |
| `m_score_flag_match_rate` | ≥ 4/5 cases | `eval/runner.py` |
| `z_score_within_0.10` | ≥ 4/5 cases | `eval/runner.py` |
| `z_score_zone_match_rate` | ≥ 4/5 cases (safe / grey / distress) | `eval/runner.py` |
| `citation_resolves` (per-claim) | 100% | `eval/citation_check.py` |
| `gold_present_for_all_cases` | 10/10 | `eval/runner.py` |

Any failure on the first two metrics for a specific case must have a one-paragraph written explanation in the eval report (e.g., "Enron 1999 prior-year iXBRL not available; standardization used PDF table extraction with known ±5% noise").

### 4.3 Citation integrity

For every output claim that the citation contract requires:

- The citation's `(doc_id, locator)` resolves to a real passage in the doc store.
- The `excerpt_hash` matches a sha256 of the resolved passage.
- The cited passage actually contains the claimed value (numeric tolerance of ±0.5% to allow for rounding in narrative restatements).

Tolerance for failures: **zero**. A single broken citation blocks the MVP.

### 4.4 Determinism

For each of the 5 sample cases, two independent runs of `analyze_for_earnings_manipulation` must produce outputs that differ only in:
- `provenance.run_at`
- `provenance.run_id`

All other fields byte-identical. LLM-involved fields (interpretation text from the L2 skill) achieve this via cached LLM responses keyed on input hash.

### 4.5 Confidence calibration (degraded-mode acceptance)

At MVP scale (5 cases) we cannot fully calibrate confidence scores. The acceptance bar is weaker:

- The confidence model is **documented**, not necessarily calibrated. The manifest's `confidence.calibration_status` is `"uncalibrated_at_mvp"`.
- Confidence scores must at minimum **monotonically degrade** when known data-quality issues are present (e.g., Enron with PDF-extracted tables should report lower confidence than Apple with full iXBRL).
- A scatter plot of confidence vs. eval-metric outcome must trend in the right direction (high confidence ↔ high pass rate), even if not statistically meaningful at n=5.

Full calibration is a post-MVP milestone (requires ≥50 gold cases).

---

## 5. Documentation acceptance

The MVP ships with the following documentation, all of which must exist and be accurate:

- `mvp/README.md` — quickstart that takes a fresh reader from clone → working Enron analysis in <30 min. Includes setup, env vars, three working CLI commands, expected outputs.
- `mvp/skills/paper_derived/compute_beneish_m_score/README.md` — paper summary in the skill author's own words (the `quant_finance_methodologist` persona's writeup), implementation decisions, deviations from paper, validation evidence.
- `mvp/rules/README.md` — guide for authoring or reviewing rule templates. Worked example using `m_score_components.yaml`.
- `mvp/agents/README.md` — for each subagent persona: prompt, contract, example inputs/outputs, and the path for human-expert replacement.
- Each skill manifest is fully populated (no `TODO`, no empty fields except those legitimately N/A).
- `mvp/data/manifest.jsonl` is human-readable and chronologically complete for the 11 ingestion events.

What we do **not** require at MVP: API reference docs auto-generated from code, architecture decision records (ADRs), CONTRIBUTING.md, CI configuration. These are post-MVP.

---

## 6. Reviewability acceptance (the human-handoff contract)

The MVP exists in part to be reviewed by real human experts. To pass the reviewability bar:

- For each of the 4 subagent personas, the `agents/README.md` includes a section "What a real expert would do here" describing how a human PhD would replace the subagent. A reviewer reading this section understands the role in <10 minutes.
- The `accounting_expert`-authored rule template (`rules/templates/m_score_components.yaml`) is reviewable by a human accounting expert — meaning it reads as YAML a human would write, not as machine-generated YAML. No vacuous `severity: "medium"` placeholders; every rule has substantive interpretation text.
- The `quant_finance_methodologist`-authored skill manifest provenance block contains specific, falsifiable claims about the source paper (formulas, sample sizes, threshold values) that a human reviewer can spot-check against the PDF in <30 minutes.
- All gold-standard YAML files in `eval/gold/beneish/` are written so an accounting expert can review and amend them without reading any code.
- For each LLM call made by any subagent persona during MVP construction, the prompt and response are saved to `mvp/agents/audit_log/` with a sha256 of inputs. This lets a reviewer audit *what the subagent saw* and *what it produced*, not just the final output.

---

## 7. Per-layer Definition of Done

| Layer | "Done" means |
|---|---|
| L0 (`lib/`, `ingestion/`) | All 11 source documents fetched and verifiable by hash; SEC fair-access compliant (≤10 req/s, declared UA); rate-limit verified by a logged-during-ingestion timing trace. |
| L1 (`store/`) | Each ingested doc is hash-addressable; reading any doc by hash returns byte-identical content; `manifest.jsonl` is append-only and complete. |
| L2 (`standardize/`) | For each of the 10 filings, a canonical IS/BS/CF JSON exists with line-item-level citations to source. Concept-mapping decisions logged to `standardize/mapping_log.jsonl`. |
| L3a (`rules/`) | `m_score_components.yaml` exists, fully populated for all 8 components, reviewable as written by a human. Loads via `pydantic` schema. |
| L3b (`engine/`) | `rule_executor.py` applies the YAML rules to L2 outputs deterministically. `citation_validator.py` verifies all required citations are present before returning. |
| L4 (`skills/`) | All 5 MVP skills load via the registry; each has a passing manifest schema validation; each has at least one passing integration test. |
| L5 (`api/`, `cli/`) | Both surfaces produce identical outputs for identical inputs. CLI prints structured JSON; API returns the same JSON over HTTP. |
| Cross-cutting eval | `mvp eval` produces a one-page report with pass/fail per case, citation-integrity status, and any warnings. |
| Cross-cutting agents | Each persona has a documented prompt, contract, and audit log of MVP-construction calls. |

---

## 8. Negative gates — what "MVP fails" looks like

The MVP is **not** done if any of the following are true:

- The Enron case requires manual intervention beyond `mvp ingest` and `mvp run` to produce its output.
- Any output contains a citation that doesn't resolve, or a hash that doesn't match.
- Either L2 interpretation skill (`interpret_m_score_components`, `interpret_z_score_components`) produces text that *summarizes* what the score means generically, rather than analyzing *this specific company's specific component values* with reference to specific line items.
- Either paper-derived skill cannot reproduce its source paper's worked examples (Beneish or Altman).
- Either rule template file (M-Score or Z-Score) is empty, mostly placeholders, or written in a way an accounting expert wouldn't recognize as their kind of artifact.
- The codebase contains any cross-layer upward imports (e.g., `lib/` imports from `skills/`) — modularity violation.
- Subagent personas are invoked ad hoc rather than via a documented contract — meaning a human couldn't replace them without code changes.
- The 4-of-5-cases-pass eval bar is missed and the failures are unexplained.

---

## 9. Explicitly NOT measured at MVP

To prevent over-engineering, we explicitly *do not* measure these at MVP and they should not block release:

- Throughput / QPS — single-call latency only.
- Production reliability metrics (uptime, error budgets) — N/A.
- Multi-tenant correctness — single-tenant only.
- Multi-jurisdiction correctness — US only.
- Coverage of skills beyond the MVP catalogue — explicitly limited to 5 skills.
- Coverage of issuers beyond the 5 sample filings — explicitly limited.
- Calibrated confidence scores — uncalibrated at MVP is acceptable.
- Restatement-aware re-running — restatements are *logged*, not *acted on*.
- Cost optimization beyond "the demo runs for under $5 in API tokens" — full cost engineering is post-MVP.
- API security beyond a localhost stub — Stage 2 production is post-MVP.

---

## 10. The "demo morning" acceptance test

The single composite test the MVP must pass: a 30-minute live walkthrough.

1. Reviewer clones the repo. Reads `mvp/README.md`. Sets `ANTHROPIC_API_KEY`. (5 min)
2. Reviewer runs `mvp ingest` for one of the 5 issuers. Sees data appear under `data/filings/`. (3 min)
3. Reviewer runs `mvp run analyze_for_red_flags` for the Enron case. Sees JSON output with both M-Score and Z-Score blocks, flags for each, and per-component citations. (2 min)
4. Reviewer reads the skill manifests for `compute_beneish_m_score` and `compute_altman_z_score`. Understands what each does, where it came from, and its limits. (5 min)
5. Reviewer reads `rules/templates/m_score_components.yaml` (and skims the Altman counterpart). Understands one rule and could imagine editing it. (5 min)
6. Reviewer reads `agents/README.md`'s description of `accounting_expert`. Understands what a human PhD would do in this role. (5 min)
7. Reviewer runs `mvp eval`. Sees the report. Understands what's passing and what's failing. (5 min)

If a reviewer with no prior context can complete this walkthrough in 30 minutes and come away understanding what was built and what would need to happen to scale it — the MVP is done.

---

## 11. Build-quality gates (Operating Principle P2)

Verifiable checks that the codebase reflects the "don't over-engineer, don't be lazy" bar:

- **Zero TODO / FIXME / XXX markers** in shipped code (excluding documented future-work notes in READMEs that explicitly belong to post-MVP scope). A grep on the `mvp/` tree returns no matches.
- **Zero `pass` placeholders** in production code paths. Functions either implement their contract or they don't exist.
- **Zero `except: pass`** or bare-`except` constructs. Every caught exception either re-raises a typed error or is logged with context.
- **Zero commented-out blocks** of more than 2 lines. Either delete or finish.
- **Every Python module is importable** without warnings. No unused imports, no shadowed names, no broken type annotations.
- **Every shipped function has tests OR is exercised by an integration test.** No "it works on the demo so it's fine."
- **No abstraction without two callers.** If a class, decorator, or helper has only one usage site, inline it. Wait for the second caller before extracting.
- **No configuration knob without a documented user.** Every config value either has a non-default caller in the codebase or is documented as a planned post-MVP extension.
- **No silent fallbacks.** If iXBRL parsing fails and the code falls back to PDF extraction, that fact is logged and surfaced in the output's `warnings` block.

A failure on any of the above blocks the MVP. The principle is not aspirational — it is enforced.

---

## 12. Agent-accessibility gates (Operating Principle P3)

Verifiable checks that the surface is agent-native, not human-first-with-an-API-bolted-on:

- **`GET /mcp/tools`** returns a valid MCP tool catalog covering all 7 MVP skills. The catalog is consumable by an MCP client (e.g., Claude Desktop or any MCP-compatible agent) without modification.
- **`GET /openai/tools`** returns a valid OpenAI `tools=[...]` array covering all 7 MVP skills. An OpenAI-style chat-completion call with these tools as `tools=` parameter results in correct skill invocation by GPT-class models.
- **`description_for_llm`** is populated and substantive on every manifest. A second-language reader (an LLM in this case) given only the descriptions of all 7 skills can correctly identify which skill to call for each of these test queries:
  - "Is Enron's 2000 filing showing earnings manipulation signals?" → `analyze_for_red_flags` or `compute_beneish_m_score`
  - "What's Carvana's distress risk per Altman?" → `compute_altman_z_score`
  - "Show me the income statement for Apple's 2023 10-K" → `extract_canonical_statements`
- **Structured errors on every failure path.** No HTTP 500 with a stack trace ever leaks to the API caller. Every error response matches `{error_code: str, error_category: enum, human_message: str, retry_safe: bool, suggested_remediation: str}`.
- **CLI ↔ API parity.** For each of the 7 skills, a CLI invocation and the equivalent API POST produce byte-identical output bodies (modulo timestamps). Verified by `tests/integration/test_cli_api_parity.py`.
- **Citations are resolvable via skill, not by parsing.** A `resolve_citation` skill (or a registry endpoint) takes a `(doc_id, locator)` tuple and returns the cited passage text + surrounding context. Agents do not have to scrape the doc store directly.
- **The natural-agent test.** A real Claude or GPT instance, given only the MCP tool catalog and the prompt "analyze whether Enron's 2000 10-K shows accounting red flags, with citations," produces a sensible multi-skill workflow ending in a cited red-flag summary — without the user (or this document) telling the agent which skills to call in which order. This is the single most important agent-accessibility test.

If the natural-agent test fails, the surface is not agent-native and the MVP is not done — even if every other gate passes.

---

## 13. Workshop scope (team-internal tooling)

`mvp_build_goal.md` §15 introduces a sibling folder `workshop/` at the repo root, holding team-internal tools and playbooks that support MVP maintenance and skill expansion. `workshop/` is **NOT audited by the top-line gates in §1** — the MVP done-bar is defined over `mvp/` only. What `workshop/` must satisfy at MVP completion is a lightweight skeleton. This section is intentionally softer than §1–§12: workshop is where the team works, not where the product ships.

### 13.1 Required skeleton at MVP completion

- `workshop/README.md` — one-page overview: what workshop is, when a team member reaches for it vs `mvp/`, subfolder index.
- `workshop/paper_to_skill/README.md` — step-by-step playbook documenting how Beneish (1999) and Altman (1968) were onboarded during Phase 3–4. Written *retrospectively* from the build; no new scripts required at MVP. Must cover: (a) how to read a paper and extract coefficients, thresholds, and worked examples; (b) how to author the skill manifest's `provenance` and `implementation_decisions` blocks; (c) how to write rule templates from the paper's interpretation guidance; (d) how to author gold-standard cases; (e) the replication bar a new skill must hit before shipping.
- `workshop/docs/paper_onboarding_playbook.md` — expanded version of the above, with specific lessons-learned callouts from Phase 3–4 (e.g., "the Beneish threshold printed in the 1999 paper is -1.78, not -2.22 — check the source before trusting popular references"; "the Altman X5 coefficient is 0.999, not the rounded 1.0").
- `workshop/docs/skill_design_checklist.md` — a one-page review checklist a reviewer runs before approving a new skill's PR. Derived from what the Phase 4 review needed.
- `workshop/{research,coverage,eval_ops,maintenance}/README.md` — one-paragraph placeholder per folder: what goes here, who owns it, what the first real script in it will likely be.

### 13.2 Explicitly NOT required at MVP

- Implementation of `workshop/paper_to_skill/extract_paper.py`, `draft_manifest.py`, `replication_harness.py`, or `templates/*.yaml`. These are post-MVP and land when the second paper (beyond Beneish + Altman) is onboarded.
- Any executable script in `research/`, `coverage/`, `eval_ops/`, or `maintenance/`. READMEs only.
- Tests for workshop code. Workshop is exempt from the full-test bar.

### 13.3 Separation contract

- `workshop/` scripts MAY import from `mvp.lib` and MAY call `mvp/skills/` via the registry.
- `workshop/` scripts MUST NOT import from `mvp/skills/**/skill.py` or `mvp/engine/` directly — the registry is the seam.
- `mvp/` code MUST NOT import from `workshop/`. Workshop is strictly a consumer of mvp, never a dependency of it.

A single grep verifies the contract at MVP: `grep -R "from workshop" mvp/ || echo OK` must print `OK`.

### 13.4 Quality contract

Workshop content is team-owned and intentionally looser:
- Zero-TODO and full-test bars (§11) do **not** apply inside `workshop/`.
- Exploratory notebooks, scratch scripts, and commented-out experiments are permitted inside `workshop/research/` and `workshop/experiments/` if that folder is later added.
- The separation contract (§13.3) is the only hard rule.

### 13.5 Why this is separate from §1

The MVP is defined by what a user gets. Workshop is defined by how the team works. Gating MVP-done on team-tool completeness would delay shipping and miss the point — team tools earn their keep by saving the *next* engineer time, which requires MVP-shipping first to know what was actually tedious.

---

## 14. Deep paper-to-skill pipeline (post-MVP, Workstream A)

The post-MVP `workshop/paper_to_skill/orchestrator.py` runs an
LLM-orchestrated six-stage pipeline (A1 Extract → A2 Digest → A3
Implementation → A4 Unit-test authoring → A5 Replication harness →
A6 Verification + persona review) with explicit per-stage budgets and
persona-review gates. Acceptance gates for one paper through the deep
pipeline:

### 14.1 Stage budgets

Per-paper target ≈ 5M tokens, distributed across stages:

| Stage | Driver persona | Gate persona | Target tokens |
|---|---|---|---:|
| A1_extract | quant_finance_methodologist (deterministic + review) | quant_finance_methodologist | 500_000 |
| A2_digest | quant_finance_methodologist | accounting_expert | 1_000_000 |
| A3_implementation | quant_finance_methodologist | accounting_expert | 1_000_000 |
| A4_unit_tests | evaluation_agent | evaluation_agent | 500_000 |
| A5_replication | quant_finance_methodologist | evaluation_agent | 500_000 |
| A6_verification | citation_auditor + accounting_expert + evaluation_agent | evaluation_agent | 1_500_000 |

Each stage's actual spend is logged via
`mvp.lib.cost_tracking.track_cost` to
`mvp/agents/cost_log/<run_id>.jsonl`. The per-stage budget is satisfied
when actual spend lands within ±20% of the target, OR the deviation
is documented in the run report's `revisions_needed` block.

### 14.2 Per-paper acceptance gates

A run on one paper is accepted when **all** of:

- The pipeline's terminal verdict is `go` or `complete` (no
  `block` was emitted by any persona gate).
- Every stage's spend is within ±20% of its target.
- For paper-derived skills with worked examples, the A5 replication
  reproduces every reported worked example within ±0.05 on the
  headline scalar and ±2% on each component, OR documents the
  deviation in `implementation_decisions[]`.
- The A6 citation_auditor's gate verdict is `go` (citation contract
  is intact, locator_format matches the catalog convention, every
  required_per_field rule names a canonical line item).
- The A6 evaluation_agent emits gold-case YAMLs for the paper's
  worked examples; each YAML matches
  `mvp/human_layer/gold_authoring_guide.md`.
- For `mode='fresh'`, after promotion, `mvp eval` stays green
  (the §4.2 gates continue to hold for the pre-existing skills, and
  the new skill's manifest-declared `eval_metrics` all pass).

### 14.3 Calibration-mode contract

A `mode='calibration'` run on an already-onboarded paper additionally
emits a delta against the shipped artifacts via
`workshop.paper_to_skill.orchestrator.compare_calibration_outputs`.
Acceptable deltas:

- The drafted manifest's top-level key set is a superset of the
  shipped manifest's top-level key set (no required block omitted).
- The drafted skill.py size is within ±50% of the shipped skill.py
  size.
- The drafted `implementation_decisions[]` enumerates at least every
  decision the shipped manifest already records.

Bigger deltas are acceptable when accompanied by a written
explanation in the calibration delta report (the report is the
human-facing artifact; the gates above are the machine-facing ones).
