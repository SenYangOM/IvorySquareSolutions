# `coverage/` — expanding the issuer / filing universe

Scripts to grow the set of filings `mvp/` can run against. The MVP sample
universe is 5 US large-cap issuers × 2 fiscal years each = 10 filings; every
skill is exercised against this set. Adding a new issuer or a new fiscal
year to the universe is a recurring operation — each expansion requires
pulling the submissions JSON, validating the filings exist, checking iXBRL
tagging, appending to the ingestion catalog, and re-running eval. The
scripts here automate that pipeline so "add Netflix FY2023" is one command
instead of a 40-minute manual process.

Typical first real items, in descending priority:

- **`add_issuer.py cik=<cik> years=<y1,y2>`** — pull the issuer's
  submissions JSON from EDGAR (via `mvp.lib.edgar.EdgarClient`), locate the
  10-K for each requested fiscal year, verify iXBRL era (or flag
  `pre_ixbrl_sgml` if older than ~2009), append `FilingRef` entries to the
  hardcoded `_SAMPLE_FILINGS` tuple in
  `mvp/ingestion/filings_ingest.py`, and optionally run `ingest_filing()`
  to pull the bytes. Writes back a diff for the operator to review before
  commit. This is the workflow for growing beyond the MVP 5.
- **`validate_new_filing.py cik=<cik> accession=<accession>`** — for a
  single new filing, run the extract_canonical_statements skill and report
  the population rate (which of the 16 canonical line items resolved,
  which returned null, which used a fallback concept). Gates a new issuer's
  "is this worth adding?" decision before the gold-case work starts.
- **`expand_market_data_fixture.py`** — for each new issuer in
  `_SAMPLE_FILINGS`, fetch shares outstanding (cover page) and fiscal-
  year-end close price (CRSP / Yahoo / Bloomberg) to populate a new row in
  `data/market_data/equity_values.yaml`. Includes the 1%-tolerance
  consistency check from `market_data_loader.py`.

Owner: the `evaluation_agent` persona or the engineer landing a new issuer.
Coverage scripts are closer to infrastructure than to research — a failed
`add_issuer.py` blocks a gold case from being authored, so these are worth
testing once they exist.
