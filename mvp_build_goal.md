# MVP Build Goal

This document defines **what we are building** for the MVP. Companion: `success_criteria.md` defines **how we know it worked**.

The MVP is a **vertical slice**: two paper-derived analytical skills (Beneish M-Score primary, Altman Z-Score parallel sibling) implemented end-to-end across all six layers (L0 → L5) of the architecture, on five representative US large-cap filings. The goal is to prove the *product shape* is correct before broadening the skill catalogue.

Throughout the MVP, the roles that would eventually be filled by domain experts (accounting PhD, quant-finance PhD, audit/compliance) are played by **Claude subagent personas**. Every artifact those personas produce is structured so a real human expert can later step into the same role with the same contract.

---

## 0. Operating principles (read first, apply throughout)

These three principles are load-bearing across every phase. Before writing any code, rule, or document, check it against all three. They take precedence over the more detailed sections that follow.

### P1 — Human verification and experience layers are disjoint from engineering layers

When real domain experts (accounting PhD, finance methodologist, audit reviewer) replace the LLM-subagent personas, **they must not need to write, read, or run Python**. Their contributions land in **declarative artifacts** under `mvp/human_layer/` and adjacent declarative trees:

- `mvp/human_layer/personas/<persona>.yaml` — persona prompt, model assignment, contract description. The runtime in `mvp/agents/` loads these; humans edit them directly.
- `mvp/rules/templates/*.yaml` — accounting-expert-authored rule templates.
- `mvp/eval/gold/**/*.yaml` — domain-expert-authored gold-standard cases.
- `mvp/agents/audit_log/` — sampled entries reviewed via the checklist in `human_layer/audit_review_guide.md`; comments flow back as edits to rule templates or gold sets, not as code changes.
- Skill manifests (`mvp/skills/**/manifest.yaml`) — reviewable line-by-line by a domain expert.

**Rule:** a change in the human layer must not require recompilation, code review, or engineering involvement. A change in the engineering layer must not require domain-expert review.

### P2 — Build-quality bar: don't over-engineer, don't be lazy

This is an MVP. Premature abstractions, framework wrappers around two-line operations, configuration knobs without callers, and microservice splits are **out**. Three similar lines is better than a premature abstraction. No backwards-compat shims for code we control.

At the same time, every shipped piece must be done to our best level:

- **No TODO placeholders.** No `pass` stub functions. No "we'll add tests later." No commented-out code.
- **No silent error-swallow.** Every error path is structured and documented.
- **No half-built scaffolding.** If a thing is in scope per this document, finish it. If it is out of scope, leave it out cleanly with no half-built remnant.
- **No "good enough for the demo" shortcuts.** The demo IS the product surface; treat it accordingly.

**不要怕麻烦.** The few extra hours spent doing a thing properly the first time are saved many times over in review and rework. When in doubt about scope, ask before guessing. When in doubt about quality, do the rigorous version.

### P3 — The user is an AI agent (design accordingly)

The end user is a human-operated personal AI agent, not a human directly invoking endpoints. The system surface must be **agent-native**, not human-first-with-an-API-bolted-on:

- **Skill discoverability.** Every skill manifest is loadable as an MCP tool spec **and** as an OpenAI tool-use spec. The registry exposes a `list_skills()` operation that returns the full agent-consumable catalog with descriptions a calling LLM can use to choose and construct calls.
- **Self-describing I/O.** Every input/output is JSON-Schema-typed with `description` fields written for LLM readers — verbose enough that an agent can correctly populate inputs without reading separate docs.
- **Structured errors, not exceptions.** Every failure mode returns a typed error object: `{error_code, error_category, human_message, retry_safe, suggested_remediation}`. No HTTP 500s with stack traces leaking to the agent.
- **Agent-actionable citations.** Every citation includes a stable `doc_id` and `locator` that the agent can resolve via a `resolve_citation` skill — no scraping, no fragile string matching.
- **CLI is a thin wrapper over the same registry the API uses.** Anything callable in one is callable in the other with byte-identical semantics. No CLI-only or API-only paths.
- **Determinism + cache-friendliness.** Identical inputs produce identical outputs (modulo run timestamps), so an agent can cache and trust skill responses across calls.
- **Composability over completeness.** Prefer many small skills the agent composes over one omnibus skill that does everything. The composite (`analyze_for_red_flags`) exists as an example of orchestration, not as a model for every future skill.

The business test for any design choice is: **would a personal AI agent acting on behalf of a non-expert human find this surface natural to use?** If not, redesign.

---

## 1. Scope

### In scope

- **Issuer universe:** US public companies. US GAAP only. SEC EDGAR as the canonical source.
- **Filing types:** 10-K (primary), 10-Q (secondary), 8-K (tertiary), earnings call transcripts (if obtainable in the MVP timeframe).
- **Initial coverage:** 5 large-cap issuers (rationale and selection in §4).
- **Skill catalogue at MVP:** one paper-derived skill (Beneish M-Score, see §3), plus the supporting fundamental, interpretation, and composite skills it depends on.
- **Two PDF substrates handled:** SEC filings (filing PDFs / iXBRL HTML) and academic research papers (the paper that the paper-derived skill comes from).
- **Cross-cutting layers:** evaluation harness, citation-integrity checking, versioning/provenance, observability stubs — all implemented with LLM-subagent personas standing in for human experts.

### Out of scope (deferred, do not build)

- Multi-jurisdiction (HK, A-shares, IFRS, CAS) — see CLAUDE.md "Established design decisions"
- Multi-domain skill library (corporate finance, quant finance, econ, OR, quant marketing) — long-term roadmap only
- Production-grade auth, multi-tenancy, billing, SLA — Stage 2 API is a stub at MVP
- Production database (Postgres etc.) — file-system + JSONL stores at MVP
- Restatement-aware versioning at full fidelity — record restatements but don't auto-rerun
- Real-time refresh / event bus — batch-only at MVP
- UI — CLI + JSON outputs only at MVP

---

## 2. Architectural restatement

Reference: `deep_research_report.md` §"Layered architecture" and `CLAUDE.md` §"Established design decisions". Brief recap so this file stands alone.

