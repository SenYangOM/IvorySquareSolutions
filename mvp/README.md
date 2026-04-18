# `mvp/` — Proj_ongoing MVP

**Machine-readable accounting interpretation — Beneish M-Score + Altman Z-Score
vertical slice on 5 US large-cap filings.** Seven skills, one CLI, one
FastAPI stub, 10 gold cases, 380 tests. See `../mvp_build_goal.md` for the
architecture and scope.

This README is the 30-minute quickstart: clone → working Enron analysis.

---

## Prerequisites

- **Python 3.11** — install via
  [pyenv](https://github.com/pyenv/pyenv) and select `3.11.13` (or any
  `3.11.x`).
- **git**.
- **≤10 MB disk** for the 12 sample artifacts (10 filings + 2 papers).
- *Optional:* `ANTHROPIC_API_KEY` — **not required** by any shipped MVP
  skill (the L2 interpretation skills are deterministic templated
  substitution, no LLM calls in the request path). Future persona-driven
  skills will consume the key; set it via `.env` when those ship.

## Setup (copy-paste-runnable)

```bash
# from the project root
cd mvp
python -m venv .venv
.venv/bin/pip install -e '.[dev]'   # installs 'mvp' package + test deps

# verify install: 380 tests must pass
.venv/bin/pytest -q
```

   On a fresh clone (no data ingested yet), pytest prints "341 passed, 39 skipped".
   The skipped tests require live-ingested filings and run automatically after
   `mvp ingest filings --batch all` populates data/filings/ — full suite is 380.

Expected final line from pytest:

```
380 passed in 83s (0:01:23)
```

If you see anything other than `380 passed` (once data is ingested), stop and
diagnose — the remaining demo commands depend on a clean test run.

## Demo — three commands

