"""Curriculum module — foundational skill DAG, TOC ingestion, and bare-LLM filtering.

The curriculum module defines the foundational layer of the IvorySquare skill
graph: textbook-subsection-granular concept skills that sit *below* the
paper-derived skills, covering the basics a finance/accounting/OR student
learns before reading research papers.

Sub-modules
-----------
- :mod:`mvp.curriculum.graph` — DAG store. Nodes are subsection skill ids,
  edges are prerequisite relationships. Backed by ``graph.yaml``.
- :mod:`mvp.curriculum.toc_ingest` — converts a structured TOC YAML
  (book_id + chapters/sections/subsections) into graph nodes plus default
  prerequisite edges following textbook ordering.
- :mod:`mvp.curriculum.prereqs` — proposes prerequisite edges by analyzing
  textbook ordering and cross-references found in subsection summaries.
- :mod:`mvp.curriculum.llm_baseline` — runs a bare LLM on a candidate
  node's question bank N times, records pass rate and failure-mode
  taxonomy, and returns the materialization decision per the
  two-dimensional filter rule (see ``workshop/docs/curriculum_design.md``).

The two-dimensional filter rule
-------------------------------
For each candidate subsection node:

- **Drop** if pass rate > 0.95 AND failure mode is benign (qualitative-only,
  no numerical wrong answers).
- **Keep markdown-only** (``concept.md`` only, no ``code/``) if pass rate is
  in [0.85, 0.95] AND content is conceptual rather than computational.
- **Keep code-backed** (``concept.md`` + ``code/``) if pass rate < 0.85 OR
  the subsection involves closed-form numerical calculation regardless of
  pass rate.

Closed-form numerical calculations (Black-Scholes pricing, simplex pivots,
NPV/IRR, ratio computations) always materialize as code-backed skills even
when bare-LLM pass rate is high — code makes them deterministic, eliminating
the silent-failure risk of LLM arithmetic.
"""

from mvp.curriculum import graph, llm_baseline, materialize, prereqs, toc_ingest

__all__ = ["graph", "llm_baseline", "materialize", "prereqs", "toc_ingest"]
