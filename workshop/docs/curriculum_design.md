# Curriculum design — foundational layer

This document describes the foundational layer of the IvorySquare skill
graph: the basics-first curriculum that sits *below* the paper-derived
skills (Beneish M-Score, Altman Z, Bernard 2025 readability, etc.) and
covers the textbook material a finance/accounting/OR student would
learn before reading research papers.

## Layer taxonomy

```
                          ┌──────────────────────────┐
                          │ L4 composite skills      │   analyze_for_red_flags
                          └──────────────────────────┘
                                       ▲
                          ┌──────────────────────────┐
                          │ L3 paper_derived skills  │   compute_beneish_m_score
                          │     +  interpretation    │   compute_altman_z_score
                          │     +  fundamental       │   …11 total at MVP+post-MVP
                          └──────────────────────────┘
                                       ▲
                          ┌──────────────────────────┐
                          │ L2 foundational skills   │   ← this document
                          │  (textbook subsections)  │
                          └──────────────────────────┘
```

Foundational skills are subsection-granular, e.g. `cfa_l1_fsa` chapter 5
section 2 subsection `accrual_quality_basics`. Each is one concept, one
question bank, optionally one deterministic code reference. The granularity
is intentional: paper-derived skills cite the foundational skills they
depend on, and the resulting graph mirrors how a domain expert
actually learns the material.

## Subsection-level granularity rule

A subsection is the smallest unit at which a textbook author has chosen
to draw a conceptual boundary. Going coarser (per-section) merges
unrelated concepts into one node; going finer (per-paragraph) shatters
the graph into noise. Subsection granularity yields ~50–200 nodes per
textbook, which matches the size of an undergraduate course's
problem-set glossary.

Concretely:

- **Finance/Accounting branch.** CFA Level 1 (FSA, Equity, Corporate
  Issuers) plus a CPA FAR review outline. Subsections inherit the
  CFA-LOS / CPA-blueprint numbering.
- **Operations Research branch.** Bertsimas & Tsitsiklis *Introduction
  to Linear Optimization*; Boyd & Vandenberghe *Convex Optimization*;
  Ross *Stochastic Processes*; Ross *A First Course in Probability*.
  Subsections inherit each book's chapter–section numbering.

Verbatim textbook content does NOT enter the repository. Only TOC
structure plus IvorySquare-authored summaries (≤ 2 sentences per
subsection) — the licensing baseline matches OpenStax-style
textbook-summary projects.

## The two-dimensional filter

Every candidate subsection runs through `mvp.curriculum.llm_baseline`:

1. Generate or load a `question_bank.yaml` with 10–25 textbook-style
   questions and expected answers.
2. Run a bare LLM (`claude-haiku-4-5` by default) `N=10` trials per
   question with **no foundational-skill context** — i.e., measure what
   the bare LLM already knows.
3. Score each trial against the expected answer. Tag each failure with
   one of:
   - `qualitative_correct` — answer is qualitatively right but doesn't
     hit the exact target string.
   - `partial_correct` — answer is close but missing a key part.
   - `computational_off_by_arithmetic` — numeric answer is in the right
     order of magnitude but outside tolerance.
   - `unit_or_dimension_error` — numeric answer is off by a unit
     conversion factor (or a dimensional confusion).
   - `structural_misunderstanding` — answer reflects a wrong concept
     entirely.
4. Apply the filter rule below.

The filter is **two-dimensional** because pass rate alone is misleading.
A subsection where the bare LLM is right 88% of the time looks "mostly
fine" until you notice the 12% failure tag is
`computational_off_by_arithmetic` on a Black-Scholes call — i.e., one in
eight calls produces a silently wrong number that an unsuspecting
downstream consumer treats as authoritative. The fix is not better
prompts; the fix is a deterministic code reference.

### The rule

| pass rate            | failure mode                          | content kind             | decision                |
|----------------------|---------------------------------------|--------------------------|-------------------------|
| > 0.95               | benign only (qualitative/partial)     | any                      | **drop**                |
| ∈ [0.85, 0.95]       | benign or non-benign                  | conceptual               | keep markdown-only      |
| ∈ [0.85, 0.95]       | benign or non-benign                  | computational / mixed    | keep code-backed        |
| < 0.85               | any                                   | any                      | keep code-backed        |
| any                  | any                                   | closed-form numerical    | keep code-backed        |

The closed-form-numerical override is the load-bearing piece. Black-
Scholes pricing, simplex pivots, NPV/IRR, ratio analyses, KKT residual
checks: these are all closed-form deterministic computations where any
non-zero failure rate is unacceptable downstream. They materialize as
code-backed skills regardless of bare-LLM pass rate, with
`materialization_reason: closed_form_determinism` in the manifest.

### Why 0.85 and 0.95?

These are starting-point thresholds, not derived constants. They map to
the intuition that:

- Above 0.95, the bare LLM is "reliably correct" and a foundational
  skill adds little surface — the LLM already knows the material as
  well as the textbook chapter would teach it.
- Between 0.85 and 0.95, the LLM is "mostly correct" — useful enough
  that paraphrased markdown content is the right artifact, since the
  failure tail is small and the marginal cost of code-backed
  determinism isn't worth it for purely conceptual material.
- Below 0.85, the LLM is "unreliable" — code-backed determinism is the
  right answer regardless of content kind, because the LLM-only path
  exposes the caller to a > 15% chance of being silently wrong.

The thresholds are tunable. Each materialization run logs both the
pass-rate distribution and the failure-mode taxonomy, so re-tuning is a
recompile of the filter, not a re-author of the curriculum.

## Materialization reasons (manifest field)

Every materialized foundational skill carries one of:

- `llm_fails` — pass rate < 0.85 OR non-benign failures dominate.
- `closed_form_determinism` — closed-form numerical computation;
  deterministic code reference is required regardless of pass rate.
- `conceptual_high_value` — pass rate ∈ [0.85, 0.95] AND content is
  conceptual; markdown-only surface adds value.

Every batch of new foundational skills targets at least one node of
each kind so the rationale is visible, not just stated.

## Closed-form determinism rationale

> An 88% pass rate on a Black-Scholes calculation still means 12% of
> calls produce silently wrong numbers — code makes it deterministic.

The economics:

- **LLM-only path:** caller asks the agent "price this European call,
  K = 100, T = 0.5, σ = 0.20, r = 0.03, S = 105." The bare LLM produces
  a number; in 12% of calls that number is wrong by an order-of-magnitude
  arithmetic mistake (squared σ vs. σ, missing discount factor, etc.).
  The caller has no easy way to detect the failure short of running an
  independent reference computation. In a multi-call agent loop, the
  per-call failure rate compounds.
- **Code-backed path:** the foundational skill exposes a deterministic
  Python function that computes the price closed-form. The LLM's role
  is only to *recognize* that "this is a Black-Scholes call" and select
  the skill, not to do the arithmetic. Recognition is a high-pass-rate
  task even for haiku; arithmetic is the low-pass-rate task that code
  removes.

The same reasoning applies to simplex pivots, NPV/IRR, ratio analyses,
LP feasibility checks, and other closed-form numerical computations
across the OR and finance branches. Conceptual material (definitions,
theorem statements, intuition) does not need code; computation does.

## TOC-only-no-verbatim policy

The repository ingests **structure**, not **text**. For each book:

- TOC YAML records `chapter` / `section` / `subsection` numbering and
  `title`. Verbatim textbook content stays in the textbook.
- The IvorySquare-authored `summary` field is ≤ 2 sentences,
  paraphrased, and IvorySquare-original.
- `concept.md` for each materialized subsection is IvorySquare-authored
  paraphrase + IvorySquare-original examples (often constructed from
  publicly available data sources: SEC filings, public market data,
  textbook problem-style synthetic numbers).
- `eval/question_bank.yaml` questions are IvorySquare-authored, not
  copied from textbook problem sets.

This matches the licensing baseline the project already commits to for
GAAP / FASB content: ingest taxonomy, do not reproduce copyrighted
text.

## Relation to paper-derived skills

A paper-derived skill (e.g. `compute_beneish_m_score`) usually depends
on several foundational skills:

- The accrual-quality concept (CFA L1 FSA §5.2).
- The income-statement structure (CFA L1 FSA §2.1).
- The balance-sheet structure (CFA L1 FSA §3.1).
- Probit-model intuition (Ross probability §10.3 — when materialized).

These dependencies are recorded in the paper-derived skill's
`prereqs.yaml` (a future extension; the paper-derived layer's existing
`dependencies.skills` field will accept foundational skill_ids as soon
as the registry permits). For now, the foundational layer is a
parallel sub-tree under `mvp/skills/foundational/`; the paper-derived
layer continues to function unchanged.

## CLI

The `mvp curriculum` subcommands let the curriculum builder operate the
filter without writing Python:

- `mvp curriculum ingest <book_id> <toc_path>` — load a TOC YAML.
- `mvp curriculum filter <node_id>` — run the bare-LLM filter and
  return a decision + reasoning.
- `mvp curriculum materialize <node_id>` — create the skill files for a
  surviving node.
- `mvp curriculum graph` — render the DAG to dot/svg.

## What ships in the first batch

Initial 10–30 materialized nodes, balanced across:

- All three `materialization_reason` values represented.
- Both branches (finance/accounting + OR) represented.
- All four target books in the OR branch represented in the TOC ingestion
  pass even when materialization is sparse.

The cap is intentional. The TOC ingestion produces hundreds of candidate
nodes; the filter is the constraint that keeps the layer's signal-to-noise
high.
