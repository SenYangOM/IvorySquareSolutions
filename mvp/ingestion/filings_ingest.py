"""L0 filings ingestion.

Downloads the 10 sample 10-K filings referenced in ``BUILD_REFS.md`` into
``data/filings/<cik>/<accession>/`` and records one append-only line per
ingestion event in ``data/manifest.jsonl``.

Each filing directory contains:

- ``primary_document.<ext>`` — the raw HTML/TXT as returned by EDGAR,
  byte-identical to the upstream document (extension preserved from the
  source filename).
- ``meta.json`` — structured metadata conforming to
  :class:`IngestResult` (minus ``was_cached``), always overwritten
  atomically after the primary document is persisted.

Idempotence contract
--------------------
A second call for the same ``(cik, accession)`` whose on-disk
``primary_document`` already matches the recorded ``sha256`` is a no-op: it
returns ``was_cached=True`` and appends a
``{"event": "filing_skipped_already_ingested", ...}`` line to the manifest.
A hash mismatch (file on disk differs from the recorded ``sha256``) raises
:class:`mvp.lib.errors.IngestionError` — silent repair is forbidden per
Operating Principle P2.

See ``mvp_build_goal.md`` §9 (filings store layout), §4 (sample issuers),
and §13 decision 3 (pre-iXBRL SGML handling).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from mvp.lib.edgar import EdgarClient, normalize_cik
from mvp.lib.errors import IngestionError
from mvp.lib.hashing import sha256_bytes, sha256_file

# -- Paths ---------------------------------------------------------------

_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_FILINGS_DIR = _DATA_DIR / "filings"
_MANIFEST_PATH = _DATA_DIR / "manifest.jsonl"

# Pre-iXBRL filings — mandated by §13 decision 3 to carry a data-quality
# flag. The four accessions below are hand-copied from BUILD_REFS.md §1.1
# and §1.2; they are the two Enron and two WorldCom filings.
_PRE_IXBRL_FLAG = "pre_ixbrl_sgml"
_PRE_IXBRL_ACCESSIONS: frozenset[str] = frozenset(
    {
        "0001024401-01-500010",  # Enron FY2000
        "0001024401-00-000002",  # Enron FY1999
        "0001005477-02-001226",  # WorldCom FY2001
        "0000912057-01-505916",  # WorldCom FY2000
    }
)


# -- Reference data ------------------------------------------------------


class FilingRef(BaseModel):
    """A single sample filing's canonical reference from BUILD_REFS.md."""

    model_config = {"frozen": True}

    issuer: str
    cik: str
    accession: str
    filing_type: str
    fiscal_period_end: str  # ISO date yyyy-mm-dd
    filed_at: str  # ISO date yyyy-mm-dd
    primary_document: str
    source_url: str