```
Cross-cutting:  Evaluation & gold-standard | Versioning & provenance | Governance | Observability
L5  Delivery surface   CLI + minimal FastAPI stub
L4  Skills library     Callable, versioned, manifest-driven endpoints
L3  Interpretation     (a) Rule set / ontology  (b) Interpretation engine
L2  Standardization    XBRL → canonical statements; period & restatement handling
L1  Document/fact store Immutable, hash-addressed
L0  Sources & ingestion SEC EDGAR + academic-paper fetch
```

The MVP implements **all six layers**, but each at the minimum thickness required for the vertical slice to work end-to-end.

---

## 3. The MVP vertical slice: Beneish M-Score

### Why this construct

We need a paper-derived skill that exercises every layer with the least amount of domain breadth. **Beneish (1999), "The Detection of Earnings Manipulation"** is the right MVP candidate because it:

- Is purely numeric (no NLP), so the eval surface is well-defined: the score is a single real number with a categorical threshold (M > -2.22 ⇒ flagged).
- Requires **two consecutive years** of financial-statement data — exercises temporal handling, restatement detection, and period alignment.
- Pulls from all three primary statements (income statement, balance sheet, cash flow) — exercises full standardization, not just one statement.
- Has eight named ratio components (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) — each component requires a non-trivial line-item mapping decision, exercising the rule set and judgment-template machinery.
- Is famous, well-replicated, and has known reference values on canonical cases (Enron, WorldCom). Gold-standard data is buildable.
- The original paper is publicly available (SSRN abstract 823405) and publishes both the model coefficients and the holdout-sample test results, so implementation faithfulness is verifiable.

### Parallel second slice: Altman Z-Score (1968)

Per resolved §13 decision 5, **Altman Z-Score is included at MVP** as a parallel second paper-derived skill. It does not extend the timeline materially because it shares all L0/L1/L2 infrastructure with M-Score and reuses the same 5 sample filings. Its purpose at MVP is to **demonstrate the multi-skill pattern**: two paper-derived skills coexisting in the registry, both manifest-driven, both orchestrated by a single composite (`analyze_for_red_flags`).

