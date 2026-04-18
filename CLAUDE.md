# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this directory is

`Proj_ongoing/` is a **strategy / research workspace that now also contains a working Python codebase**. The strategy docs (at the repo root) are the thesis; the working code lives under `mvp/`; team-internal tooling lives under `workshop/`.

Current contents:
- `deep_research_report.md` — the canonical whitepaper covering product thesis, competitive landscape, TAM/SAM/SOM, layered architecture, evaluation as the trust backbone, MVP scope, and long-term skill-library breadth. The strategic / positioning source-of-truth.
- `mvp_build_goal.md` — **operational source-of-truth for what we are building.** Defines MVP scope, the vertical slice (Beneish M-Score + Altman Z-Score on 5 US large-cap filings), the layered repo structure under `mvp/`, the 7-skill MVP catalogue, the skill manifest schema, the rule-set design, the four subagent personas, the 7-phase build sequence, and (§15) the `workshop/` sibling.
- `success_criteria.md` — **operational source-of-truth for "done."** Defines the 5 top-line gates, per-layer DoD, negative gates, eval pass-rate targets for both M-Score and Altman Z, the 30-minute "demo morning" walkthrough, and (§13) the `workshop/` skeleton contract.
- `goal_driven.txt` — the goal-driven master/subagent system template. Wires `mvp_build_goal.md` (Goal) and `success_criteria.md` (Criteria for success) into a self-perpetuating subagent loop. Read first when orienting to active build work.
- `discussions.txt` — informal brainstorm log (chat-style notes in mixed Chinese/English). Source of in-flight design ideas that haven't yet been promoted into the main report.
- `openai_bioproject.txt` — reference material on OpenAI's GPT-Rosalind launch: a domain-specific frontier reasoning model for life sciences, paired with a Codex "Life Sciences Research Plugin" exposing 50+ public databases and biology tools as modular skills. Architecturally analogous to this project's Stage 1 + Stage 2 thesis; cite it as the closest public validation of the "domain reasoning model + skill orchestration" pattern.
- `paper_examples/` — 5 accounting / finance paper PDFs (one from J of Accounting Research 2024, one from Review of Accounting Studies 2025, two SSRN working papers, and a fundamentals text) queued as the **post-MVP practice corpus** for the `workshop/paper_to_skill/` playbook. Task #10 applies the playbook to each in sequence; the dual-growth directive (SPEC_UPDATES.md) requires each paper grow both `mvp/` (one new skill minimum) and `workshop/` (one playbook callout + one scripted improvement minimum).

`mvp/` **now exists** and holds the full vertical slice: 7 registered skills (2 fundamental, 2 interpretation, 2 paper-derived, 1 composite), the 4-persona runtime + YAML configs, the `rule_executor` + `citation_validator` engine, the 10-gold-case eval harness, the FastAPI stub (9 routes), the argparse CLI (12 subcommands), and 380 passing tests. See `mvp/README.md` for the 30-minute quickstart, `mvp/BUILD_LOG.md` for the per-phase history, and `mvp/SPEC_UPDATES.md` for late-breaking spec changes that override the originally-drafted phase prompts. The MVP's top-line gates (`success_criteria.md` §1) are verified by the master-agent loop post-Phase-7; "Phase 7 subagent reported done" is **not** the same as "MVP is done."

`workshop/` **also now exists** as a skeleton per `mvp_build_goal.md` §15 and `success_criteria.md` §13: `workshop/README.md`, the `paper_to_skill/README.md` retrospective playbook, `docs/paper_onboarding_playbook.md` + `docs/skill_design_checklist.md`, and one-paragraph READMEs under `research/`, `coverage/`, `eval_ops/`, and `maintenance/`. Executable tooling (`paper_to_skill/extract_paper.py`, `draft_manifest.py`, `replication_harness.py`) lands **post-MVP**, incrementally, during the `paper_examples/` workstream — paper 1 creates rough first versions; paper 5's onboarding should feel visibly faster because the workshop tooling matured along the way. `workshop/` is strictly a consumer of `mvp/` — never a dependency of it. `grep -R "from workshop" mvp/` must always print nothing.

The two configured working directories (`/mnt/nvme2/iv/research/Proj_ongoing` and `/home/iv/research/Proj_ongoing`) resolve to the same inode — they are the same directory. Edit either path; don't duplicate files between them.

