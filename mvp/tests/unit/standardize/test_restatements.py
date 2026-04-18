"""Unit tests for :mod:`mvp.standardize.restatements`.

Hermetic — builds a tiny doc store under ``tmp_path`` with two filings
sharing a fiscal-period-end (a restatement overlap) and one filing with
a unique fpe (no overlap).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from mvp.lib.errors import StoreError
from mvp.lib.hashing import sha256_bytes
from mvp.standardize import restatements as rs_mod
from mvp.standardize.restatements import RestatementRecord, detect_restatements
from mvp.store import doc_store


@pytest.fixture
def isolated_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    (data / "filings").mkdir(parents=True)
    monkeypatch.setattr(doc_store, "_DATA_DIR", data)
    monkeypatch.setattr(doc_store, "_FILINGS_DIR", data / "filings")
    monkeypatch.setattr(rs_mod, "_MVP_ROOT", tmp_path)
    monkeypatch.setattr(rs_mod, "_DATA_DIR", data)
    monkeypatch.setattr(rs_mod, "_FILINGS_DIR", data / "filings")
    monkeypatch.setattr(
        rs_mod,
        "_RESTATEMENT_LOG_PATH",
        data / "standardize_restatement_log.jsonl",
    )
    return data


def _write_filing(
    data: Path,
    cik: str,
    accession: str,
    *,
    body: bytes = b"x",
    fpe: str = "2023-12-31",
    filed_at: str = "2024-02-15",
) -> str:
    fd = data / "filings" / cik / accession
    fd.mkdir(parents=True, exist_ok=True)
    (fd / "primary_document.htm").write_bytes(body)
    meta: dict[str, Any] = {
        "cik": cik,
        "accession_number": accession,
        "filing_type": "10-K",
        "fiscal_period_end": fpe,
        "filed_at": filed_at,
        "source_url": "https://example.invalid/",
        "primary_document": "p.htm",
        "primary_document_ext": ".htm",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(body),
        "size_bytes": len(body),
    }
    (fd / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return f"{cik}/{accession}"


def test_no_overlap_returns_empty(isolated_tree: Path) -> None:
    cik = "0000123456"
    _write_filing(isolated_tree, cik, "0000123456-23-000001", fpe="2023-12-31", filed_at="2024-02-15")
    _write_filing(isolated_tree, cik, "0000123456-22-000001", fpe="2022-12-31", filed_at="2023-02-15")
    assert detect_restatements(cik) == []


def test_overlap_emits_record(isolated_tree: Path) -> None:
    cik = "0000123456"
    # Original FY2022 filed 2023-02-15.
    _write_filing(isolated_tree, cik, "0000123456-23-000001", fpe="2022-12-31", filed_at="2023-02-15")
    # Amended FY2022 10-K/A filed 2024-01-05 — same fpe as above.
    _write_filing(isolated_tree, cik, "0000123456-24-000005", fpe="2022-12-31", filed_at="2024-01-05")

    recs = detect_restatements(cik)
    assert len(recs) == 1
    r = recs[0]
    assert isinstance(r, RestatementRecord)
    assert r.earlier_filing_id == f"{cik}/0000123456-23-000001"
    assert r.later_filing_id == f"{cik}/0000123456-24-000005"
    assert str(r.fiscal_period_end) == "2022-12-31"
    assert r.notes == "overlap_detected"


def test_overlap_is_logged(isolated_tree: Path) -> None:
    cik = "0000123456"
    _write_filing(isolated_tree, cik, "0000123456-23-000001", fpe="2022-12-31", filed_at="2023-02-15")
    _write_filing(isolated_tree, cik, "0000123456-24-000005", fpe="2022-12-31", filed_at="2024-01-05")
    detect_restatements(cik)
    log_path = isolated_tree / "standardize_restatement_log.jsonl"
    assert log_path.exists()
    lines = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    assert len(lines) == 1
    assert lines[0]["earlier_filing_id"].endswith("0000123456-23-000001")


def test_no_log_written_when_no_overlap(isolated_tree: Path) -> None:
    cik = "0000123456"
    _write_filing(isolated_tree, cik, "0000123456-23-000001", fpe="2023-12-31", filed_at="2024-02-15")
    detect_restatements(cik)
    assert not (isolated_tree / "standardize_restatement_log.jsonl").exists()


def test_filters_to_cik(isolated_tree: Path) -> None:
    cik_a = "0000111111"
    cik_b = "0000222222"
    _write_filing(isolated_tree, cik_a, "0000111111-23-000001", fpe="2022-12-31", filed_at="2023-02-15")
    _write_filing(isolated_tree, cik_b, "0000222222-24-000001", fpe="2022-12-31", filed_at="2024-01-15")
    assert detect_restatements(cik_a) == []  # different CIKs never overlap
    assert detect_restatements(cik_b) == []


def test_bad_cik_raises_store_error(isolated_tree: Path) -> None:
    with pytest.raises(StoreError) as ei:
        detect_restatements("abc")
    assert ei.value.reason == "invalid_cik"