# Hardcoded per the build spec: Phase 1 is NOT a re-scraper. BUILD_REFS.md
# gathered these by querying EDGAR submissions JSON in Phase 0; Phase 1
# uses them as immutable inputs. Order: issuer × (current year, prior year).
_SAMPLE_FILINGS: tuple[FilingRef, ...] = (
    # Enron Corp — CIK 0001024401 — pre-iXBRL SGML .txt
    FilingRef(
        issuer="Enron Corp",
        cik="0001024401",
        accession="0001024401-01-500010",
        filing_type="10-K",
        fiscal_period_end="2000-12-31",
        filed_at="2001-04-02",
        primary_document="ene10-k.txt",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1024401/"
            "000102440101500010/ene10-k.txt"
        ),
    ),
    FilingRef(
        issuer="Enron Corp",
        cik="0001024401",
        accession="0001024401-00-000002",
        filing_type="10-K",
        fiscal_period_end="1999-12-31",
        filed_at="2000-03-30",
        # EDGAR's primaryDocument field is blank for this accession; the
        # single SGML-concatenated submission file is the whole document.
        primary_document="0001024401-00-000002.txt",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1024401/"
            "000102440100000002/0001024401-00-000002.txt"
        ),
    ),
    # WorldCom Inc. — CIK 0000723527 — pre-iXBRL SGML .txt, form 10-K405
    FilingRef(
        issuer="WorldCom Inc",
        cik="0000723527",
        accession="0001005477-02-001226",
        filing_type="10-K405",
        fiscal_period_end="2001-12-31",
        filed_at="2002-03-13",
        primary_document="d02-36461.txt",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/723527/"
            "000100547702001226/d02-36461.txt"
        ),
    ),
    FilingRef(
        issuer="WorldCom Inc",
        cik="0000723527",
        accession="0000912057-01-505916",
        filing_type="10-K405",
        fiscal_period_end="2000-12-31",
        filed_at="2001-03-30",
        primary_document="a2043540z10-k405.txt",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/723527/"
            "000091205701505916/a2043540z10-k405.txt"
        ),
    ),
    # Apple Inc. — CIK 0000320193 — iXBRL-tagged HTML
    FilingRef(
        issuer="Apple Inc",
        cik="0000320193",
        accession="0000320193-23-000106",
        filing_type="10-K",
        fiscal_period_end="2023-09-30",
        filed_at="2023-11-03",
        primary_document="aapl-20230930.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/"
            "000032019323000106/aapl-20230930.htm"
        ),
    ),
    FilingRef(
        issuer="Apple Inc",
        cik="0000320193",
        accession="0000320193-22-000108",
        filing_type="10-K",
        fiscal_period_end="2022-09-24",
        filed_at="2022-10-28",
        primary_document="aapl-20220924.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/320193/"
            "000032019322000108/aapl-20220924.htm"
        ),
    ),
    # Microsoft Corporation — CIK 0000789019 — iXBRL-tagged HTML
    FilingRef(
        issuer="Microsoft Corporation",
        cik="0000789019",
        accession="0000950170-23-035122",
        filing_type="10-K",
        fiscal_period_end="2023-06-30",
        filed_at="2023-07-27",
        primary_document="msft-20230630.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/789019/"
            "000095017023035122/msft-20230630.htm"
        ),
    ),
    FilingRef(
        issuer="Microsoft Corporation",
        cik="0000789019",
        accession="0001564590-22-026876",
        filing_type="10-K",
        fiscal_period_end="2022-06-30",
        filed_at="2022-07-28",
        primary_document="msft-10k_20220630.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/789019/"
            "000156459022026876/msft-10k_20220630.htm"
        ),
    ),
    # Carvana Co. — CIK 0001690820 — iXBRL-tagged HTML
    FilingRef(
        issuer="Carvana Co",
        cik="0001690820",
        accession="0001690820-23-000052",
        filing_type="10-K",
        fiscal_period_end="2022-12-31",
        filed_at="2023-02-23",
        primary_document="cvna-20221231.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1690820/"
            "000169082023000052/cvna-20221231.htm"
        ),
    ),
    FilingRef(
        issuer="Carvana Co",
        cik="0001690820",
        accession="0001690820-22-000080",
        filing_type="10-K",
        fiscal_period_end="2021-12-31",
        filed_at="2022-02-24",
        primary_document="cvna-20211231.htm",
        source_url=(
            "https://www.sec.gov/Archives/edgar/data/1690820/"
            "000169082022000080/cvna-20211231.htm"
        ),
    ),
)

_SAMPLE_INDEX: dict[tuple[str, str], FilingRef] = {
    (f.cik, f.accession): f for f in _SAMPLE_FILINGS
}


# -- Public model --------------------------------------------------------


class IngestResult(BaseModel):
    """Result of an ``ingest_filing`` call.

    Mirrors the on-disk ``meta.json`` 1:1, plus ``was_cached`` and
    ``path`` for the caller's convenience.
    """

    cik: str = Field(pattern=r"^\d{10}$")
    accession_number: str
    filing_type: str
    fiscal_period_end: str
    filed_at: str
    source_url: str
    primary_document: str
    primary_document_ext: str
    path: str  # absolute path to the primary document on disk
    fetched_at: str  # ISO-8601 UTC
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int
    data_quality_flag: str | None = None
    was_cached: bool = False


# -- Public API ----------------------------------------------------------