The original Altman (1968) Z-score is used (not the Z'-prime 1983 variant), to keep "paper-derived" honest — Z'-prime is published in a book, not a paper. Z requires market value of equity as an input; for the 5 sample issuers, market caps at fiscal year-end are pre-populated as a small fixture in `data/market_data/equity_values.yaml`. The Z'-prime variant is added as a follow-on in post-MVP scope.

### Source papers

- **Beneish, M. D. (1999).** "The Detection of Earnings Manipulation." *Financial Analysts Journal*, 55(5), 24–36. Store: `data/papers/beneish_1999.pdf` from a publicly mirrored copy, with manifest entry recording source URL, fetch date, sha256.
- **Altman, E. I. (1968).** "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy." *Journal of Finance*, 23(4), 589–609. Store: `data/papers/altman_1968.pdf` from a publicly mirrored copy, same manifest treatment.

---

## 4. Sample filings (the 5)

Selected to span the M-Score interpretation range and exercise edge cases:

| # | Issuer | Filing | Year | Why |
|---|---|---|---|---|
| 1 | Enron | 10-K | 2000 | Canonical positive case. Beneish himself cites it. M-Score should flag. |
| 2 | WorldCom | 10-K | 2001 | Second canonical positive case. Independent fraud pattern from Enron. |
| 3 | Apple | 10-K | 2023 | Clean blue-chip negative control. M-Score should not flag. |
| 4 | Microsoft | 10-K | 2023 | Second clean negative control; multi-segment, high cash flow. |
| 5 | Carvana | 10-K | 2022 | Ambiguous case: stressed working capital, complex revenue recognition, no fraud finding. Tests judgment-template behavior in the gray zone. |

This mix gives **2 positives, 2 negatives, 1 ambiguous**. It is the smallest set that lets us measure precision, recall, and gray-zone behavior simultaneously.

For each issuer, MVP ingests:
- The 10-K filing for the listed year
- The prior-year 10-K (M-Score requires t and t-1)
- Both filings' iXBRL facts (where available; for Enron/WorldCom, the iXBRL era predates these filings — must fall back to PDF text + manual standardization, exercising the fallback path)

The same 5-issuer set serves both M-Score and Altman Z evaluation. Altman Z does not require prior-year data, so for Z it is sufficient to score year t (using year t-1 data only as a sanity check on the score's stability). Market cap at fiscal year-end for each issuer is recorded in `data/market_data/equity_values.yaml` as an input fixture.

---

## 5. Repository structure

All code lives in `mvp/` under the project root. Modular, with each layer as its own package:

```
Proj_ongoing/
├── CLAUDE.md
├── deep_research_report.md
├── discussions.txt
├── openai_bioproject.txt
├── goal_driven.txt
├── mvp_build_goal.md          (this file)
├── success_criteria.md
├── workshop/                               # TEAM-INTERNAL — paper-onboarding playbook, research helpers, eval ops, maintenance. Never shipped to users. See §15.
│   ├── README.md                           # what workshop is; when to reach for it vs mvp/
│   ├── paper_to_skill/                     # hero workflow: given a paper PDF, ship a skill
│   │   ├── README.md                       # playbook (Beneish + Altman onboarded under it)
│   │   ├── extract_paper.py                # PDF → structured JSON (formulas, thresholds, reported numbers). Post-MVP.
│   │   ├── draft_manifest.py               # scaffold mvp/skills/<layer>/<id>/manifest.yaml from extraction. Post-MVP.
│   │   ├── replication_harness.py          # compare draft skill against paper's worked examples. Post-MVP.
│   │   └── templates/
│   │       ├── manifest_scaffold.yaml
│   │       └── rule_scaffold.yaml
│   ├── research/                           # ad-hoc scripts (EDGAR queries, peer-group scans, XBRL concept coverage audits)
│   │   └── README.md
│   ├── coverage/                           # tools for expanding the issuer/filing universe (new CIKs, new fiscal years)
│   │   └── README.md
│   ├── eval_ops/                           # eval harness extensions: backtests, regression diffs, calibration dashboards
│   │   └── README.md
│   ├── maintenance/                        # periodic upkeep: refresh_companyfacts.py, audit_log_sampler.py, rule_version_bump.py
│   │   └── README.md
│   └── docs/
│       ├── paper_onboarding_playbook.md    # lessons-learned from Phase 3–4 Beneish + Altman work
│       └── skill_design_checklist.md       # per-skill review checklist
└── mvp/
    ├── README.md
    ├── pyproject.toml
    ├── .env.example
    ├── data/                                # L0/L1: raw + immutable
    │   ├── filings/<cik>/<accession>/       # downloaded SEC filings
    │   ├── papers/<paper_id>.pdf            # research papers
    │   ├── market_data/
    │   │   └── equity_values.yaml           # fixture: fiscal-year-end market caps for sample issuers (Altman Z input)
    │   └── manifest.jsonl                   # immutable ingestion log
    ├── lib/                                 # cross-cutting utilities (NOT skills)
    │   ├── pdf_io.py                        # facade over pymupdf + pdf2zh.doclayout
    │   ├── edgar.py                         # SEC EDGAR client (rate-limited, UA declared)
    │   ├── xbrl.py                          # iXBRL parsing + taxonomy lookup
    │   ├── periods.py                       # date / fiscal-period normalization
    │   ├── hashing.py                       # passage / output content hashing
    │   ├── citation.py                      # Citation dataclass + provenance helpers
    │   └── llm.py                           # Anthropic SDK wrapper (caching, retries)
    ├── ingestion/                           # L0: pull raw inputs
    │   ├── filings_ingest.py
    │   └── papers_ingest.py
    ├── store/                               # L1: immutable doc/fact store
    │   ├── doc_store.py                     # CRUD on hash-addressed docs
    │   ├── facts_store.py                   # parsed XBRL facts
    │   └── schema.py
    ├── standardize/                         # L2: canonical statements
    │   ├── statements.py                    # canonical IS/BS/CF builder
    │   ├── mappings.py                      # XBRL concept → canonical line item
    │   └── restatements.py                  # restatement detection (logging-only at MVP)
    ├── rules/                               # L3(a): declarative knowledge
    │   ├── ontology.yaml                    # domain ontology
    │   ├── templates/
    │   │   └── m_score_components.yaml      # how each M-Score component is interpreted
    │   └── README.md                        # rule-authoring guide
    ├── engine/                              # L3(b): interpretation engine
    │   ├── rule_executor.py                 # apply declarative rules to L2 outputs
    │   ├── llm_interpreter.py               # constrained LLM extraction with citations
    │   └── citation_validator.py
    ├── skills/                              # L4: callable skill endpoints
    │   ├── manifest_schema.py               # SkillManifest dataclass + YAML loader
    │   ├── registry.py                      # discovery, dispatch, version routing
    │   ├── _base.py                         # Skill base class
    │   ├── fundamental/
    │   │   ├── extract_canonical_statements/
    │   │   │   ├── skill.py
    │   │   │   └── manifest.yaml
    │   │   └── extract_mdna/
    │   │       ├── skill.py
    │   │       └── manifest.yaml
    │   ├── interpretation/
    │   │   ├── interpret_m_score_components/
    │   │   │   ├── skill.py
    │   │   │   └── manifest.yaml
    │   │   └── interpret_z_score_components/
    │   │       ├── skill.py
    │   │       └── manifest.yaml
    │   ├── paper_derived/
    │   │   ├── compute_beneish_m_score/
    │   │   │   ├── skill.py
    │   │   │   ├── manifest.yaml
    │   │   │   └── README.md                # paper summary + implementation notes
    │   │   └── compute_altman_z_score/
    │   │       ├── skill.py
    │   │       ├── manifest.yaml
    │   │       └── README.md
    │   └── composite/
    │       └── analyze_for_red_flags/
    │           ├── skill.py
    │           └── manifest.yaml
    ├── agents/                              # ENGINEERING: persona runtime (loads YAML configs from human_layer/)
    │   ├── persona_runtime.py               # generic loader, dispatcher, audit logger
    │   ├── accounting_expert.py             # thin wrapper: loads config + calls runtime
    │   ├── quant_finance_methodologist.py
    │   ├── evaluation_agent.py
    │   ├── citation_auditor.py
    │   ├── audit_log/                       # generated audit log (write target; never edited by humans directly)
    │   └── README.md                        # engineering-internal: how the runtime works
    ├── human_layer/                         # DISJOINT FROM ENGINEERING — humans contribute here, no Python required
    │   ├── README.md                        # the seam — entry point for human contributors
    │   ├── personas/                        # YAML configs (prompt + model + contract) loaded by agents/ runtime
    │   │   ├── accounting_expert.yaml
    │   │   ├── quant_finance_methodologist.yaml
    │   │   ├── evaluation_agent.yaml
    │   │   └── citation_auditor.yaml
    │   ├── rule_authoring_guide.md          # how a human edits rules/templates/*.yaml
    │   ├── gold_authoring_guide.md          # how a human edits eval/gold/**/*.yaml
    │   └── audit_review_guide.md            # one-page checklist for reviewing audit_log/ entries
    ├── eval/                                # cross-cutting: evaluation harness
    │   ├── runner.py
    │   ├── citation_check.py
    │   └── gold/
    │       ├── beneish/
    │       │   ├── enron_2000.yaml
    │       │   ├── worldcom_2001.yaml
    │       │   ├── apple_2023.yaml
    │       │   ├── microsoft_2023.yaml
    │       │   └── carvana_2022.yaml
    │       └── altman/
    │           ├── enron_2000.yaml
    │           ├── worldcom_2001.yaml
    │           ├── apple_2023.yaml
    │           ├── microsoft_2023.yaml
    │           └── carvana_2022.yaml
    ├── api/                                 # L5: minimal FastAPI stub
    │   ├── server.py
    │   └── routes.py
    ├── cli/                                 # L5: CLI for human use
    │   └── main.py
    └── tests/
        ├── unit/
        └── integration/
```

**Modularity contract:** each layer's package depends only on layers strictly below it (or on `lib/`). No upward imports. No sibling imports across `skills/{fundamental,interpretation,paper_derived,composite}` — composite skills compose lower skills via the registry, not direct imports.

---

## 6. Skill manifest schema

Every skill ships with a `manifest.yaml`. This is the contract between the skill and its callers (human or agent), and the contract between the skill author and the maintenance/audit roles.

The user proposed a hypothesis-test-style flow (problem → methods → results → takeaways). I am keeping that as the **provenance** subsection of the manifest, and adding the operational metadata a callable, versioned, evaluable skill needs.

Schema (YAML):

```yaml
# --- Identity ---
skill_id: compute_beneish_m_score          # unique, snake_case, immutable
version: 0.1.0                              # semver
layer: paper_derived                        # fundamental | interpretation | paper_derived | composite
status: alpha                               # alpha | beta | ga | deprecated
maintainer_persona: quant_finance_methodologist  # which subagent role owns this

# --- Provenance (the hypothesis-test flow, expanded) ---
provenance:
  source_papers:
    - citation: "Beneish, M. D. (1999). The Detection of Earnings Manipulation. Financial Analysts Journal, 55(5), 24–36."
      doi_or_url: "https://www.jstor.org/stable/4480190"
      local_pdf: "data/papers/beneish_1999.pdf"
      pdf_sha256: "<hash>"
  study_scope:
    asset_class: "US public equities"
    time_period_in_paper: "1982–1992"
    sample_size_in_paper: "74 manipulators + 2,332 non-manipulators (Compustat)"
  problem:
    one_line: "Detect earnings manipulation using publicly available financial-statement data."
    long_form: "Predict the probability that a firm has manipulated reported earnings, using a probit model on eight financial-statement ratios computed from year t and year t-1."
  methodology:
    summary: "Compute eight ratios (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA), apply the published linear combination, compare to threshold."
    formulas_extracted_from_paper:
      M_score: "-4.84 + 0.92*DSRI + 0.528*GMI + 0.404*AQI + 0.892*SGI + 0.115*DEPI - 0.172*SGAI + 4.679*TATA - 0.327*LVGI"
      DSRI: "(Receivables_t / Sales_t) / (Receivables_{t-1} / Sales_{t-1})"
      # ... full formula table
    threshold: "M > -2.22 ⇒ flag as likely manipulator (paper's reported optimal cutoff)"
  expected_results:
    metric_kind: "scalar + categorical flag + 8 component scores"
    interpretation_guide: "Flagged firms have ~76% probability of being manipulators in Beneish's holdout sample."
  takeaways:
    - "Useful as a screening tool, not a verdict."
    - "Cutoff varies by industry and period; the -2.22 value is paper-specific."
    - "False-positive cases include firms with rapid legitimate growth; cross-check with industry context."
  use_cases:
    - "Earnings-quality red-flag screen during diligence"
    - "Quarterly earnings-season anomaly detection"
    - "Backtest input for accruals-quality factor"

# --- Implementation choices (where the paper has ambiguity) ---
implementation_decisions:
  - decision: "Receivables = trade receivables only, exclude other receivables"
    rationale: "Paper uses Compustat RECT; trade-only is the conservative interpretation"
    reviewer_persona: "accounting_expert"
  - decision: "When TATA can't be computed (cash-flow statement missing), skill returns null with reason='missing_cfo'"
    rationale: "Avoid silent imputation; surface the gap"
  # ... document every place where the paper is ambiguous and we made a call

# --- Inputs ---
inputs:
  type: object
  required: [cik, fiscal_year_end]
  properties:
    cik: {type: string, pattern: "^[0-9]{10}$"}
    fiscal_year_end: {type: string, format: date}
    use_restated_if_available: {type: boolean, default: false}

# --- Outputs ---
outputs:
  type: object
  required: [m_score, flag, components, citations, confidence]
  properties:
    m_score: {type: number}
    flag: {type: string, enum: [manipulator_likely, manipulator_unlikely, indeterminate]}
    components:
      type: object
      properties:
        DSRI: {type: number}
        GMI: {type: number}
        AQI: {type: number}
        SGI: {type: number}
        DEPI: {type: number}
        SGAI: {type: number}
        LVGI: {type: number}
        TATA: {type: number}
    citations:
      type: array
      items: {$ref: "#/$defs/Citation"}
    confidence: {$ref: "#/$defs/Confidence"}
    warnings: {type: array, items: {type: string}}

# --- Citation contract ---
citation_contract:
  required_per_field:
    "components.*": "every component must cite the source line items used in its computation"
    "m_score": "must cite at minimum sales_t, sales_{t-1}, total_assets_t"
  hash_algorithm: sha256
  locator_format: "filing_id::statement_role::line_item_name"

# --- Confidence model ---
confidence:
  computed_from:
    - "completeness of input data (penalty for any imputed line item)"
    - "data-quality flags from L2 (penalty for XBRL extension usage on input lines)"
    - "magnitude of any individual component (extreme component values reduce confidence)"
  calibration_status: "uncalibrated_at_mvp"   # set to 'calibrated' once gold-eval has 50+ samples

# --- Dependencies ---
dependencies:
  skills:
    - {skill_id: extract_canonical_statements, min_version: 0.1.0}
  lib:
    - mvp.lib.periods
    - mvp.lib.citation
  rules:
    - rules/templates/m_score_components.yaml

# --- Evaluation ---
evaluation:
  gold_standard_path: "eval/gold/beneish/"
  current_pass_rate: null    # populated by eval harness
  last_eval_run: null
  eval_metrics:
    - {name: m_score_within_0.10, target: ">= 0.95"}
    - {name: flag_match_rate, target: ">= 0.90"}
    - {name: citation_resolves, target: "= 1.00"}

# --- Limitations ---
limitations:
  - "Original paper sample is 1982–1992; coefficients may not generalize to post-IFRS-convergence US GAAP."
  - "Service-economy firms with low PP&E may produce noisy DEPI."
  - "Not a fraud verdict; classifier only."

# --- Examples ---
examples:
  - name: "Enron 2000 (positive case)"
    input: {cik: "0001024401", fiscal_year_end: "2000-12-31"}
    expected_flag: "manipulator_likely"
    expected_m_score_range: [-1.5, 1.0]
    notes: "Beneish (1999) and follow-up papers report Enron flagged on this filing."

# --- Cost ---
cost_estimate:
  llm_tokens_per_call: 0      # M-Score is purely arithmetic, no LLM at this skill
  external_api_calls: 0       # data assumed already in store
  typical_latency_ms: 50
```

This schema is the same for every skill. Fundamental skills will have empty `provenance.source_papers` (their provenance is the SEC taxonomy), and composite skills will have richer `dependencies` blocks.

A `skills/manifest_schema.py` module enforces the schema via Pydantic.

### Agent-accessibility (per Operating Principle P3)

Each manifest must additionally support:

- **`as_mcp_tool()`** — derive a Model Context Protocol tool spec from the manifest's identity, inputs, outputs. The registry exposes `GET /mcp/tools` that returns the full MCP catalog so a personal AI agent can register the skill set with one call.
- **`as_openai_tool()`** — derive an OpenAI-style `tools=[{type:"function", function:{...}}]` spec from the same manifest.
- **`description_for_llm`** — a 2–4 sentence string at the top of every manifest, written for an LLM caller (not for human docs). Answers: what does this skill do, what are typical inputs, what does the output look like, when *not* to call it. The LLM uses this to decide whether to invoke the skill at all.

The manifest is the single source of truth — the MCP spec, OpenAI spec, CLI help text, and OpenAPI doc are all generated from it. Never duplicate these by hand.

---

## 7. Skill layering — taxonomy and library design

The user asked for a clear answer on how to organize skills vs. a common library. The decomposition:

### Layer 0 — `lib/` (utilities, **not** skills)

Pure functions. Versioned with the codebase, not separately. Not exposed via the Skills API. Examples: PDF text extraction, XBRL concept lookup, hash-citation builder, Anthropic SDK wrapper. **Rule of thumb:** if it has no domain semantics and no judgment, it belongs in `lib/`.

### Layer 1 — Fundamental skills (`skills/fundamental/`)

Atomic extraction skills with a manifest. Take a filing, return structured canonical data. No interpretation; no judgment. Examples: `extract_canonical_statements`, `extract_mdna`, `extract_segment_table`, `extract_non_gaap_reconciliation`. **Rule of thumb:** these answer "what does the filing literally say?", not "what does it mean?"

### Layer 2 — Interpretation skills (`skills/interpretation/`)

Apply declarative judgment templates from `rules/templates/` to L1 outputs. Output structured findings with citations, flags, confidence. Examples: `assess_revenue_quality`, `interpret_m_score_components` (explains *why* a particular component is high/low for *this* company in plain language, citing specific line items). **Rule of thumb:** these answer "what does it mean?", grounded in the rule set.

### Layer 3 — Paper-derived skills (`skills/paper_derived/`)

Implement specific academic constructs faithfully. Each cites a specific paper. Examples: `compute_beneish_m_score`, `compute_altman_z_score`, `compute_modified_jones_accruals`, `compute_lm_tone`. **Rule of thumb:** if the methodology is published and citable, it goes here. The skill's manifest carries the full hypothesis-test provenance.

### Layer 4 — Composite skills (`skills/composite/`)

Orchestrate L1 + L2 + L3 skills into agent-friendly workflows. Examples: `analyze_for_earnings_manipulation` (calls extract → compute_m_score → interpret_components → produce narrative), `analyze_filing_bundle`, `peer_compare`. **Rule of thumb:** if it composes more than one lower skill and is what an end-user actually wants to call, it goes here.

### MVP skill set

The minimum set to ship the primary slice (M-Score) plus the parallel second slice (Altman Z):

| Layer | Skill | Purpose |
|---|---|---|
| L1 | `extract_canonical_statements` | parse iXBRL or PDF → IS/BS/CF for year t and t-1 (shared) |
| L1 | `extract_mdna` | extract MD&A section (used by L2 narrative interpretations) |
| L2 | `interpret_m_score_components` | per-component natural-language interpretation of M-Score, citing source line items |
| L2 | `interpret_z_score_components` | per-component natural-language interpretation of Altman Z, citing source line items |
| L3 | `compute_beneish_m_score` | paper-derived earnings-manipulation screen (Beneish 1999) |
| L3 | `compute_altman_z_score` | paper-derived distress-risk score (Altman 1968) |
| L4 | `analyze_for_red_flags` | composite that orchestrates both L3 skills + both L2 interpretations; returns a combined red-flag summary |

That is **7 skills total** at MVP. Anything more is scope creep. Adding a third paper-derived skill should be rejected until post-MVP.

---

## 8. Rule set design (`rules/`)

The rule set is **declarative knowledge**, separate from the engine that executes it.

### `rules/ontology.yaml`

Defines the domain vocabulary. Excerpt:

```yaml
domains:
  earnings_quality:
    description: "Assessment of how representative reported earnings are of sustainable economic earnings."
    sub_concepts: [accruals_quality, non_recurring_items, revenue_quality]
  accruals_quality:
    description: "Degree to which accruals reflect realized cash flows vs estimation/manipulation."
    related_constructs:
      - beneish_m_score
      - modified_jones_discretionary_accruals
      - sloan_accruals_anomaly
```

### `rules/templates/m_score_components.yaml` and `rules/templates/z_score_components.yaml`

Both authored by the `accounting_expert` subagent persona — one rule template per paper-derived skill. Each rule template is a declarative interpretation pattern:

```yaml
component: DSRI
description: "Days Sales in Receivables Index"
formula: "(Receivables_t / Sales_t) / (Receivables_{t-1} / Sales_{t-1})"
interpretation_rules:
  - condition: "value > 1.31"
    interpretation: "Receivables growing materially faster than sales — possible aggressive revenue recognition or collection issues."
    severity: "high"
    follow_up_questions:
      - "Has the company changed credit terms?"
      - "Is there a one-time customer contract inflating year-end receivables?"
    citations_required:
      - "trade_receivables_t in balance_sheet"
      - "trade_receivables_{t-1} in balance_sheet"
      - "revenue_t in income_statement"
      - "revenue_{t-1} in income_statement"
  - condition: "1.0 < value <= 1.31"
    interpretation: "Modest receivables growth above sales — within normal variation but worth noting."
    severity: "medium"
  # ... more conditions
```

Rules are versioned files, reviewable by an accounting expert (initially the subagent persona; later a real PhD).

---

## 9. Database / report management

Two stores, both file-system at MVP, both immutable-write:

### Filings store (`data/filings/<cik>/<accession>/`)

- Each ingestion fetches the filing once and stores: original file (PDF or HTML), parsed text (per-page), iXBRL facts (if available), and a `meta.json` recording `accession_number`, `filing_type`, `fiscal_period_end`, `filed_at`, `source_url`, `fetched_at`, `sha256`.
- Append-only. Never overwrite. New versions of same accession (rare; happens with amendments) get a `_amended_<n>` suffix.

### Papers store (`data/papers/`)

- One PDF per paper, named by stable ID: `beneish_1999.pdf`, `altman_1968.pdf`. `meta.json` per paper records citation, source URL, fetch date, sha256, plus a parsed `abstract.txt` and structured-extraction outputs (methodology section, formula list, results tables) produced by the `quant_finance_methodologist` subagent.

### Market data fixture (`data/market_data/equity_values.yaml`)

- Small hand-curated YAML mapping `(cik, fiscal_year_end)` → `market_value_of_equity_usd`, with citations to the public source used (e.g., CRSP / Yahoo Finance historical close × shares outstanding from the 10-K). Required input for `compute_altman_z_score`. Five entries at MVP, one per sample issuer.

### Manifest log (`data/manifest.jsonl`)

Append-only JSONL. One line per ingestion event. Enables full reproducibility ("regenerate the state of the data store as of date D"). Cross-cutting versioning hooks read this.

This design is intentionally minimal — the goal is not a database, it is a verifiable substrate. Promotion to Postgres / object storage is a post-MVP concern.

---

## 10. Cross-cutting subagent personas

Each persona is a Claude subagent with a frozen system prompt, a defined input/output contract, and a maintenance owner field on every artifact it produces. When a real human expert later replaces the persona, the contract stays the same.

**Disjoint-layer enforcement (per P1).** The persona's prompt, model assignment, and contract description live in `mvp/human_layer/personas/<persona>.yaml`. The Python file at `mvp/agents/<persona>.py` is a thin wrapper that loads the YAML config and delegates to `mvp/agents/persona_runtime.py`. **A human contributor can replace any persona by editing only its YAML — no Python changes, no rebuild.** Likewise, when a real PhD takes over the role, they edit the same YAML (or stop using it entirely and produce the YAML's downstream artifacts directly: rule templates, gold sets, audit comments).

### `agents/accounting_expert.py` (stands in for: Stern Accounting PhD)

- **Owns:** `rules/ontology.yaml`, `rules/templates/*.yaml`, all L2 interpretation skills, gold-standard labels for L1/L2.
- **Inputs:** filing text, standardized statements, draft interpretations from L2.
- **Outputs:** authored or reviewed rule templates, written interpretations, gold-standard labels.
- **Replacement contract:** a real accounting PhD takes the same inputs and writes the same artifacts. Persona prompt and example outputs serve as the role description.

### `agents/quant_finance_methodologist.py` (stands in for: quant-finance PhD)

- **Owns:** L3 paper-derived skill implementations, paper-extraction summaries (the populated provenance blocks), implementation-decision logs.
- **Inputs:** academic-paper PDF (parsed via `lib/pdf_io`).
- **Outputs:** populated skill manifest provenance blocks, working skill implementation, validation against paper's reported numbers.

### `agents/evaluation_agent.py` (stands in for: QA / eval engineer)

- **Owns:** the eval harness, eval runs, regression detection, confidence calibration data.
- **Inputs:** skill registry, gold-standard set, recent skill outputs.
- **Outputs:** pass-rate reports, regression alerts, calibration tables.

### `agents/citation_auditor.py` (stands in for: audit / compliance)

- **Owns:** citation-integrity checking, hash-chain verification, sampling audits.
- **Inputs:** skill outputs (any layer).
- **Outputs:** integrity reports, list of broken/missing citations, audit log entries.

A `agents/README.md` documents each persona's prompt, contract, and the path for human-expert replacement.

---

## 11. Tech stack

- **Language:** Python 3.11 (matches the existing `~/.python-version` in the parent research dir).
- **Package manager:** `uv` or pip + `pyproject.toml`. Use `uv` if available.
- **PDF I/O:** `pymupdf` (text extraction), `pdf2zh.doclayout.OnnxModel` (layout-aware region detection for academic papers). Both wrapped behind `lib/pdf_io.py`.
- **XBRL:** `python-xbrl` or `arelle` for iXBRL parsing; if too heavy, fall back to direct XML parsing of EDGAR's pre-extracted `companyfacts.zip`.
- **HTTP:** `httpx` with manual rate limiting (≤10 req/s for SEC, declared User-Agent).
- **LLM:** `anthropic` SDK. Subagent personas are prompts + tool-use loops, not separate processes.
  - `accounting_expert`, `quant_finance_methodologist`: `claude-opus-4-7` (depth + accuracy on judgment work)
  - `evaluation_agent`, `citation_auditor`: `claude-sonnet-4-6` (cost-managed for high-volume verification work)
- **Schema validation:** `pydantic` v2 for skill manifests, inputs, outputs.
- **API:** `fastapi` + `uvicorn` for the L5 stub.
- **Testing:** `pytest`. Property-based tests for arithmetic skills via `hypothesis` (M-Score arithmetic is well-suited).
- **Eval orchestration:** custom `eval/runner.py`, simple JSON output.

No database, no message queue, no Docker at MVP. File-system + JSONL.

---

## 12. Build sequence (phases)

Each phase is independently demoable. Do not start phase N+1 until phase N is demoed.

**Phase 0 — Bootstrap (1–2 sessions)**
- `mvp/` skeleton, `pyproject.toml`, `lib/llm.py`, `lib/pdf_io.py`, `lib/edgar.py` with rate-limit + UA.
- Demo: download Apple's most recent 10-K HTML and one page's worth of extracted text.

**Phase 1 — Ingestion (L0) for filings + papers**
- Implement `ingestion/filings_ingest.py`: pull all 5 issuers' 10-Ks (current + prior year). Persist to `data/filings/`.
- Implement `ingestion/papers_ingest.py`: download Beneish 1999 and Altman 1968. Persist to `data/papers/`.
- Hand-author `data/market_data/equity_values.yaml` with fiscal-year-end market caps for the 5 issuers, each entry citing the public source.
- Demo: `data/manifest.jsonl` shows 12 ingestion events (10 filings + 2 papers); files are present and hash-verifiable; market-data fixture validates against schema.

**Phase 2 — Doc/fact store (L1) + standardization (L2)**
- `store/doc_store.py`, `store/facts_store.py`.
- `standardize/statements.py` + `mappings.py`: produce canonical IS/BS/CF for each filing. Handle iXBRL where present, fall back to PDF-extracted tables for Enron/WorldCom.
- Demo: for each of the 10 filings, a canonical statement JSON file with line-item-level citations back to source.

**Phase 3 — Rule set authoring (L3a) by `accounting_expert` subagent**
- The subagent reads Beneish 1999 and Altman 1968 (via `quant_finance_methodologist` summaries) and authors both `rules/templates/m_score_components.yaml` and `rules/templates/z_score_components.yaml` with per-component interpretation rules.
- Demo: two human-readable YAML rule files, both reviewable as work an accounting expert would produce.

**Phase 4 — Engine + skills implementation (L3b + L4)**
- `engine/rule_executor.py`, `engine/citation_validator.py`.
- All 7 MVP skills implemented with manifests (2 fundamental, 2 interpretation, 2 paper-derived, 1 composite).
- Demo: CLI command `mvp run analyze_for_red_flags --cik 0001024401 --year 2000` produces a combined Beneish + Altman JSON for Enron, with per-component citations and natural-language interpretations.

**Phase 5 — Evaluation harness + gold standard**
- `evaluation_agent` subagent authors gold-standard YAML files for both M-Score and Altman Z (10 gold files total: 5 issuers × 2 paper-derived skills). Each file records expected score range, expected flag, and key citation expectations.
- `eval/runner.py` runs all skills against gold, produces pass-rate report.
- `eval/citation_check.py` verifies every output citation resolves.
- Demo: `mvp eval` produces a one-page report; ≥4 of 5 cases pass for **both** M-Score and Altman Z; any failure has an explainable cause.

**Phase 6 — API + CLI surface (L5)**
- `cli/main.py` with subcommands: `ingest`, `run`, `eval`, `audit`.
- `api/server.py` exposes one `/v1/skills/{skill_id}` endpoint.
- Demo: `curl` call returns the same output as CLI for the Enron case.

**Phase 7 — Documentation + reviewability + workshop skeleton**
- `mvp/README.md` with quickstart.
- Per-skill READMEs.
- `agents/README.md` with persona-replacement guide.
- `workshop/` skeleton bootstrapped per §15 and `success_criteria.md` §13:
  - `workshop/README.md` (one-page overview + subfolder index).
  - `workshop/paper_to_skill/README.md` (retrospective playbook from onboarding Beneish 1999 and Altman 1968 — documents how to read a paper, author the skill manifest's `provenance` block, author rule templates, author gold cases, and the replication bar a new skill must hit).
  - `workshop/docs/paper_onboarding_playbook.md` (expanded playbook with Phase 3–4 lessons-learned callouts — e.g., the Beneish -1.78 vs -2.22 threshold, the Altman X5 coefficient precision).
  - `workshop/docs/skill_design_checklist.md` (per-skill review checklist derived from the 7-skill MVP catalogue).
  - `workshop/{research,coverage,eval_ops,maintenance}/README.md` placeholders.
  - **No executable code required for the workshop skeleton at MVP** — scripts in `paper_to_skill/` land post-MVP when the second paper is onboarded.
- Demo: a fresh reader can run the Enron case end-to-end in <30 minutes from a clean clone.

---

## 13. Decisions (resolved)

The following are recorded as explicit, settled decisions. Re-opening any of them requires user direction.

| # | Decision | Resolution |
|---|---|---|
| 1 | Subagent model assignments | `accounting_expert` and `quant_finance_methodologist` use **`claude-opus-4-7`** (depth on judgment work); `evaluation_agent` and `citation_auditor` use **`claude-sonnet-4-6`** (cost-managed for high-volume checks). API key: `ANTHROPIC_API_KEY` env var, set by user. |
| 2 | SEC User-Agent string | **`"Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"`** — declared on every EDGAR request. |
| 3 | Pre-iXBRL filings (Enron 2000, WorldCom 2001) | Acceptable to use PDF/HTML extraction with manual standardization. Standardization quality for these two filings will be lower than for iXBRL-era filings; the standardization layer will tag them with `data_quality_flag: pre_ixbrl_pdf_extraction` so downstream confidence scores can degrade accordingly. |
| 4 | Beneish 1999 + Altman 1968 PDF sources | Acceptable to use publicly mirrored PDFs for MVP. Each paper's `meta.json` records the source URL, fetch date, sha256, and a `licensing_status: "mirrored_pending_review"` flag for later proper-licensing review. |
| 5 | Altman Z-Score as second paper-derived skill | **Included at MVP.** See §3 "Parallel second slice" for the rationale and §7 for the resulting 7-skill catalogue. Original Altman 1968 Z-score (not the Z'-prime 1983 book variant) is implemented to keep "paper-derived" honest; market caps for the 5 sample issuers are pre-populated as a fixture. |

---

## 14. Out of scope for MVP — explicit non-goals

- No transcript ingestion (8-K and earnings calls deferred unless they're trivial to add for the 5 issuers).
- No restatement re-running (we *log* restatements but don't auto-rerun upstream skills).
- No production-grade auth / multi-tenancy / billing on the API.
- No third paper-derived skill (LM tone, Modified Jones, Piotroski F, etc.) at MVP. Beneish + Altman are the two; further paper-derived skills are roadmap.
- No frontend / web UI.
- No real database — JSONL + filesystem only.
- No multi-jurisdiction support.
- No long-term skill domains (corp finance, quant finance, econ, OR, quant marketing) — these are roadmap.
- No human-in-the-loop UI for rule authoring — the subagent writes the YAML directly; human review is via reading the YAML.
- No Z'-prime variant of Altman (the 1983 book version that omits market cap). Original Z (1968) only at MVP.
- No executable `workshop/` tooling beyond READMEs. The `paper_to_skill/` scripts (`extract_paper.py`, `draft_manifest.py`, `replication_harness.py`) are post-MVP and will be written against the second paper. The MVP workshop deliverable is the *playbook* (docs) plus the subfolder skeleton — see §15 and `success_criteria.md` §13.

---

## 15. The `workshop/` sibling — team-internal tooling

`workshop/` is a **parallel, team-only codebase** that lives alongside `mvp/` but is never shipped to end users. Its purpose is to hold reusable functions, research helpers, playbooks, and maintenance scripts the founding team uses to run and grow the product over time.

### Distinction from `mvp/`
- `mvp/` is the **product surface** — user-callable skills, API, CLI, data contracts. Governed by the top-line gates in `success_criteria.md` §1.
- `workshop/` is **internal operations** — scripts and docs the founder/team uses when designing a new skill, onboarding a new paper, running a backtest, auditing rule versions. Governed by "does it save the next contributor time?"

### The hero workflow — `workshop/paper_to_skill/`
Every paper-derived skill added after MVP follows the same playbook: read the paper → extract formulas and thresholds → generate a skill-manifest scaffold → verify against the paper's worked examples → commit. `paper_to_skill/` is where that playbook lives:
- `extract_paper.py` (post-MVP) — PDF → structured JSON (the paper's formulas, coefficient tables, threshold values, worked examples). Uses `mvp.lib.pdf_io`; may call the `quant_finance_methodologist` persona via the shared runtime for semantic extraction.
- `draft_manifest.py` (post-MVP) — from the extraction, emits a populated `manifest.yaml` scaffold (identity, provenance, methodology, formulas, expected_results). Output drops into `mvp/skills/paper_derived/<skill_id>/manifest.yaml`; `implementation_decisions` is left for the engineer to fill.
- `replication_harness.py` (post-MVP) — runs the drafted skill against the paper's own reported worked-example firms (Beneish 1999's training sample; Altman 1968's Table 1 matched pairs). Flags any deviation > ±2% on components or beyond the paper's rounding on the final score.
- `templates/` (post-MVP) — YAML starting points for new manifests and new rule templates.

**At MVP, `paper_to_skill/` ships as README + directory only.** The README captures how Beneish and Altman were onboarded during Phase 3–4, so the workflow is documented in prose before it's documented in code.

### Other `workshop/` subfolders (skeleton at MVP, content grown post-MVP)
- `research/` — EDGAR ad-hoc queries, peer-group scans, XBRL concept-coverage audits.
- `coverage/` — issuer/filing-universe expansion (new CIKs, new fiscal years, new filing types).
- `eval_ops/` — eval harness extensions (backtests, regression diffs, calibration dashboards). Feeds `mvp/eval/` but lives outside the product boundary.
- `maintenance/` — periodic upkeep scripts: refreshing companyfacts caches, sampling audit-log entries for human review, bumping rule-template versions when a standard changes.
- `docs/` — the paper-onboarding playbook, skill-design checklist, any other internal-only playbooks.

### MVP-scope contract for `workshop/`
At MVP completion, `workshop/` must exist with:
1. `workshop/README.md` — one-page overview + subfolder index.
2. `workshop/paper_to_skill/README.md` — retrospective playbook from Phase 3–4.
3. `workshop/docs/paper_onboarding_playbook.md` — expanded playbook with lessons-learned.
4. `workshop/docs/skill_design_checklist.md` — per-skill review checklist.
5. `README.md` stubs in `research/`, `coverage/`, `eval_ops/`, `maintenance/` (each one paragraph).

Nothing else is required at MVP. `success_criteria.md` §13 formalizes this and makes clear it is non-blocking for the §1 top-line gates.

### Separation contract
- `workshop/` scripts MAY import from `mvp.lib` and MAY call `mvp/skills/` via the registry.
- `workshop/` scripts MUST NOT import from `mvp/skills/**/skill.py` or `mvp/engine/` directly — the registry is the seam.
- `mvp/` code MUST NOT import from `workshop/`. Workshop is strictly a consumer of mvp, never a dependency of it. Enforced by a simple grep-gate in CI (post-MVP) and by review at MVP.
- Quality gates in `success_criteria.md` §11 apply inside `mvp/` only. `workshop/` may carry experimental scripts, exploratory notebooks, and scratch files — the zero-TODO / full-test bar does not bind there, but the separation contract above is non-negotiable.

### Principle P1 applies here too
Anything a team member can do with a `workshop/` script should, once mature, not require writing Python — either the script runs as a CLI with YAML inputs, or its output is a YAML artifact a human reviewer can amend directly. `workshop/` scripts orchestrate `mvp/` skills; they do not duplicate skill logic.

### When to reach for workshop/ vs mvp/
| If you are… | Edit here |
|---|---|
| Adding a user-callable skill, endpoint, or data contract | `mvp/` |
| Adding a rule template, persona config, gold case | `mvp/` (declarative; no Python) |
| Onboarding a new paper (writing the playbook steps) | `workshop/paper_to_skill/` |
| Running a one-off backtest or coverage scan | `workshop/eval_ops/` or `workshop/coverage/` |
| Writing a script the team runs weekly to keep caches fresh | `workshop/maintenance/` |
| Documenting how the team does its own work | `workshop/docs/` |
