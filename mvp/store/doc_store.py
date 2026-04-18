"""L1 doc store: read-only access to the ingested ``data/filings/`` tree.

Phase 1 (``mvp.ingestion.filings_ingest``) is the only writer for this
tree; this module is the reader. A doc is addressed by the string
``doc_id = "<cik>/<accession>"``; locator parts inside
:class:`mvp.lib.citation.Citation` use ``"::"`` as a separator, so we
reserve ``"/"`` as the natural doc-id separator and forbid ``"::"`` in
doc_ids.

Every read verifies the on-disk sha256 against the recorded
``meta.json`` hash. A mismatch raises :class:`StoreError` with
``reason="hash_mismatch"`` — silent repair is forbidden per P2.

Public API:

* :func:`get_doc` — return a :class:`DocRecord` (does sha256 verification).
* :func:`get_doc_bytes` — raw bytes of the primary document.
* :func:`get_doc_text` — UTF-8 text of the primary document (with
  ``errors="replace"``, since pre-iXBRL SGML filings include a smattering
  of non-UTF-8 bytes that we don't want to abort a read over; the bytes
  API is available for callers who need exact fidelity).
* :func:`list_filings` — list all docs currently in the tree.
"""

from __future__ import annotations

import json
import mimetypes
from datetime import datetime
from pathlib import Path

from mvp.lib.errors import StoreError
from mvp.lib.hashing import sha256_bytes, sha256_file

from .schema import DocRecord

# Module-level path constants — monkeypatched by tests the same way
# ``mvp.ingestion.filings_ingest`` is.
_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_FILINGS_DIR = _DATA_DIR / "filings"


# --- Doc-id helpers -----------------------------------------------------


def _split_doc_id(doc_id: str) -> tuple[str, str]:
    """Split ``"<cik>/<accession>"`` into its parts with validation.

    ``"::"`` is forbidden in doc_ids (reserved for locator parts); so is
    an empty cik or accession. Raises :class:`StoreError` with
    ``reason="invalid_doc_id"`` on malformed input.
    """
    if not isinstance(doc_id, str) or not doc_id:
        raise StoreError(
            f"doc_id must be a non-empty string, got {doc_id!r}",
            reason="invalid_doc_id",
            filing_id=str(doc_id),
        )
    if "::" in doc_id:
        raise StoreError(
            f"doc_id must not contain '::' (reserved for locators): {doc_id!r}",
            reason="invalid_doc_id",
            filing_id=doc_id,
        )
    parts = doc_id.split("/")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise StoreError(
            f"doc_id must be '<cik>/<accession>', got {doc_id!r}",
            reason="invalid_doc_id",
            filing_id=doc_id,
        )
    return parts[0], parts[1]


def _filing_dir(doc_id: str) -> Path:
    cik, accession = _split_doc_id(doc_id)
    return _FILINGS_DIR / cik / accession


# --- Meta loading + primary-document discovery --------------------------


def _load_meta(doc_id: str) -> dict[str, object]:
    meta_path = _filing_dir(doc_id) / "meta.json"
    if not meta_path.exists():
        raise StoreError(
            f"filing {doc_id} not found (no meta.json at {meta_path})",
            reason="not_found",
            filing_id=doc_id,
        )
    try:
        raw = meta_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoreError(
            f"unable to read meta.json for {doc_id}: {exc}",
            reason="meta_unreadable",
            filing_id=doc_id,
        ) from exc
    try:
        meta = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StoreError(
            f"meta.json for {doc_id} is not valid JSON: {exc}",
            reason="meta_invalid_json",
            filing_id=doc_id,
        ) from exc
    if not isinstance(meta, dict):
        raise StoreError(
            f"meta.json for {doc_id} must be a JSON object, got {type(meta).__name__}",
            reason="meta_invalid_json",
            filing_id=doc_id,
        )
    return meta


def _primary_path(doc_id: str, meta: dict[str, object]) -> Path:
    ext = meta.get("primary_document_ext")
    if not isinstance(ext, str):
        raise StoreError(
            f"meta.json for {doc_id} missing 'primary_document_ext'",
            reason="meta_missing_field",
            filing_id=doc_id,
        )
    path = _filing_dir(doc_id) / f"primary_document{ext}"
    if not path.exists():
        raise StoreError(
            f"primary document for {doc_id} not found at {path}",
            reason="not_found",
            filing_id=doc_id,
        )
    return path


