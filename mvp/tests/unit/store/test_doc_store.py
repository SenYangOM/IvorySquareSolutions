"""Unit tests for :mod:`mvp.store.doc_store`.

Hermetic — fabricates a tiny ``data/filings/`` tree under ``tmp_path``
and monkeypatches the module-level paths to point at it, so the real
``mvp/data/filings/`` tree is never touched.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mvp.lib.errors import StoreError
from mvp.lib.hashing import sha256_bytes
from mvp.store import doc_store
from mvp.store.doc_store import get_doc, get_doc_bytes, get_doc_text, list_filings


# --- Fixtures -----------------------------------------------------------


@pytest.fixture
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    filings = data / "filings"
    filings.mkdir(parents=True)
    monkeypatch.setattr(doc_store, "_DATA_DIR", data)
    monkeypatch.setattr(doc_store, "_FILINGS_DIR", filings)
    return filings


def _make_filing(
    root: Path,
    cik: str,
    accession: str,
    *,
    body: bytes,
    ext: str = ".htm",
    data_quality_flag: str | None = None,
) -> str:
    fd = root / cik / accession
    fd.mkdir(parents=True, exist_ok=True)
    (fd / f"primary_document{ext}").write_bytes(body)
    meta = {
        "cik": cik,
        "accession_number": accession,
        "filing_type": "10-K",
        "fiscal_period_end": "2023-09-30",
        "filed_at": "2023-11-03",
        "source_url": "https://example.invalid/",
        "primary_document": f"test{ext}",
        "primary_document_ext": ext,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(body),
        "size_bytes": len(body),
    }
    if data_quality_flag is not None:
        meta["data_quality_flag"] = data_quality_flag
    (fd / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return f"{cik}/{accession}"


# --- get_doc ------------------------------------------------------------


def test_get_doc_happy_path(isolated_store: Path) -> None:
    body = b"<html>hello</html>"
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000001", body=body)
    doc = get_doc(fid)
    assert doc.doc_id == fid
    assert doc.cik == "0000123456"
    assert doc.accession == "0000123456-23-000001"
    assert doc.sha256 == sha256_bytes(body)
    assert doc.byte_len == len(body)
    assert doc.content_type == "text/html"
    assert doc.data_quality_flag is None


def test_get_doc_records_data_quality_flag(isolated_store: Path) -> None:
    fid = _make_filing(
        isolated_store,
        "0001024401",
        "0001024401-01-500010",
        body=b"SGML-ish",
        ext=".txt",
        data_quality_flag="pre_ixbrl_sgml",
    )
    doc = get_doc(fid)
    assert doc.data_quality_flag == "pre_ixbrl_sgml"
    assert doc.content_type == "text/plain"


def test_get_doc_missing_raises(isolated_store: Path) -> None:
    with pytest.raises(StoreError) as ei:
        get_doc("0000999999/0000999999-99-999999")
    assert ei.value.reason == "not_found"


def test_get_doc_hash_mismatch_is_loud(isolated_store: Path) -> None:
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000002", body=b"original")
    # Silently corrupt the primary document without updating meta.
    cik, accession = fid.split("/")
    (isolated_store / cik / accession / "primary_document.htm").write_bytes(b"tampered")
    with pytest.raises(StoreError) as ei:
        get_doc(fid)
    assert ei.value.reason == "hash_mismatch"
    assert ei.value.filing_id == fid


def test_get_doc_invalid_doc_id(isolated_store: Path) -> None:
    with pytest.raises(StoreError) as ei:
        get_doc("")
    assert ei.value.reason == "invalid_doc_id"


def test_get_doc_rejects_locator_separator(isolated_store: Path) -> None:
    with pytest.raises(StoreError) as ei:
        get_doc("cik::accession")
    assert ei.value.reason == "invalid_doc_id"


def test_get_doc_bad_meta_json(isolated_store: Path) -> None:
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000003", body=b"x")
    cik, accession = fid.split("/")
    (isolated_store / cik / accession / "meta.json").write_text("not json{", encoding="utf-8")
    with pytest.raises(StoreError) as ei:
        get_doc(fid)
    assert ei.value.reason == "meta_invalid_json"


def test_get_doc_meta_missing_sha256(isolated_store: Path) -> None:
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000004", body=b"x")
    cik, accession = fid.split("/")
    (isolated_store / cik / accession / "meta.json").write_text(
        json.dumps({"primary_document_ext": ".htm", "fetched_at": "2023-01-01T00:00:00Z"}),
        encoding="utf-8",
    )
    with pytest.raises(StoreError) as ei:
        get_doc(fid)
    assert ei.value.reason == "meta_missing_sha256"


# --- get_doc_bytes / get_doc_text ---------------------------------------


def test_get_doc_bytes_returns_raw(isolated_store: Path) -> None:
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000005", body=b"xyzzy")
    assert get_doc_bytes(fid) == b"xyzzy"


def test_get_doc_text_decodes_utf8(isolated_store: Path) -> None:
    fid = _make_filing(
        isolated_store,
        "0000123456",
        "0000123456-23-000006",
        body="café\n".encode("utf-8"),
        ext=".txt",
    )
    assert get_doc_text(fid).strip() == "café"


def test_get_doc_text_tolerates_non_utf8_bytes(isolated_store: Path) -> None:
    body = b"\xff\xfe header" + b"\n" + b"OK"
    fid = _make_filing(
        isolated_store, "0000123456", "0000123456-23-000007", body=body, ext=".txt"
    )
    text = get_doc_text(fid)
    assert "OK" in text


def test_get_doc_bytes_hash_mismatch_is_loud(isolated_store: Path) -> None:
    fid = _make_filing(isolated_store, "0000123456", "0000123456-23-000008", body=b"abc")
    cik, accession = fid.split("/")
    (isolated_store / cik / accession / "primary_document.htm").write_bytes(b"different")
    with pytest.raises(StoreError) as ei:
        get_doc_bytes(fid)
    assert ei.value.reason == "hash_mismatch"


# --- list_filings -------------------------------------------------------


def test_list_filings_empty(isolated_store: Path) -> None:
    assert list_filings() == []


def test_list_filings_walks_both_levels(isolated_store: Path) -> None:
    _make_filing(isolated_store, "0000111111", "0000111111-23-000001", body=b"a")
    _make_filing(isolated_store, "0000111111", "0000111111-22-000001", body=b"b")
    _make_filing(isolated_store, "0000222222", "0000222222-23-000001", body=b"c")
    docs = list_filings()
    assert len(docs) == 3
    # Deterministic ordering: sorted by cik then accession
    assert [d.doc_id for d in docs] == [
        "0000111111/0000111111-22-000001",
        "0000111111/0000111111-23-000001",
        "0000222222/0000222222-23-000001",
    ]


def test_list_filings_propagates_corruption(isolated_store: Path) -> None:
    _make_filing(isolated_store, "0000333333", "0000333333-23-000001", body=b"fine")
    fid = _make_filing(isolated_store, "0000333333", "0000333333-23-000002", body=b"fine2")
    cik, accession = fid.split("/")
    (isolated_store / cik / accession / "primary_document.htm").write_bytes(b"CORRUPTED")
    with pytest.raises(StoreError) as ei:
        list_filings()
    assert ei.value.reason == "hash_mismatch"
