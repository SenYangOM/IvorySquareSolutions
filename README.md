# IvorySquare

*An open Ivory Tower for everyone.*

A framework that treats peer-reviewed methodology — across finance, accounting, economics, and operations research — as a first-class tool surface for LLM agents.

Most AI tools for these domains today are wrappers around chat, with a human as the user of the language model. IvorySquare is built on the inverted premise: **the language model is the user**, and the system exposes peer-reviewed methods — typed, test-backed, provenance-tracked — as the tool surface it consumes.

## Architecture

Three components, plus a purpose-built evaluation harness that gates every solution.

- **Data.** Ingestion of corporate disclosures (SEC filings, XBRL / iXBRL), market data, and related sources through APIs and MCP connectors. Standardized into a typed store with versioning and deterministic replay.
- **Skills.** Citation-grounded implementations derived directly from peer-reviewed papers. Each skill carries its formula, its paper reference, a unit-test harness against known cases, and a provenance trace from numeric output down to the source filing line item. Exposed through parallel MCP server and OpenAI tool-spec surfaces — one library, two agent runtimes, no translation glue.
- **Solutions.** Compositions of data and skills into workflows and sub-agents for concrete applications. Four LLM sub-agent personas — `accounting_expert`, `quant_finance_methodologist`, `evaluation_agent`, `citation_auditor` — self-validate outputs and flag hallucinated citations before delivery.
- **Evaluation harness.** A first-class design concern, not an afterthought. Every solution is gated by a harness tuned to the review bar of the domain it serves — rubric-driven scoring for accounting interpretation, overfitting-aware statistical validation for quantitative research. The harness, not the language model, decides what ships.

A longer discussion of the framing lives at [senyangom.github.io/posts/2026/04/ivorysquare-architecture/](https://senyangom.github.io/posts/2026/04/ivorysquare-architecture/).

## Current status — MVP vertical slice

The repository ships an end-to-end vertical slice on US large-cap SEC filings:

- 7 registered skills (2 fundamentals, 2 interpretation, 2 paper-derived, 1 composite);
- paper-derived skills implementing the **Beneish M-Score** and **Altman Z-Score**, grounded in the original academic papers;
- 10 gold cases across the two paper-derived skills, with deterministic replay;
- 4 YAML-configurable LLM sub-agent personas;
- parallel FastAPI service and argparse CLI over a single shared tool registry;
- 380 passing tests.

The canonical worked example is a citation-grounded analysis of the historical Enron 10-K (fiscal year 2000) — a known-positive case used as a regression check on the interpretation engine.

## Quick start

Requires Python 3.11.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -e ./mvp

# Run the test suite (380 tests when filings are ingested; 341 on a fresh clone).
.venv/bin/pytest -q

# Run the gold-case evaluation.
.venv/bin/python -m mvp.cli.main eval

# Canonical Enron 10-K demo.
.venv/bin/python -m mvp.cli.main run analyze_for_red_flags \
    --cik 0001024401 --year 2000-12-31
```

See [`mvp/README.md`](mvp/README.md) for the full engineering quickstart, including data ingestion and the end-to-end demo walkthrough.

The Python package currently imports as `mvp` — a name carried over from the initial build phase; a rename to `ivorysquare` is planned but has not yet been applied to the code.

## Repository layout

```
mvp/             # Python package: data ingestion, skill library, agent personas,
                 # interpretation engine, evaluation harness, FastAPI service, CLI.
paper_examples/  # Source PDFs backing the paper-derived skills.
workshop/        # Team-facing playbook for onboarding new papers into new skills.
```

## Research direction

A direction that motivates the framework is the use of **academic citation networks** — the topology of how ideas build from primitive methods to composite ones — as a structured post-training substrate for tool-using LLMs. A library of paper-derived, citation-audited skills is more than a collection: it is a graph whose topology mirrors the conceptual structure of the underlying literature, and each skill supplies both a tool-use trace and a verifiable ground-truth signal.

## Authors and collaborators

- [**Sen Yang**](https://senyangom.github.io/) — lead author and maintainer. Ph.D. in Operations Management, NYU Stern.
- **Han Yan** — collaborator. Assistant Professor, Accounting Department, UBC; Ph.D. in Accounting, NYU Stern.

## Contact

`sy2576 [at] stern.nyu.edu`