def _infer_content_type(ext: str) -> str:
    # Hand-map the extensions we actually produce in L0 ingestion; fall
    # back to mimetypes.guess_type for anything else. We keep the map
    # explicit (rather than relying on mimetypes alone) because Python's
    # stdlib mimetypes treats ``.htm`` as ``text/html`` only on some
    # platforms.
    ext_lower = ext.lower()
    if ext_lower in (".htm", ".html"):
        return "text/html"
    if ext_lower == ".txt":
        return "text/plain"
    guess, _ = mimetypes.guess_type(f"x{ext_lower}")
    return guess or "application/octet-stream"


# --- Public API ---------------------------------------------------------


def get_doc(filing_id: str) -> DocRecord:
    """Return the :class:`DocRecord` for ``filing_id``.

    Reads ``meta.json``, locates the primary document, and verifies its
    on-disk sha256 against the recorded hash. A mismatch raises
    :class:`StoreError` with ``reason="hash_mismatch"``.
    """
    meta = _load_meta(filing_id)
    primary = _primary_path(filing_id, meta)

    recorded_hash = meta.get("sha256")
    if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
        raise StoreError(
            f"meta.json for {filing_id} missing or malformed sha256",
            reason="meta_missing_sha256",
            filing_id=filing_id,
        )

    actual_hash = sha256_file(primary)
    if actual_hash != recorded_hash:
        raise StoreError(
            f"hash mismatch for {filing_id}: meta recorded {recorded_hash} "
            f"but primary document hashes to {actual_hash}",
            reason="hash_mismatch",
            filing_id=filing_id,
        )

    cik, accession = _split_doc_id(filing_id)
    ext = str(meta.get("primary_document_ext", primary.suffix))
    fetched_at_raw = meta.get("fetched_at")
    if not isinstance(fetched_at_raw, str):
        raise StoreError(
            f"meta.json for {filing_id} missing 'fetched_at'",
            reason="meta_missing_field",
            filing_id=filing_id,
        )
    # ``fromisoformat`` in 3.11+ handles ``"Z"`` suffixes since 3.11.
    fetched_at = datetime.fromisoformat(fetched_at_raw.replace("Z", "+00:00"))

    return DocRecord(
        doc_id=filing_id,
        cik=cik,
        accession=accession,
        source_path=str(primary),
        content_type=_infer_content_type(ext),
        sha256=actual_hash,
        byte_len=primary.stat().st_size,
        fetched_at=fetched_at,
        data_quality_flag=(
            str(meta["data_quality_flag"]) if "data_quality_flag" in meta else None
        ),
    )


def get_doc_bytes(filing_id: str) -> bytes:
    """Return the raw bytes of the primary document for ``filing_id``.

    Verifies the sha256 after reading; a mismatch raises :class:`StoreError`
    with ``reason="hash_mismatch"``.
    """
    meta = _load_meta(filing_id)
    primary = _primary_path(filing_id, meta)
    recorded_hash = meta.get("sha256")
    if not isinstance(recorded_hash, str) or len(recorded_hash) != 64:
        raise StoreError(
            f"meta.json for {filing_id} missing or malformed sha256",
            reason="meta_missing_sha256",
            filing_id=filing_id,
        )
    data = primary.read_bytes()
    actual = sha256_bytes(data)
    if actual != recorded_hash:
        raise StoreError(
            f"hash mismatch for {filing_id}: meta recorded {recorded_hash} "
            f"but primary document bytes hash to {actual}",
            reason="hash_mismatch",
            filing_id=filing_id,
        )
    return data


def get_doc_text(filing_id: str) -> str:
    """Return the UTF-8-decoded text of the primary document.

    Bytes that aren't valid UTF-8 are replaced with ``U+FFFD``. Pre-iXBRL
    SGML filings include a handful of such bytes from legacy encodings;
    refusing to decode at all would break the only standardization path
    we have for those filings. Callers needing byte-exact fidelity should
    call :func:`get_doc_bytes` instead.
    """
    return get_doc_bytes(filing_id).decode("utf-8", errors="replace")


def list_filings() -> list[DocRecord]:
    """Return every filing currently under ``data/filings/``.

    Walks the two-level ``<cik>/<accession>/`` layout. Missing ``meta.json``
    / ``primary_document.*`` in a directory raises :class:`StoreError`
    (the tree is either well-formed or it isn't — we don't skip silently).
    Ordering is deterministic: sorted by ``(cik, accession)``.
    """
    if not _FILINGS_DIR.exists():
        return []
    results: list[DocRecord] = []
    for cik_dir in sorted(p for p in _FILINGS_DIR.iterdir() if p.is_dir()):
        for acc_dir in sorted(p for p in cik_dir.iterdir() if p.is_dir()):
            results.append(get_doc(f"{cik_dir.name}/{acc_dir.name}"))
    return results