def ingest_filing(
    cik: str,
    accession: str,
    client: EdgarClient | None = None,
) -> IngestResult:
    """Ingest one sample filing into ``data/filings/<cik>/<accession>/``.

    Parameters
    ----------
    cik:
        10-digit zero-padded CIK, or any form accepted by
        :func:`mvp.lib.edgar.normalize_cik`.
    accession:
        Dashed EDGAR accession (``"0000320193-23-000106"``) matching one of
        the ten sample filings hardcoded in this module.
    client:
        Optional :class:`EdgarClient`. When ``None`` a fresh client is
        constructed (and closed) inside this call.

    Returns
    -------
    IngestResult
        Populated from either the freshly fetched document or the existing
        cached copy (``was_cached=True``).

    Raises
    ------
    IngestionError
        - ``reason="unknown_filing"`` if the ``(cik, accession)`` pair is
          not one of the ten sample filings.
        - ``reason="hash_mismatch"`` if the file on disk does not match
          the recorded ``meta.json`` hash (silent corruption; never
          auto-repaired).
        - ``reason="size_mismatch"`` if the downloaded body is zero-length
          (EDGAR should never return an empty document for a real filing).
    EdgarHttpError, RateLimitExceeded
        Propagated from the underlying EDGAR client on network/HTTP error.
    """
    cik_norm = normalize_cik(cik)
    ref = _SAMPLE_INDEX.get((cik_norm, accession))
    if ref is None:
        raise IngestionError(
            f"no sample filing registered for cik={cik_norm} accession={accession}",
            reason="unknown_filing",
            target=f"{cik_norm}/{accession}",
        )

    filing_dir = _FILINGS_DIR / cik_norm / accession
    ext = _extract_extension(ref.primary_document)
    primary_path = filing_dir / f"primary_document{ext}"
    meta_path = filing_dir / "meta.json"

    cached = _try_load_cached(primary_path, meta_path, ref)
    if cached is not None:
        _append_manifest(
            {
                "event": "filing_skipped_already_ingested",
                "cik": cik_norm,
                "accession": accession,
                "path": str(primary_path),
                "sha256": cached.sha256,
                "ingested_at": _utc_now_iso(),
            }
        )
        return cached

    owns_client = client is None
    active_client = client if client is not None else EdgarClient()
    try:
        body = active_client.fetch_document(ref.source_url)
    finally:
        if owns_client:
            active_client.close()

    if not body:
        raise IngestionError(
            f"empty document body from {ref.source_url}",
            reason="size_mismatch",
            target=f"{cik_norm}/{accession}",
        )

    filing_dir.mkdir(parents=True, exist_ok=True)

    # Write atomically: staging path, then rename. Prevents a partial write
    # from masquerading as a successful cached ingestion on a later run.
    stage_path = primary_path.with_suffix(primary_path.suffix + ".partial")
    stage_path.write_bytes(body)
    stage_path.replace(primary_path)

    digest = sha256_bytes(body)
    data_quality_flag: str | None = (
        _PRE_IXBRL_FLAG if accession in _PRE_IXBRL_ACCESSIONS else None
    )

    fetched_at = _utc_now_iso()
    meta: dict[str, object] = {
        "cik": cik_norm,
        "accession_number": accession,
        "filing_type": ref.filing_type,
        "fiscal_period_end": ref.fiscal_period_end,
        "filed_at": ref.filed_at,
        "source_url": ref.source_url,
        "primary_document": ref.primary_document,
        "primary_document_ext": ext,
        "fetched_at": fetched_at,
        "sha256": digest,
        "size_bytes": len(body),
    }
    if data_quality_flag is not None:
        meta["data_quality_flag"] = data_quality_flag

    meta_stage = meta_path.with_suffix(".json.partial")
    meta_stage.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    meta_stage.replace(meta_path)

    _append_manifest(
        {
            "event": "filing_ingested",
            "cik": cik_norm,
            "accession": accession,
            "path": str(primary_path),
            "sha256": digest,
            "ingested_at": fetched_at,
        }
    )

    return IngestResult(
        cik=cik_norm,
        accession_number=accession,
        filing_type=ref.filing_type,
        fiscal_period_end=ref.fiscal_period_end,
        filed_at=ref.filed_at,
        source_url=ref.source_url,
        primary_document=ref.primary_document,
        primary_document_ext=ext,
        path=str(primary_path),
        fetched_at=fetched_at,
        sha256=digest,
        size_bytes=len(body),
        data_quality_flag=data_quality_flag,
        was_cached=False,
    )


def sample_filings() -> tuple[FilingRef, ...]:
    """Return the hardcoded Phase 1 sample-filing references."""
    return _SAMPLE_FILINGS


def find_filing(cik: str, fiscal_year_end: str) -> FilingRef | None:
    """Return the sample :class:`FilingRef` for ``(cik, fiscal_year_end)``.

    ``cik`` is normalised through :func:`mvp.lib.edgar.normalize_cik`;
    ``fiscal_year_end`` must be an ISO date string (e.g. ``"2000-12-31"``)
    and must match a filing's recorded FPE exactly.

    Returns ``None`` when no sample filing matches — callers use this to
    surface an ``unknown_filing`` error to the agent.
    """
    cik_norm = normalize_cik(cik)
    for ref in _SAMPLE_FILINGS:
        if ref.cik == cik_norm and ref.fiscal_period_end == fiscal_year_end:
            return ref
    return None


def find_prior_year_filing(cik: str, current_fiscal_year_end: str) -> FilingRef | None:
    """Return the prior-year sample :class:`FilingRef` for the same issuer.

    Looks for a sample filing whose ``fiscal_period_end`` falls roughly
    one year before ``current_fiscal_year_end``. Accepts any span between
    340 and 380 days to cover 52/53-week fiscal years (e.g. Apple's
    2022→2023 transition spans 371 days).
    """
    cik_norm = normalize_cik(cik)
    cur = date.fromisoformat(current_fiscal_year_end)
    best: FilingRef | None = None
    best_gap = 10**9
    for ref in _SAMPLE_FILINGS:
        if ref.cik != cik_norm:
            continue
        their = date.fromisoformat(ref.fiscal_period_end)
        if their >= cur:
            continue
        gap = (cur - their).days
        if 340 <= gap <= 380 and gap < best_gap:
            best = ref
            best_gap = gap
    return best


