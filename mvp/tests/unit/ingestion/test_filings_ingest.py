"""Unit tests for ``mvp.ingestion.filings_ingest``.

Hermetic — uses ``httpx.MockTransport`` for the EDGAR client and
monkeypatches the module's data-directory constants onto per-test temp
paths, so no test ever touches the real ``data/`` tree.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from mvp.ingestion import filings_ingest
from mvp.ingestion.filings_ingest import (
    FilingRef,
    IngestResult,
    ingest_filing,
    sample_filings,
)
from mvp.lib.edgar import EdgarClient
from mvp.lib.errors import IngestionError


# -- Fixtures -------------------------------------------------------------


@pytest.fixture
def isolated_data_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point filings_ingest's module-level paths at ``tmp_path/data``."""
    data = tmp_path / "data"
    filings = data / "filings"
    manifest = data / "manifest.jsonl"
    monkeypatch.setattr(filings_ingest, "_DATA_DIR", data)
    monkeypatch.setattr(filings_ingest, "_FILINGS_DIR", filings)
    monkeypatch.setattr(filings_ingest, "_MANIFEST_PATH", manifest)
    return data


def _mk_client(handler: Any) -> EdgarClient:
    return EdgarClient(transport=httpx.MockTransport(handler))


def _read_manifest(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "manifest.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# -- Catalogue sanity -----------------------------------------------------


def test_sample_filings_size_and_shape() -> None:
    filings = sample_filings()
    assert len(filings) == 10  # 5 issuers × 2 years per §3 success criteria
    assert len({(f.cik, f.accession) for f in filings}) == 10
    for f in filings:
        assert isinstance(f, FilingRef)
        assert f.cik.isdigit() and len(f.cik) == 10
        assert f.source_url.startswith("https://www.sec.gov/Archives/edgar/data/")


# -- Happy path -----------------------------------------------------------


def test_happy_path_writes_file_meta_and_manifest(
    isolated_data_dir: Path,
) -> None:
    ref = sample_filings()[4]  # Apple FY2023 (iXBRL, no data-quality flag)
    payload = b"<html>apple 10-K body</html>"

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ref.source_url
        return httpx.Response(200, content=payload)

    with _mk_client(handler) as client:
        result = ingest_filing(ref.cik, ref.accession, client=client)

    assert isinstance(result, IngestResult)
    assert result.was_cached is False
    assert result.sha256 == filings_ingest.sha256_bytes(payload)  # type: ignore[attr-defined]

    filing_dir = isolated_data_dir / "filings" / ref.cik / ref.accession
    primary = filing_dir / "primary_document.htm"
    meta = filing_dir / "meta.json"
    assert primary.exists()
    assert primary.read_bytes() == payload

    meta_obj = json.loads(meta.read_text())
    assert meta_obj["cik"] == ref.cik
    assert meta_obj["accession_number"] == ref.accession
    assert meta_obj["source_url"] == ref.source_url
    assert meta_obj["sha256"] == result.sha256
    assert meta_obj["size_bytes"] == len(payload)
    assert "data_quality_flag" not in meta_obj  # iXBRL filing

    events = _read_manifest(isolated_data_dir)
    assert len(events) == 1
    assert events[0]["event"] == "filing_ingested"
    assert events[0]["cik"] == ref.cik
    assert events[0]["accession"] == ref.accession
    assert events[0]["sha256"] == result.sha256


def test_pre_ixbrl_accession_gets_flag(isolated_data_dir: Path) -> None:
    # Enron FY2000 — first filing in the catalogue; pre-iXBRL SGML.
    ref = sample_filings()[0]
    payload = b"<SEC-DOCUMENT>Enron 10-K SGML</SEC-DOCUMENT>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    with _mk_client(handler) as client:
        result = ingest_filing(ref.cik, ref.accession, client=client)

    assert result.data_quality_flag == "pre_ixbrl_sgml"

    meta = isolated_data_dir / "filings" / ref.cik / ref.accession / "meta.json"
    meta_obj = json.loads(meta.read_text())
    assert meta_obj["data_quality_flag"] == "pre_ixbrl_sgml"


def test_enron_1999_sgml_txt_ingested_as_is(isolated_data_dir: Path) -> None:
    # BUILD_REFS.md §1.1: EDGAR primaryDocument is blank for this accession;
    # the accession-named .txt is the single SGML submission and must be
    # stored as-is.
    ref = next(
        f for f in sample_filings() if f.accession == "0001024401-00-000002"
    )
    assert ref.primary_document.endswith(".txt")
    payload = b"<SEC-DOCUMENT>1024401-00-000002 SGML</SEC-DOCUMENT>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    with _mk_client(handler) as client:
        result = ingest_filing(ref.cik, ref.accession, client=client)

    assert result.primary_document_ext == ".txt"
    primary = isolated_data_dir / "filings" / ref.cik / ref.accession / "primary_document.txt"
    assert primary.exists()
    assert primary.read_bytes() == payload
    assert result.data_quality_flag == "pre_ixbrl_sgml"


# -- Idempotence ----------------------------------------------------------


def test_second_call_returns_cached_and_skips_download(
    isolated_data_dir: Path,
) -> None:
    ref = sample_filings()[4]
    payload = b"<html>apple body</html>"
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=payload)

    with _mk_client(handler) as client:
        first = ingest_filing(ref.cik, ref.accession, client=client)
        second = ingest_filing(ref.cik, ref.accession, client=client)

    assert len(calls) == 1  # second call is cached
    assert first.was_cached is False
    assert second.was_cached is True
    assert first.sha256 == second.sha256

    events = _read_manifest(isolated_data_dir)
    assert [e["event"] for e in events] == [
        "filing_ingested",
        "filing_skipped_already_ingested",
    ]


