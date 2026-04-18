"""Phase 1 live L0-ingestion demo.

Runs the full Phase 1 L0 ingestion end-to-end against the live SEC EDGAR
and paper-mirror hosts:

1. All 10 sample 10-K filings (``ingestion.filings_ingest.ingest_filing``),
   with a 0.2s courtesy pause between fresh downloads (lib/edgar already
   enforces the 10 req/s bucket, the pause is additional).
2. Both sample papers (``ingestion.papers_ingest.ingest_paper``).
3. The market-data fixture (``ingestion.market_data_loader.load_equity_values``).

Prints a compact per-record summary and the final ``data/manifest.jsonl``
line count. A first run against an empty ``data/`` tree should produce
12 manifest events (10 filings + 2 papers). Re-runs remain idempotent —
each call appends a ``*_skipped_already_ingested`` event.

Run with:

    .venv/bin/python -m mvp.scripts.phase1_demo
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from mvp.ingestion.filings_ingest import ingest_filing, sample_filings
from mvp.ingestion.market_data_loader import load_equity_values
from mvp.ingestion.papers_ingest import ingest_paper, sample_papers
from mvp.lib.edgar import EdgarClient

_MVP_ROOT = Path(__file__).resolve().parent.parent
_MANIFEST_PATH = _MVP_ROOT / "data" / "manifest.jsonl"


def _count_manifest_lines() -> int:
    if not _MANIFEST_PATH.exists():
        return 0
    return sum(1 for line in _MANIFEST_PATH.read_text().splitlines() if line.strip())


def _ingest_all_filings(pause_seconds: float = 0.2) -> None:
    print("=== Filings ===")
    with EdgarClient() as client:
        for ref in sample_filings():
            result = ingest_filing(ref.cik, ref.accession, client=client)
            status = "cached" if result.was_cached else "fetched"
            flag = f" flag={result.data_quality_flag}" if result.data_quality_flag else ""
            print(
                f"  [{status}] {ref.issuer:<22s} {ref.fiscal_period_end} "
                f"size={result.size_bytes:>10,d}  sha256={result.sha256[:12]}{flag}"
            )
            if not result.was_cached:
                time.sleep(pause_seconds)


def _ingest_all_papers() -> None:
    print("=== Papers ===")
    for ref in sample_papers():
        result = ingest_paper(ref.paper_id)
        status = "cached" if result.was_cached else "fetched"
        print(
            f"  [{status}] {ref.paper_id:<16s} size={result.size_bytes:>8,d}  "
            f"sha256={result.sha256[:12]}"
        )


def _summarize_equity_values() -> None:
    print("=== Market-data fixture ===")
    entries = load_equity_values()
    for e in entries:
        flags: list[str] = []
        if e.market_cap_source:
            flags.append(f"market_cap_source={e.market_cap_source}")
        if e.shares_source_flag:
            flags.append(f"shares_source_flag={e.shares_source_flag}")
        flag_suffix = f"  [{'; '.join(flags)}]" if flags else ""
        print(
            f"  {e.issuer:<22s} {e.fiscal_year_end}  "
            f"MVE=${e.market_value_of_equity_usd:>20,.0f}{flag_suffix}"
        )
    print(f"  total entries: {len(entries)}")


def main() -> int:
    start = _count_manifest_lines()
    print(f"manifest.jsonl starting line count: {start}")

    _ingest_all_filings()
    _ingest_all_papers()
    _summarize_equity_values()

    end = _count_manifest_lines()
    print(f"\nmanifest.jsonl ending line count: {end}")
    print(f"delta: +{end - start} events")
    return 0


if __name__ == "__main__":
    sys.exit(main())
