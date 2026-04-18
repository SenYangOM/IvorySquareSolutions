# Spec updates during the MVP build

Append-only log of changes to `goal_driven.txt`, `mvp_build_goal.md`, and `success_criteria.md` that happen **after** a subagent's phase prompt was originally drafted. Every subagent spawned from Phase 3 onward MUST read this file in full before starting work. Updates here override anything inconsistent in a previously-drafted phase prompt.

---

## 2026-04-17 — Introduced sibling `workshop/` directory (load-bearing)

**Affected spec files:**
- `goal_driven.txt` — added a "Parallel scope note" block after the success-criteria pointer. Says the goal-driven build targets `mvp/`; `workshop/` is outside the done-bar.
- `mvp_build_goal.md` — **§5 repo structure** now shows `workshop/` as a repo-root sibling to `mvp/` (with its full subfolder tree); **§12 Phase 7** now includes a workshop-skeleton bootstrap bullet; **§14 out-of-scope** adds a line saying workshop executable tooling is post-MVP; **NEW §15** fully specifies workshop (purpose, hero workflow `paper_to_skill/`, subfolders, MVP-scope contract, separation contract, principle P1 application, and a "when to reach for workshop vs mvp" table).
- `success_criteria.md` — **NEW §13** specifies workshop's MVP-completion contract (required skeleton, explicit NOT-required list, separation contract with one-line grep gate, looser quality contract, and the rationale for keeping workshop out of §1 top-line gates).

**What this means operationally for each remaining phase:**

- **Phase 2 (in progress):** No impact. Phase 2 is scoped to `mvp/store/` and `mvp/standardize/`. Do not create anything under `workshop/`.
- **Phase 3 (rule-set authoring):** No direct impact. Phase 3 writes rule templates under `mvp/rules/` and persona YAMLs under `mvp/human_layer/`. These remain in `mvp/`. When documenting decisions in the skill manifest's `implementation_decisions` block, you MAY reference the future `workshop/docs/paper_onboarding_playbook.md` as the forward home for playbook-level prose.
- **Phase 4 (engine + skills):** No direct impact on the skill code itself. If you find yourself wanting to write a helper that *supports* skill authorship (rather than *being* a skill), that helper is workshop material and should be deferred to Phase 7 — not quietly slipped into `mvp/`.
- **Phase 5 (eval + gold):** No direct impact. Eval harness and gold cases stay under `mvp/eval/`.
- **Phase 6 (API + CLI):** No direct impact. API + CLI surfaces `mvp/skills/` only. They MUST NOT expose `workshop/` anything.
- **Phase 7 (docs + reviewability + gates):** **Heavy impact.** You are responsible for bootstrapping the workshop skeleton. Deliverables per `success_criteria.md` §13.1:
  1. `workshop/README.md` — one-page overview + subfolder index.
  2. `workshop/paper_to_skill/README.md` — step-by-step retrospective playbook from Phase 3–4 (Beneish + Altman onboarding). Must cover: paper reading, coefficient/threshold extraction, manifest `provenance` authoring, `implementation_decisions` authoring, rule-template authoring, gold-case authoring, and the replication bar.
  3. `workshop/docs/paper_onboarding_playbook.md` — expanded playbook with lessons-learned callouts. Must include at minimum: the Beneish -1.78 vs -2.22 threshold correction (1999 paper says -1.78; the -2.22 comes from Beneish 2013), and the Altman X5 coefficient precision (1968 paper says 0.999, not rounded 1.0). Both came out of the Phase 1 research work.
  4. `workshop/docs/skill_design_checklist.md` — per-skill review checklist derived from what Phase 4 review needed.
  5. `workshop/{research,coverage,eval_ops,maintenance}/README.md` — one-paragraph placeholders each.
  Separation-contract gate: `grep -R "from workshop" mvp/` must print nothing. Run it and record the result in the Phase 7 audit.
  Quality bar note: `workshop/` itself is exempt from the zero-TODO / full-test gate (that bar applies to `mvp/` only per §11 and §13.4).

**Post-hoc review rule:** If you are a subagent and you notice any instruction in your phase prompt that contradicts this file, trust this file and flag the discrepancy in your final report.

---

## 2026-04-17 — Criteria-check loop continues past Phase 7 (master-loop rule)

**Scope:** This is a master-agent rule, not a subagent rule. It is recorded here for operational transparency.

User reiterated that `goal_driven.txt`'s loop pseudocode keeps running past Phase 7. Completion of Phase 7's self-report is **not** the exit condition. The exit condition is: all six top-line gates in `success_criteria.md` §1 simultaneously pass in one contiguous verification pass.