All three commands run from inside `mvp/` with the venv active (replace
`.venv/bin/python` with your shell's `python` once the venv is on `PATH`).

### 1. Ingest the 10 filings + 2 papers (idempotent)

```bash
.venv/bin/python -m mvp.cli.main ingest filings --batch all
.venv/bin/python -m mvp.cli.main ingest paper   --batch all
```

First run fetches from SEC EDGAR (`≤10 req/s`, declared User-Agent) and from
a public paper mirror. Subsequent runs hit the on-disk cache and print
`filing_ingested_skipped_already_ingested` events. Expected output
(abbreviated):

```json
[
  {
    "cik": "0001024401",
    "accession_number": "0001024401-01-500010",
    "filing_type": "10-K",
    "fiscal_period_end": "2000-12-31",
    ...
  },
  ... (9 more filings)
]
[
  {
    "paper_id": "beneish_1999",
    "citation": "Beneish, M. D. (1999). The Detection of Earnings Manipulation...",
    ...
  },
  { "paper_id": "altman_1968", ... }
]
```

### 2. Analyze Enron's 2000 10-K — the canonical demo case

```bash
.venv/bin/python -m mvp.cli.main run analyze_for_red_flags \
    --cik 0001024401 --year 2000-12-31
```

Expected output (abbreviated — the full JSON has both result blocks,
per-component breakdowns, interpretations with citations, warnings, and
provenance):

```json
{
  "m_score_result": {
    "score": -0.2422,
    "flag": "manipulator_likely",
    "components": {
      "DSRI": 1.3654783625184095, "GMI": 2.1437183276812175,
      "AQI":  0.7713938466374066, "SGI": 2.5126894694854407,
      "DEPI": 1.109775564354571,  "SGAI": 0.42295331225151583,
      "LVGI": 1.353929279864726,  "TATA": 0.009526281239027221
    },
    "citations": [ ...32 line-item citations... ],
    "warnings": ["tata_approximation: ...", "pre_ixbrl_manual_extraction: ..."]
  },
  "z_score_result": {
    "score": 2.50655,
    "flag": "grey_zone",
    "components": { "X1": ..., "X2": ..., "X3": ..., "X4": ..., "X5": ... },
    "citations": [ ...8 line-item citations... ]
  },
  "provenance": {
    "composite_skill_id": "analyze_for_red_flags",
    "composite_version": "0.1.0",
    "rule_set_version": "...",
    "sub_skill_versions": { ... }
  }
}
```

Enron shows `manipulator_likely` (Beneish's own canonical positive case) and
`grey_zone` (consistent with Enron's November 2001 collapse being ~11 months
after this filing).

### 3. Full eval — the one-page gate report

```bash
.venv/bin/python -m mvp.cli.main eval
```

Expected output:

```
# Eval report <run_id> at <timestamp>
# Gold root: mvp/eval/gold

| case_id                  | score       | flag              | tol | cite |
|--------------------------|-------------|-------------------|-----|------|
| apple_2023_altman        | +7.6500 v +7.6500 | safe→safe         | OK | OK |
| carvana_2022_altman      |  null v  null | indetermi→indetermi | OK | OK |
| enron_2000_altman        | +2.5065 v +2.5070 | grey_zone→grey_zone | OK | OK |
| microsoft_2023_altman    | +9.2390 v +9.2390 | safe→safe         | OK | OK |
| worldcom_2001_altman     | +1.1016 v +1.1020 | distress→distress | OK | OK |
| apple_2023_beneish       | -2.3839 v -2.3840 | manipulat→manipulat | OK | OK |
| carvana_2022_beneish     |  null v  null | indetermi→indetermi | OK | OK |
| enron_2000_beneish       | -0.2422 v -0.2422 | manipulat→manipulat | OK | OK |
| microsoft_2023_beneish   | -2.4297 v -2.4300 | manipulat→manipulat | OK | OK |
| worldcom_2001_beneish    | -2.6284 v -1.4000 | manipulat→manipulat | !! | OK |

## Metrics (§4.2 — gate is 4/5 on score+flag for each skill, 100% on citations)
  m_score_within_0.10       : 4/5
  m_score_flag_match_rate   : 4/5
  z_score_within_0.10       : 5/5
  z_score_zone_match_rate   : 5/5
  citation_resolves         : 194/194
  gold_present_for_all_cases: 10/10
```

The WorldCom Beneish `!!` is an **explainable failure** — the MVP's 16-
canonical TATA approximation shifts the score across the -1.78 threshold.
Documented in the gold file's `known_deviation_explanation` block and in
the manifest's `implementation_decisions`. See
`../workshop/docs/paper_onboarding_playbook.md` §"Approximation is
acceptable; hiding approximation is not."

Exit code is `0` when the §4.2 gates pass; `1` if any threshold is missed.

---

## What you now have

After those three commands:

- 10 filings under `data/filings/<cik>/<accession>/` (~15 MB).
- 2 papers under `data/papers/*.pdf`.
- `data/manifest.jsonl` — append-only ingestion log, 12+ events.
- `data/canonical/<cik>/<accession>/*.json` — canonical IS/BS/CF for every
  filing (written on-demand by the skill).
- `data/demo_outputs/enron_2000_analyze_for_red_flags.json` — the Enron
  composite output (if you piped the command into the demo path).
- `eval/reports/<date>_<run_id>.json` — latest eval run, 30 KB.

## Agent / API surface

Every CLI command has a matching API route — the two share one registry and
produce byte-identical output bodies (modulo run_at / run_id / build_id /
retrieved_at).

```bash
# start the API
.venv/bin/uvicorn mvp.api:app --reload --port 8000

# list all skills
curl -s localhost:8000/v1/skills | jq .

# MCP tool catalog (drop-in for Claude Desktop / any MCP client)
curl -s localhost:8000/mcp/tools | jq length    # => 7

# OpenAI tools=[...] catalog (drop-in for chat completions with function-calling)
curl -s localhost:8000/openai/tools | jq length # => 7

# invoke the Enron composite over HTTP
curl -s -X POST localhost:8000/v1/skills/analyze_for_red_flags \
    -H 'content-type: application/json' \
    -d '{"cik":"0001024401","fiscal_year_end":"2000-12-31"}' | jq .
```

## Directory map

```
mvp/
├── README.md                   (this file)
├── pyproject.toml              install point
├── lib/                        cross-cutting utilities (no domain semantics)
├── ingestion/                  L0 — pull from EDGAR + paper mirrors
├── store/                      L1 — immutable hash-addressed doc/fact store
├── standardize/                L2 — XBRL → 16 canonical line items
├── rules/                      L3a — declarative rule templates (accounting_expert-authored)
├── engine/                     L3b — deterministic rule executor + citation validator
├── skills/
│   ├── fundamental/            L1 skills: extract_canonical_statements, extract_mdna
│   ├── interpretation/         L2 skills: interpret_m_score_components, interpret_z_score_components
│   ├── paper_derived/          L3 skills: compute_beneish_m_score, compute_altman_z_score
│   └── composite/              L4 skills: analyze_for_red_flags
├── agents/                     engineering-layer persona runtime (loads human_layer YAML)
├── human_layer/                declarative artifacts (personas, guides) — no Python required
├── eval/                       eval harness + 10 gold cases + reports
├── api/                        FastAPI stub (9 routes, 4 error handlers)
├── cli/                        argparse CLI (12 subcommands)
├── scripts/                    per-phase demo scripts
├── tests/                      380 tests (unit + integration)
└── data/                       filings, papers, market data, manifest.jsonl
```

## Further reading

- [`../mvp_build_goal.md`](../mvp_build_goal.md) — scope, architecture, skill
  catalogue, manifest schema, build sequence.
- [`../success_criteria.md`](../success_criteria.md) — top-line gates,
  per-layer DoD, quality gates, "demo morning" walkthrough.
- [`../workshop/README.md`](../workshop/README.md) — team-internal tooling;
  the post-MVP paper-onboarding playbook lives there.

The canonical build-progress ledger is [`BUILD_LOG.md`](BUILD_LOG.md) and
[`BUILD_STATE.json`](BUILD_STATE.json). `SPEC_UPDATES.md` records
late-breaking spec changes that override anything in the earlier phase
documents.
