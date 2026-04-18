# `research/` — ad-hoc research scripts

Ad-hoc research scripts live here. Scripts in this folder are one-offs — they
answer a specific question at a specific point in time, the team runs them
once or twice, and the output (a CSV, a markdown note, a JSON dump) is what
the team cares about, not the script itself. A research script that becomes
recurring is a signal to promote it: either into `workshop/coverage/`,
`workshop/maintenance/`, or `workshop/eval_ops/` depending on its cadence, or
(if it is useful enough to expose as a product surface) into `mvp.lib` +
`mvp/skills/`.

Typical first real items, in descending priority:

- **`edgar_company_search.py`** — take a company name or partial CIK and
  return the submissions-history summary: every 10-K / 10-Q / 8-K accession
  in the last N years, fiscal-period-end alignment, iXBRL vs SGML detection.
  Reuses `mvp.lib.edgar.EdgarClient` so the SEC fair-access rate limit is
  respected. Answers the question "can this issuer be added to our sample
  universe?" without writing a new ingestion path.
- **`companyfacts_concept_coverage.py`** — given a CIK and a list of us-gaap
  concepts (or the current 16 canonical line items), tabulate which concepts
  appear in that issuer's companyfacts JSON, which are null, which use a
  fallback taxonomy tag, and which the issuer has extended. Reads the cached
  `data/companyfacts/CIK<cik>.json` files; no new network fetches. Outputs a
  CSV. Answers "is this issuer's XBRL clean enough to extend an existing
  skill to it?" before we commit to a gold case.
- **`peer_group_scanner.py`** — given a seed CIK, enumerate SIC-matched peers
  from the SEC's fulltext search, rank by filed-10-K cadence and size.
  Produces a markdown summary a human can read in 5 minutes. Useful whenever
  a paper's skill needs industry context we don't already have.

Owner: the `quant_finance_methodologist` persona or the researcher who spawns
the script. Scripts here do NOT need tests; the one-shot nature is the point.
Do NOT import from `mvp/skills/**/skill.py` directly — use the registry if
you need a skill's output.