**Master's post-Phase-7 procedure:**

1. When Phase 7 subagent reports done, do NOT mark MVP complete yet.
2. Run the full gate-verification pass as a distinct master-loop step:
   - `mvp/eval/runner.py` live against all 10 gold cases → must report ≥4/5 pass for **both** M-Score and Altman Z.
   - CLI `mvp run analyze_for_red_flags --cik 0001024401 --year 2000` live → must produce both result blocks with components, interpretations, citations.
   - `mvp/eval/citation_check.py` → must report 100% citation resolution across all 5 cases.
   - Natural-agent test per `success_criteria.md` §12 → must pass.
   - 30-min clean-clone walkthrough per `success_criteria.md` §10.
   - `grep -RnE "TODO|FIXME|XXX|^[[:space:]]*pass[[:space:]]*$|except:[[:space:]]*$" mvp/` → must print nothing.
   - `grep -R "from workshop" mvp/` → must print nothing (separation contract per §13).
3. If any gate fails, spawn a **Phase 8 fixer** subagent scoped to the failing gate only (e.g., "Phase 8 fixer — Carvana Altman Z within-tolerance fail"). Fixer name pattern: `Phase 8 fixer — <gate_id>: <brief>`.
4. Loop steps 2–3 until all gates pass contiguously.
5. Only then: update `BUILD_STATE.json` with `all_gates_passed: true` + final gate report, message the user that the MVP is done.

This section exists to prevent any master-agent instance (including one resuming after a context rollover) from mistaking "Phase 7 subagent reported done" for "MVP is done."

---

## 2026-04-17 — `paper_examples/` practice corpus (post-MVP workstream)

**New directory:** `/home/iv/research/Proj_ongoing/paper_examples/` was added by the user with 5 accounting/finance paper PDFs:
1. `fundamentals_text.pdf`
2. `J of Accounting Research - 2024 - KIM - Context‐Based Interpretation of Financial Information.pdf`
3. `s11142-025-09885-5.pdf` (Review of Accounting Studies)
4. `ssrn-4429658.pdf` (SSRN working paper)
5. `ssrn-4480309.pdf` (SSRN working paper)

**Directive from the user:** after MVP is established AND the workshop skeleton is built (Phase 7), apply the `workshop/paper_to_skill/` playbook to each of these 5 papers — turn each into a shipped skill that fits into the MVP library. Follow the goal-driven master/subagent loop pattern per paper: spawn a subagent, verify the paper's skill actually works (manifest valid, paper-replication test passes, registry-discoverable, eval still green), restart if inactive, proceed to next paper only on confirmed success.

