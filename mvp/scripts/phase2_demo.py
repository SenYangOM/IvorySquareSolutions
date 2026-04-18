"""Phase 2 live demo — canonicalise all 10 sample filings.

Walks :func:`mvp.ingestion.filings_ingest.sample_filings` and calls
:func:`mvp.standardize.statements.build_canonical_statements` on each.
Prints a one-line summary per filing (populated line-items / 16 plus
the data-quality flag), emits the 30 JSON statement files under
``data/canonical/``, and appends one
``{"event":"phase2_canonicalized", ...}`` line to ``data/manifest.jsonl``.

Exits ``0`` even when some line items are null — missingness is
expected (e.g. Carvana doesn't tag D&A / operating-income as standalone
concepts; pre-iXBRL filings may not split out a concept we want). The
mapping log at ``data/standardize_mapping_log.jsonl`` is the detailed
record of which concepts were tried for every line item.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from mvp.ingestion.filings_ingest import sample_filings
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement

_MVP_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _MVP_ROOT / "data" / "manifest.jsonl"


def _summarise(statements: list[CanonicalStatement]) -> tuple[int, int, str]:
    total = 0
    populated = 0
    for s in statements:
        for li in s.line_items:
            total += 1
            if li.value_usd is not None:
                populated += 1
    dqflag = statements[0].data_quality_flag if statements else "unknown"
    return populated, total, dqflag


def main(argv: list[str] | None = None) -> int:
    filings = sample_filings()
    print(f"Phase 2 demo — canonicalising {len(filings)} filings...")
    per_filing: list[dict[str, object]] = []
    for f in filings:
        filing_id = f"{f.cik}/{f.accession}"
        try:
            stmts = build_canonical_statements(filing_id)
        except Exception as exc:
            print(f"[fail ] {filing_id}: {type(exc).__name__}: {exc}")
            return 2
        populated, total, dqflag = _summarise(stmts)
        per_filing.append(
            {
                "filing_id": filing_id,
                "populated": populated,
                "total": total,
                "data_quality_flag": dqflag,
            }
        )
        print(
            f"[ok   ] {filing_id}  populated={populated}/{total}  "
            f"dqflag={dqflag}  issuer={f.issuer}  fpe={f.fiscal_period_end}"
        )

    # Append a single manifest event summarising the run.
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event": "phase2_canonicalized",
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filings_processed": len(filings),
        "per_filing": per_filing,
    }
    with _MANIFEST_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")

    total_populated = sum(int(x["populated"]) for x in per_filing)
    total_slots = sum(int(x["total"]) for x in per_filing)
    print(
        f"\nsummary: {total_populated}/{total_slots} line-items populated "
        f"across {len(filings)} filings "
        f"({total_populated / total_slots:.1%})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