Build / lint / test commands now exist for `mvp/` — see `mvp/README.md`. The canonical invocations are `.venv/bin/pytest -q` (380 tests), `.venv/bin/python -m mvp.cli.main eval` (the §4.2 gate line), and `.venv/bin/python -m mvp.cli.main run analyze_for_red_flags --cik 0001024401 --year 2000-12-31` (the Enron canonical demo). `workshop/` has no test suite at MVP and is exempt from the `mvp/` quality gates per §13.4.

## Operating principles (P1 / P2 / P3 — load-bearing)

Full detail in `mvp_build_goal.md` §0; enforced by `success_criteria.md` §11 (P2) and §12 (P3). **These three take precedence over any detail elsewhere — when they conflict, the principles win.**

- **P1 — Human-layer and engineering-layer are disjoint.** Domain experts contribute through declarative YAML/markdown artifacts under `mvp/human_layer/` (persona configs), `mvp/rules/templates/` (rule sets), `mvp/eval/gold/` (gold cases), and audit-log comments. They must never need to write, read, or run Python. Conversely, engineering changes must never require domain-expert sign-off. Every persona's prompt + model assignment lives in YAML (`mvp/human_layer/personas/*.yaml`), not in Python.
- **P2 — No over-engineering, no laziness.** Premature abstractions, config knobs without callers, and framework-for-three-lines-of-logic are forbidden. Equally forbidden: TODOs, `pass` stubs, half-built modules, silent error-swallow, "demo-only" shortcuts. **不要怕麻烦** — do each shipped piece to our best level the first time. Enforced by `success_criteria.md` §11 build-quality gates (zero TODO, zero bare-except, no abstraction without two callers, every function tested or integration-exercised).
- **P3 — The user is an AI agent.** Every skill manifest is loadable as an MCP tool spec **and** an OpenAI tool-use spec. Every input/output is JSON-Schema-typed with `description` fields written for an LLM reader. Errors are always typed `{error_code, error_category, human_message, retry_safe, suggested_remediation}` objects — never raw exceptions or HTTP 500s. CLI and API share one registry; no separate code paths. The "natural-agent test" (a cold Claude/GPT given only the tool catalog solves the Enron question without hand-holding) is the definitive agent-accessibility gate per §12.

When in doubt about a design choice: **would a personal AI agent, acting on behalf of a non-expert human, find this surface natural to use?** If not, redesign before shipping.

## Subject matter (orientation)

The project is a startup concept for a **machine-readable accounting interpretation service** — a "professional-grade interpretation layer" over public-company disclosures (10-K/10-Q/8-K, transcripts, XBRL), positioned distinct from terminals (S&P CIQ, LSEG, FactSet) and AI search (AlphaSense, BamSEC).

Two-stage product thesis — keep this distinction sharp in any edits:
- **Stage 1** — precomputed, standardized, citation-grounded interpretation outputs for a defined coverage universe (initially large-cap US). Output-only, schema-versioned.
- **Stage 2** — a black-box "skills API" exposing intent-level capabilities (e.g. `revenue_quality_assessment`, `detect_accounting_policy_changes`) to agents. **No intermediate artifacts, no chain-of-thought, no pipeline-unit endpoints** — this is a deliberate moat-protection design choice, not an oversight. Don't propose endpoints that expose internals.

Recurring non-negotiables in the design — preserve these when editing:
- **Citation/provenance on every claim** (doc_id, section, locator, excerpt_hash). XBRL data-quality issues are a documented risk; provenance-first is the trust mechanism.
- **Versioned ontology + judgment templates** authored by an accounting expert (Stern Accounting PhD), governed like code.
- **Restatement-aware versioning** of outputs.
- Standards anchoring: US GAAP / IFRS. GAAP taxonomy is royalty-free; FASB Codification text is not — don't propose reproducing copyrighted standard-setter text.
- SEC fair-access constraints: ≤10 req/s, declared User-Agent, prefer bulk archives.

Active next workstream: **build the MVP vertical slice** per `mvp_build_goal.md` and `success_criteria.md`. Planning is locked; execution starts from `mvp_build_goal.md` §12 (7-phase build sequence). The rule-set work and the engine are both part of this MVP (§11 Tech stack and §7 MVP skill catalogue).

