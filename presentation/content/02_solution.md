# 02 — Solution

**A machine-readable accounting interpretation service exposed as a skills API. Every call is typed, cited, deterministic, and authored under an expert-judgment contract that humans can review without reading code.**

## What we deliver

The product is a **library of callable skills** that turn a 10-K, a 10-Q, an 8-K, or a transcript into structured judgment objects. Today's MVP catalogue includes:

- Atomic extraction skills — `extract_canonical_statements`, `extract_mdna` — that return standardized financial statements and narrative sections with per-line-item citations.
- Paper-derived analytical skills — `compute_beneish_m_score`, `compute_altman_z_score`, plus five additional skills onboarded post-MVP from published accounting research (see §04 for the full catalogue).
- Interpretation skills that explain *why* a particular component is high or low for *this* filing in plain language, citing specific line items.
- Composite skills like `analyze_for_red_flags` that orchestrate the lower skills into one agent-friendly call.

Every skill is loadable as both an MCP tool spec and an OpenAI tool-use spec from a single manifest. CLI and API share one registry. Outputs are JSON with strict schemas. Errors are typed structured objects, not HTTP 500s.

## The two-stage thesis

We separate the product surface into two stages, deliberately:

**Stage 1 — precomputed, standardized, citation-grounded outputs** for a defined coverage universe (initially US large-cap). Output-only, schema-versioned. Buyers get the structured interpretation; they do not get the pipeline. Stage 1 is the Bloomberg-of-interpretations: scheduled, refreshed, queryable.

**Stage 2 — a black-box "skills API"** exposing intent-level capabilities (e.g. `revenue_quality_assessment`, `detect_accounting_policy_changes`) to agents. **No intermediate artifacts, no chain-of-thought, no pipeline-unit endpoints.** This is a deliberate moat-protection design choice: every agent gets the same callable contract; nobody gets to reverse-engineer our rule set, our gold corpus, or our judgment templates from the responses.

The MVP ships the Stage 2 surface end-to-end on a vertical slice (Beneish + Altman on five filings). Stage 1 broadens the same machinery to a coverage universe.

## Three operating principles, each a product guarantee

The MVP was built under three principles that are also the three things we tell buyers up front:

**P1 — The expert layer is disjoint from the engineering layer.** Domain experts (accounting PhDs, audit specialists) contribute through declarative YAML and markdown — persona configs, rule templates, gold cases, audit comments — and never need to read or write Python. Engineers ship code; experts ship judgment. Today's MVP enforces this with the `mvp/human_layer/` tree: every persona's prompt and model assignment lives in YAML, every interpretation rule is reviewable line-by-line. A real PhD can replace any subagent persona by editing one YAML file.

**P2 — Don't over-engineer, don't be lazy.** Premature abstractions, framework wrappers around two-line operations, and "demo-only" shortcuts are forbidden. So are TODOs, `pass` stubs, half-built modules, and silent error-swallow. Quality is enforced by gates the build itself ran against: zero TODO, zero bare-except, no abstraction without two callers, every shipped function tested or integration-exercised. The MVP shipped at 550 passing tests with all six final gates green.

**P3 — The user is an AI agent.** Every skill manifest is loadable as an MCP tool spec **and** an OpenAI tool-use spec. Every input/output is JSON-Schema-typed with `description_for_llm` fields written for an LLM reader. Errors are always typed `{error_code, error_category, human_message, retry_safe, suggested_remediation}` objects. CLI and API share one registry; no separate code paths. The "natural-agent test" — a cold Claude given only the tool catalog solves the Enron question without hand-holding — is our definitive acceptance gate, and it passes.

These three principles are not aspirational. They are checks the MVP ran against; failures of any one would have blocked release. They are the pitch as much as they are the engineering discipline.

## What the product is *not*

- Not a buy/sell signal engine. The skills surface judgment, not alpha.
- Not a chatbot. The user is an agent, not a human typing into a textbox.
- Not a substitute for a CFA or an auditor. The skills compress and standardize the interpretation work; the human still owns the conclusion.
- Not a terminal replacement. Bloomberg sells the seat; we sell the structured judgment that flows under the seat.

The wedge is narrow on purpose. Audit-grade accounting interpretation is a single category we can dominate before extending to corporate finance, quant finance, economics, and beyond.