# -- Internals -----------------------------------------------------------


def _extract_extension(primary_document: str) -> str:
    """Return the original document extension including the leading dot.

    For multi-dot filenames like ``msft-10k_20220630.htm`` the final
    extension is returned. If no extension is present an empty string
    comes back — callers should not hit this for real EDGAR documents.
    """
    suffix = Path(primary_document).suffix
    return suffix.lower()


def _try_load_cached(
    primary_path: Path,
    meta_path: Path,
    ref: FilingRef,
) -> IngestResult | None:
    """Return a cached :class:`IngestResult` or ``None`` if not fully present.

    Raises :class:`IngestionError` with ``reason="hash_mismatch"`` when the
    file is on disk but its sha256 no longer matches the recorded meta —
    per Operating Principle P2, we never silently re-download.
    """
    if not (primary_path.exists() and meta_path.exists()):
        return None

    try:
        meta_raw = meta_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise IngestionError(
            f"unable to read cached meta {meta_path}: {exc}",
            reason="meta_unreadable",
            target=str(meta_path),
        ) from exc

    try:
        meta = json.loads(meta_raw)
    except json.JSONDecodeError as exc:
        raise IngestionError(
            f"cached meta {meta_path} is not valid JSON: {exc}",
            reason="meta_invalid_json",
            target=str(meta_path),
        ) from exc

    recorded_hash = meta.get("sha256")
    if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
        raise IngestionError(
            f"cached meta {meta_path} missing/malformed sha256",
            reason="meta_missing_sha256",
            target=str(meta_path),
        )

    actual_hash = sha256_file(primary_path)
    if actual_hash != recorded_hash:
        raise IngestionError(
            (
                f"hash mismatch for {primary_path}: meta recorded "
                f"{recorded_hash} but file hashes to {actual_hash}"
            ),
            reason="hash_mismatch",
            target=str(primary_path),
        )

    return IngestResult(
        cik=str(meta.get("cik", ref.cik)),
        accession_number=str(meta.get("accession_number", ref.accession)),
        filing_type=str(meta.get("filing_type", ref.filing_type)),
        fiscal_period_end=str(meta.get("fiscal_period_end", ref.fiscal_period_end)),
        filed_at=str(meta.get("filed_at", ref.filed_at)),
        source_url=str(meta.get("source_url", ref.source_url)),
        primary_document=str(meta.get("primary_document", ref.primary_document)),
        primary_document_ext=str(
            meta.get("primary_document_ext", _extract_extension(ref.primary_document))
        ),
        path=str(primary_path),
        fetched_at=str(meta.get("fetched_at", _utc_now_iso())),
        sha256=recorded_hash,
        size_bytes=int(meta.get("size_bytes", primary_path.stat().st_size)),
        data_quality_flag=meta.get("data_quality_flag"),
        was_cached=True,
    )


def _append_manifest(record: dict[str, object]) -> None:
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False, sort_keys=True)
    with _MANIFEST_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# -- CLI -----------------------------------------------------------------


def _cli_batch_all(client: EdgarClient, pause_seconds: float) -> list[IngestResult]:
    import time as _time

    results: list[IngestResult] = []
    for ref in _SAMPLE_FILINGS:
        result = ingest_filing(ref.cik, ref.accession, client=client)
        results.append(result)
        if not result.was_cached:
            _time.sleep(pause_seconds)
    return results


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvp.ingestion.filings_ingest",
        description="Ingest SEC filings for the Phase 1 sample set.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--batch",
        choices=["all"],
        help="Ingest all 10 Phase 1 sample filings.",
    )
    group.add_argument(
        "--cik",
        help="CIK of a single filing (requires --accession).",
    )
    parser.add_argument(
        "--accession",
        help="Accession number (required with --cik).",
    )
    parser.add_argument(
        "--pause-seconds",
        type=float,
        default=0.2,
        help="Courteous pause between downloads in batch mode (default 0.2).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    mode: Literal["batch", "single"]
    if args.batch is not None:
        mode = "batch"
    else:
        if not args.accession:
            parser.error("--cik requires --accession")
        mode = "single"

    with EdgarClient() as client:
        if mode == "batch":
            results = _cli_batch_all(client, args.pause_seconds)
            for r in results:
                status = "cached" if r.was_cached else "fetched"
                print(
                    f"[{status}] {r.cik}/{r.accession_number} "
                    f"size={r.size_bytes} sha256={r.sha256[:12]}"
                )
        else:
            result = ingest_filing(args.cik, args.accession, client=client)
            json.dump(
                result.model_dump(), sys.stdout, indent=2, ensure_ascii=False
            )
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