# -- Error paths ----------------------------------------------------------


def test_unknown_filing_raises(isolated_data_dir: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should not reach network for unknown filing")

    with _mk_client(handler) as client:
        with pytest.raises(IngestionError) as exc:
            ingest_filing("0000999999", "9999999999-99-999999", client=client)
    assert exc.value.reason == "unknown_filing"


def test_empty_body_raises(isolated_data_dir: Path) -> None:
    ref = sample_filings()[4]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"")

    with _mk_client(handler) as client:
        with pytest.raises(IngestionError) as exc:
            ingest_filing(ref.cik, ref.accession, client=client)
    assert exc.value.reason == "size_mismatch"


def test_hash_mismatch_on_disk_raises(isolated_data_dir: Path) -> None:
    ref = sample_filings()[4]
    payload = b"<html>body</html>"

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=payload)

    with _mk_client(handler) as client:
        ingest_filing(ref.cik, ref.accession, client=client)

    # Silently corrupt the file on disk.
    primary = (
        isolated_data_dir / "filings" / ref.cik / ref.accession / "primary_document.htm"
    )
    primary.write_bytes(b"<html>TAMPERED</html>")

    with _mk_client(handler) as client:
        with pytest.raises(IngestionError) as exc:
            ingest_filing(ref.cik, ref.accession, client=client)
    assert exc.value.reason == "hash_mismatch"


def test_malformed_meta_json_raises(isolated_data_dir: Path) -> None:
    ref = sample_filings()[4]
    # Stage the primary doc and a broken meta.json manually.
    filing_dir = isolated_data_dir / "filings" / ref.cik / ref.accession
    filing_dir.mkdir(parents=True)
    (filing_dir / "primary_document.htm").write_bytes(b"x")
    (filing_dir / "meta.json").write_text("{not valid json")

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should fail before network")

    with _mk_client(handler) as client:
        with pytest.raises(IngestionError) as exc:
            ingest_filing(ref.cik, ref.accession, client=client)
    assert exc.value.reason == "meta_invalid_json"


def test_meta_missing_sha256_raises(isolated_data_dir: Path) -> None:
    ref = sample_filings()[4]
    filing_dir = isolated_data_dir / "filings" / ref.cik / ref.accession
    filing_dir.mkdir(parents=True)
    (filing_dir / "primary_document.htm").write_bytes(b"x")
    (filing_dir / "meta.json").write_text(json.dumps({"cik": ref.cik}))

    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        raise AssertionError("should fail before network")

    with _mk_client(handler) as client:
        with pytest.raises(IngestionError) as exc:
            ingest_filing(ref.cik, ref.accession, client=client)
    assert exc.value.reason == "meta_missing_sha256"


# -- Retry logic (verifies lib/edgar retry is exercised) ------------------


def test_429_then_success_via_edgar_retry(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ref = sample_filings()[4]
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, content=b"<html>ok</html>")

    # Don't actually sleep during retry backoff.
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with _mk_client(handler) as client:
        result = ingest_filing(ref.cik, ref.accession, client=client)
    assert len(attempts) == 2
    assert result.was_cached is False


def test_503_exhausts_retries_and_surfaces_edgar_error(
    isolated_data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from mvp.lib.errors import EdgarHttpError

    ref = sample_filings()[4]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"down")

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with _mk_client(handler) as client:
        with pytest.raises(EdgarHttpError) as exc:
            ingest_filing(ref.cik, ref.accession, client=client)
    assert exc.value.status_code == 503


# -- CLI integration ------------------------------------------------------


def test_cli_single_mode_prints_json(
    isolated_data_dir: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ref = sample_filings()[4]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>apple</html>")

    # Force the CLI to use our mock-transport client rather than a real one.
    class _FakeCtor:
        def __init__(self, *a: Any, **kw: Any) -> None:
            self._c = EdgarClient(transport=httpx.MockTransport(handler))

        def __enter__(self) -> EdgarClient:
            return self._c

        def __exit__(self, *exc: object) -> None:
            self._c.close()

    monkeypatch.setattr(filings_ingest, "EdgarClient", _FakeCtor)

    rc = filings_ingest.main(
        ["--cik", ref.cik, "--accession", ref.accession]
    )
    assert rc == 0

    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["cik"] == ref.cik
    assert payload["accession_number"] == ref.accession
