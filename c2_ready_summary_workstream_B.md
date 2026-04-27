# IvorySquare — foundational curriculum layer (C2-ready summary)

IvorySquare's skill graph is anchored at the bottom by a **foundational
layer** of textbook-subsection-granular concept skills, sitting below
the paper-derived skills (Beneish M-Score, Altman Z-Score, the
readability/complexity family from the post-MVP paper queue) and above
the layered data and standardization stack. Two branches — finance /
accounting (CFA Level 1 FSA / Equity / Corporate Issuers and a CPA FAR
review outline) and operations research (Bertsimas & Tsitsiklis on
linear optimization, Boyd & Vandenberghe on convex optimization, Ross
on stochastic processes, and Ross on probability) — populate a YAML-
backed prerequisite DAG with ninety-five candidate subsection nodes and
the textbook-ordering plus cross-reference edges that connect them.
The graph is queryable through the `mvp curriculum` CLI surface
(`ingest`, `filter`, `materialize`, `graph`) and renders to Graphviz
DOT or SVG; node identifiers preserve `<branch>/<book_id>/chXX__YY__sub`
shape so prerequisite chains remain readable in both the curriculum
audit log and the materialized skill tree.

A two-dimensional bare-LLM filter governs which candidate nodes earn
materialized skills. Each subsection's question bank runs N=10 trials
per question through `claude-haiku-4-5` and records both the pass rate
and the failure-mode taxonomy (`qualitative_correct`,
`computational_off_by_arithmetic`, `structural_misunderstanding`,
`unit_or_dimension_error`, `partial_correct`); subsections are
**dropped** when pass rate exceeds 0.95 with only benign failures,
**kept markdown-only** with reason `conceptual_high_value` when the
pass rate sits in the [0.85, 0.95] band on conceptual content, and
**kept code-backed** with reason `closed_form_determinism` whenever the
content is closed-form numerical (Black-Scholes pricing, simplex
pivots, NPV/IRR, ratio analyses, KKT residual checks) regardless of
pass rate, because an 88% pass rate on a deterministic computation
still leaves 12% silently wrong calls that downstream consumers would
treat as authoritative. Thirty subsection skills are now materialized
across both branches — twenty-one `closed_form_determinism` skills
(each shipping a `code/` reference implementation), seven
`llm_fails` skills (markdown-driven concept content where the bare
LLM's pass rate falls below the 0.85 floor), and two
`conceptual_high_value` markdown-only skills — every manifest
validates against the strict `SkillManifest` schema, every code
reference compiles cleanly, and every node carries the bare-LLM
pass-rate snapshot plus failure-mode taxonomy alongside the curated
`concept.md` content. Verbatim textbook content is excluded by policy:
only TOC structure, IvorySquare-authored paraphrases, and IvorySquare-
original worked examples ship in the repository.