The MVP is the Beneish M-Score + Altman Z-Score vertical slice on 5 US large-cap filings, with 4 LLM-subagent personas standing in for human domain experts. All new build work should trace to a section of `mvp_build_goal.md` and advance a gate in `success_criteria.md`. Do not build things that don't. See `goal_driven.txt` for the compact decision ledger.

## Established design decisions

These are settled and load-bearing. Don't relitigate without explicit user direction.

- **MVP scope: US public companies only.** Multi-jurisdiction (HK, A-shares, IFRS, CAS) is explicitly out of MVP scope and deferred to year 2+. Pick US GAAP / SEC EDGAR as the single substrate; this decision cascades into every layer (taxonomy, parsing, ontology authoring).
- **Vertical-slice MVP, not horizontal coverage.** Build L0 → L4 end-to-end on **one** analytical construct (one paper-derived skill, ~5 large-cap filings) before broadening. Don't pre-build a wide skill catalogue.
- **Sellable layers are L3 (interpretation) and L4 (skills API).** L0–L2 are infrastructure, not separately monetized. Don't propose pricing or positioning for the lower layers.
- **Evaluation/QA is a first-class layer, not a checkbox.** Gold-standard corpus + continuous eval + citation-integrity checks + confidence calibration are the moat. Treat as the most expensive long-term investment, not a Phase 2 nice-to-have.
- **Skill library breadth — long-term roadmap, not MVP.** Beyond accounting/finance, the skills library can eventually absorb constructs from corporate finance, quantitative finance, economics, operations research, and quantitative marketing papers. Keep this in long-term scope; do not let it pull MVP scope.
- **Knowledge / engine separation in the interpretation layer.** Rule set / ontology (declarative, expert-authored, expert-velocity iteration) is distinct from the interpretation engine (code, engineering-velocity releases). Don't conflate them in any architectural proposal.
- **Layered architecture (internal view).** Six layers — L0 sources & ingestion, L1 immutable doc/fact store, L2 standardization, L3 interpretation (rule set + engine), L4 skills library, L5 delivery surface — plus four cross-cutting concerns (evaluation, versioning/provenance, governance/IP, observability/metering). The three-layer view ("data → interpretation → skills") is retained for external positioning only.
- **OpenAI GPT-Rosalind is the closest public reference architecture** (domain-specific frontier reasoning model + orchestration plugin + modular skills calling 50+ tools). It validates the "domain reasoning + skills orchestration" shape but is not a competitor in domain. The wedge here remains *expert judgment + citation provenance*, which a generic foundation-lab plugin won't replicate.

## Document conventions in `deep_research_report.md`

The report appears to have been produced by a deep-research tool and contains non-standard inline markup that must be preserved on edits:

- `citeturn<N>search<M>` / `citeturn<N>view<M>` — citation reference tokens. Don't reformat, don't strip, don't merge.
- `entity["type","name","description"]` — structured entity annotations inside table cells (e.g. competitor rows). Preserve the exact bracket/quote form.
- `image_group{...}` JSON blocks — image-render directives. Leave intact.
- ` ```mermaid ` diagrams (architecture flowchart, roadmap timeline) — keep as fenced mermaid blocks; don't convert to images or prose.
- Pricing/coverage figures and dates are anchored to specific citations — when changing a number, update or add the corresponding `citeturn` reference; don't leave numbers without provenance.

Tables use Markdown pipe syntax with right-aligned numeric columns (`---:`). Match existing alignment when adding rows.

## When editing or extending the report

- The report's voice is analytical and hedged ("likely," "illustrative," "assumption"). Match it; avoid promotional or absolute claims.
- TAM/SAM/SOM, pricing tiers, and revenue scenarios are explicitly labeled as illustrative with stated assumptions — keep assumptions explicit when revising.
- New skills added to the Stage 2 list should follow the existing schema convention: `result_version`, `as_of`, `inputs`, `outputs`, `citations`, `confidence`, `warnings`.
- For substantive structural changes (reordering sections, dropping the Stage 1/Stage 2 framing, removing the citation requirement), confirm with the user first — these are load-bearing thesis choices, not stylistic.