**Scope boundary:** this is a **post-MVP workstream**. It runs AFTER `success_criteria.md` §1 gates all pass (Task #9). It does not replace or delay MVP completion.

**Per-paper subagent contract** (what "done" means for ONE paper):
1. Paper PDF ingested into `mvp/data/papers/<paper_id>.pdf` with meta + abstract per the existing `papers_ingest.py` pattern.
2. `quant_finance_methodologist` extraction: skill scope decision ("is this a paper-derived L3 skill, an L2 interpretation skill, or does it not fit the existing layer taxonomy?"), formulas identified, coefficients/thresholds recorded, worked examples noted. Recorded in `workshop/paper_to_skill/notes/<paper_id>.md`.
3. Skill implemented at the right layer: `mvp/skills/<layer>/<skill_id>/{skill.py,manifest.yaml,README.md}` with full §6 manifest including `implementation_decisions`.
4. Rule template authored (if the skill needs per-component interpretation): `mvp/rules/templates/<skill_id>_components.yaml`.
5. Paper-replication integration test: `tests/integration/test_<skill_id>_paper_replication.py` asserting implementation against the paper's own reported worked examples within ±0.05 on the headline metric and ±2% on components (analogous to `test_beneish_paper_replication.py`).
6. Registry discovery: skill appears in `registry.mcp_catalog()` and `registry.openai_catalog()`.
7. If the skill can plausibly run against one of the 5 MVP sample filings, add a gold case under `eval/gold/<skill_id>/<issuer>_<year>.yaml` (opportunistic — not required for every paper).
8. `eval/runner.py` still green (pre-existing 4/5 and 5/5 on M and Z unchanged; citation resolution still 100%).
9. No violation of the separation contract (§13.3): `grep -R "from workshop" mvp/` still prints nothing after the paper's skill lands.
10. `workshop/docs/paper_onboarding_playbook.md` updated with lessons-learned from that paper (one bullet per paper).

**Per-paper goal-driven loop (master-agent procedure):**
- Spawn a subagent named `paper-to-skill #N: <paper_id>` for paper N.
- Wait for completion notification OR at each master wake-up check activity.
- If subagent returns success: verify the 10 criteria above with direct tool calls. If all pass, move to paper N+1. If any fail, spawn a narrow fixer.
- If subagent returns inactive/errored before completion: restart a fresh subagent with the same name and full SPEC_UPDATES.md + partial-state context.
- Loop ends when all 5 papers have shipped skills with all 10 criteria met for each.

**Workshop-playbook feedback loop:** each paper processed is a chance to strengthen `workshop/paper_to_skill/README.md` and `workshop/docs/paper_onboarding_playbook.md`. If the workflow for paper N was smoother than paper N-1 because we improved the playbook, record that. If paper N revealed a gap not seen in Beneish/Altman MVP work, add the gap + resolution as a playbook callout.

**Rule for not letting this delay MVP done:** Task #9 (gate verification) MUST pass before any paper-to-skill subagent is spawned. If you're tempted to start this workstream while MVP gates are still failing, don't — finish MVP first.

**Dual-growth directive (added 2026-04-17).** Every paper processed MUST grow both codebases — this is not optional:

1. **`mvp/` grows with at least one new shipped skill per paper.** If after reading the paper you conclude it doesn't yield a useful skill, that is a research-design problem, not an excuse to skip. Either find the skill inside the paper, or escalate to the user with a concrete proposal (e.g., "this paper is better as an L2 interpretation over an existing L3 than as its own skill"). Do NOT silently add a paper with no corresponding `mvp/skills/*` contribution.

2. **`workshop/` grows every iteration.** During each paper's work, actively ask: (i) what workshop script would have saved time here? write it into `workshop/<subfolder>/`; (ii) which existing workshop script was too weak or missing a feature? fix it now, with the paper as a regression case; (iii) which playbook step was ambiguous? improve `workshop/docs/paper_onboarding_playbook.md` with a concrete callout.

   Minimum workshop deltas per paper:
   - Append at least one lessons-learned callout to `workshop/docs/paper_onboarding_playbook.md`.
   - If the paper's formulas needed extraction from the PDF: either improve `workshop/paper_to_skill/extract_paper.py` (if it exists) or write a first version of it (scoped to what this paper needed).
   - If the paper's reported worked examples required a harness to verify replication: either improve `workshop/paper_to_skill/replication_harness.py` or write its first version.
   - If any part of the workflow felt ad-hoc, codify it — even a 20-line CLI helper is worth committing. Workshop/ quality bar is softer than mvp/ (per §13.4), so a rough first version beats nothing.

3. **Workshop growth compounds.** Paper 1 creates the rough first draft of `extract_paper.py`. Paper 2 hardens it against a second paper's quirks. By paper 5, the workshop tooling should be robust enough that onboarding paper 6 is visibly faster than paper 1 was. Master's loop should measure this qualitatively — report wall-clock time per paper in the final `BUILD_LOG.md` summary, along with a "what got faster" note.

4. **Cross-checks at the end of each paper:**
   - `grep -R "from workshop" mvp/` still prints nothing (separation contract intact — workshop improvements never accidentally become mvp dependencies).
   - Full eval runner still green (new skills don't break existing ones; citations still resolve).
   - `mvp/skills/registry.py` now discovers one more skill.
   - `workshop/docs/paper_onboarding_playbook.md` has at least one new section/callout.

The dual-growth directive makes the paper-processing workstream genuinely useful beyond the 5 papers themselves: it's how we harden the whole operation for the team member who comes after us.

---

## 2026-04-17 12:39 UTC — Phase 4 partial-ship snapshot (usage-budget interruption)

**Trigger:** The Phase 4 builder subagent hit an Anthropic API usage-budget cap mid-flight ("You're out of extra usage · resets 10am (UTC)"). It completed ~15 min / 76 tool-uses of work before termination. No orphaned half-files: every shipped module imports cleanly.

**What landed (Phase 4 partial):**
- `mvp/skills/_base.py`, `mvp/skills/manifest_schema.py`, `mvp/skills/registry.py`
- `mvp/engine/rule_executor.py`, `mvp/engine/citation_validator.py`
- `mvp/skills/fundamental/extract_canonical_statements/{skill.py,manifest.yaml}`
- `mvp/skills/fundamental/extract_mdna/{skill.py,manifest.yaml}`
- `mvp/skills/paper_derived/compute_beneish_m_score/{skill.py,manifest.yaml}`

**What did NOT land (Phase 4 remaining):**
- `mvp/skills/interpretation/interpret_m_score_components/{skill.py,manifest.yaml}`
- `mvp/skills/interpretation/interpret_z_score_components/{skill.py,manifest.yaml}`
- `mvp/skills/paper_derived/compute_altman_z_score/{skill.py,manifest.yaml,README.md}`
- `mvp/skills/paper_derived/compute_beneish_m_score/README.md` (manifest + skill landed, README didn't)
- `mvp/skills/composite/analyze_for_red_flags/{skill.py,manifest.yaml}`
- `mvp/cli/main.py` (minimal CLI for the demo)
- `mvp/scripts/phase4_demo.py` (the Enron live-demo script)
- `tests/unit/skills/*` and `tests/integration/{test_beneish_paper_replication,test_altman_paper_replication,test_enron_demo}.py` — NONE of the Phase-4 tests landed. Test collection is still at 237 (unchanged from Phase 3).
- `engine/llm_interpreter.py` was explicitly conditional in the prompt; its absence is spec-compliant (per P2 no-stub rule the prompt said "only create if fully exercised by a test; otherwise don't").
- `BUILD_STATE.json` and `BUILD_LOG.md` not updated by Phase 4 yet.

**Current quality state:** 237/237 tests still green; `python -W error -c "import ..."` clean on every shipped Phase-4 module; no broken imports. Safe to resume from here.

**When budget resets (10:00 UTC 2026-04-18, ~21 hours from this snapshot):**
Spawn a **Phase 4 continuation** subagent with a prompt that (i) reads this section, (ii) inventories the partial work above, (iii) picks up with `interpret_m_score_components` and continues through the remaining items, (iv) validates the three already-shipped manifests against `skills/manifest_schema.py`'s Pydantic validator — if ANY of them fails the final schema, the continuation agent must fix them, not ship around them. Do NOT re-ship the already-landed modules unless validation finds a defect. The continuation must end with the same Phase-4 acceptance criteria: live Enron demo producing both M+Z blocks, full MCP + OpenAI catalogs, all Phase-4 integration tests green.

---

## 2026-04-17 — Hermetic pytest gate (Phase 8 fixer)

**Problem.** On a fresh clone of the repo (before `mvp ingest filings --batch all` runs), `pytest tests/ -q` reported **39 failed, 341 passed**. The failures were real but expected: those 39 tests exercise the skill pipeline, engine, and CLI/API surfaces against live-ingested filings under `data/filings/`, which `.gitignore` excludes. This made the test suite unusable as a clean-clone onboarding gate — a new developer (or CI runner) couldn't tell "genuinely broken" from "just missing data" without triaging every failure.

**Fix (pragmatic marker split).** Added a `requires_live_data` pytest marker in `mvp/tests/conftest.py` plus a `pytest_collection_modifyitems` hook that auto-skips marked tests when the live corpus sentinel (`data/filings/0000320193/`) is absent. Applied the marker to the 39 failing tests:

- `tests/integration/test_cli_api_parity.py` — module-level `pytestmark` (7 of 7).
- `tests/integration/test_enron_demo.py` — module-level `pytestmark` (5 of 5).
- `tests/integration/test_eval_e2e.py` — per-function on 2 of 4.
- `tests/unit/api/test_server.py` — per-function on 3 of 11.
- `tests/unit/engine/test_citation_validator.py` — per-function on 2 of 5.
- `tests/unit/engine/test_rule_executor.py` — per-function on 4 of 6.
- `tests/unit/eval/test_citation_check.py` — per-function on 1 of 8.
- `tests/unit/skills/test_analyze_for_red_flags.py` — per-function on 3 of 5.
- `tests/unit/skills/test_compute_altman_z_score.py` — per-function on 6 of 7.
- `tests/unit/skills/test_interpret_m_score_components.py` — per-function on 3 of 5.
- `tests/unit/skills/test_interpret_z_score_components.py` — per-function on 3 of 4.

After the fix:
- **Full-venv** (with live data ingested): `380 passed` in ~90s.
- **Clean-clone** (no `data/filings/`): `341 passed, 39 skipped` in ~13s, exit 0.

README quickstart now calls out the clean-clone tally so a first-time reader doesn't mistake the skips for breakage.

**Follow-up (future workshop work — Option B).** The 25 unit tests in the marked set are only *pragmatically* hermetic — they're skipped instead of refactored. The ambitious cleanup is to replace their live-data reads with fabricated canonical-statement fixtures (a `tests/fixtures/` module producing a minimal `CanonicalStatements` object with the exact line items each test needs) so they run on any clone. Integration tests legitimately need live data and should keep the marker. This refactor is filed for a future workshop improvement ticket — it's not on the MVP critical path, and the current state is adequate for the `success_criteria.md` §1 top-line gates.
