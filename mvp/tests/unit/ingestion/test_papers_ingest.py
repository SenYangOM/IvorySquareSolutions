"""Unit tests for ``mvp.ingestion.papers_ingest``.

Hermetic — uses ``httpx.MockTransport`` to serve a fabricated PDF. The
expected sha256 is derived from the fabricated bytes at test time and
monkeypatched onto the module's sample-paper catalogue so the
body-vs-pinned hash check passes.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pymupdf  # type: ignore[import-untyped]
import pytest

from mvp.ingestion import papers_ingest
from mvp.ingestion.papers_ingest import (
    PaperIngestResult,
    PaperRef,
    ingest_paper,
    sample_papers,
)
from mvp.lib.errors import IngestionError
from mvp.lib.hashing import sha256_bytes


# -- Helpers --------------------------------------------------------------


def _make_pdf_bytes(abstract_text: str) -> bytes:
    """Generate a minimal 1-page PDF with the given text on page 1."""
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((72, 72), abstract_text, fontsize=12)
    buf = doc.tobytes()
    doc.close()
    return buf


@pytest.fixture
def isolated_paper_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    data = tmp_path / "data"
    papers = data / "papers"
    manifest = data / "manifest.jsonl"
    monkeypatch.setattr(papers_ingest, "_DATA_DIR", data)
    monkeypatch.setattr(papers_ingest, "_PAPERS_DIR", papers)
    monkeypatch.setattr(papers_ingest, "_MANIFEST_PATH", manifest)
    return data


@pytest.fixture
def fake_paper(monkeypatch: pytest.MonkeyPatch) -> tuple[PaperRef, bytes]:
    """Replace the real sample-paper catalogue with a one-entry fake."""
    body = _make_pdf_bytes(
        "This paper studies earnings manipulation across 74 firms. Abstract body."
    )
    digest = sha256_bytes(body)
    ref = PaperRef(
        paper_id="fake_paper_2026",
        citation="Fake, A. (2026). Fake Paper. Journal of Testing.",
        source_url="https://example.com/fake.pdf",
        expected_sha256=digest,
    )
    monkeypatch.setattr(papers_ingest, "_SAMPLE_PAPERS", (ref,))
    monkeypatch.setattr(papers_ingest, "_SAMPLE_INDEX", {ref.paper_id: ref})
    return ref, body


def _read_manifest(data_dir: Path) -> list[dict[str, Any]]:
    path = data_dir / "manifest.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


# -- Catalogue sanity (on the real, un-monkeypatched catalogue) -----------


def test_real_catalogue_has_two_papers() -> None:
    papers = sample_papers()
    assert len(papers) == 2
    ids = {p.paper_id for p in papers}
    assert ids == {"beneish_1999", "altman_1968"}
    for p in papers:
        assert p.expected_sha256 and len(p.expected_sha256) == 64


# -- Happy path -----------------------------------------------------------


def test_happy_path_writes_pdf_meta_abstract_and_manifest(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, body = fake_paper

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == ref.source_url
        return httpx.Response(
            200, content=body, headers={"Content-Type": "application/pdf"}
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        result = ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()

    assert isinstance(result, PaperIngestResult)
    assert result.was_cached is False
    assert result.sha256 == ref.expected_sha256

    pdf_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.pdf"
    meta_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.meta.json"
    abstract_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.abstract.txt"
    assert pdf_path.exists() and pdf_path.read_bytes() == body
    assert meta_path.exists()
    assert abstract_path.exists()

    meta_obj = json.loads(meta_path.read_text())
    assert meta_obj["paper_id"] == ref.paper_id
    assert meta_obj["sha256"] == ref.expected_sha256
    assert meta_obj["licensing_status"] == "mirrored_pending_review"

    abstract_text = abstract_path.read_text()
    assert "earnings manipulation" in abstract_text
    assert len(abstract_text) <= 2000

    events = _read_manifest(isolated_paper_dir)
    assert len(events) == 1
    assert events[0]["event"] == "paper_ingested"
    assert events[0]["paper_id"] == ref.paper_id


# -- Idempotence ----------------------------------------------------------


def test_second_call_returns_cached(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, body = fake_paper
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, content=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        first = ingest_paper(ref.paper_id, client=client)
        second = ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()

    assert len(calls) == 1
    assert first.was_cached is False
    assert second.was_cached is True

    events = _read_manifest(isolated_paper_dir)
    assert [e["event"] for e in events] == [
        "paper_ingested",
        "paper_skipped_already_ingested",
    ]


# -- Error paths ----------------------------------------------------------


def test_unknown_paper_raises(isolated_paper_dir: Path) -> None:
    with pytest.raises(IngestionError) as exc:
        ingest_paper("not_a_real_paper")
    assert exc.value.reason == "unknown_paper"


def test_expected_hash_mismatch_raises(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, _ = fake_paper

    # Serve *different* bytes than the catalogue expected.
    swapped_body = _make_pdf_bytes("Different abstract.")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=swapped_body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IngestionError) as exc:
            ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()
    assert exc.value.reason == "expected_hash_mismatch"


def test_hash_mismatch_on_disk_raises(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, body = fake_paper

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()

    pdf_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntampered\n%%EOF\n")

    # Even without a client the cache-probe path runs first and must raise.
    with pytest.raises(IngestionError) as exc:
        ingest_paper(ref.paper_id)
    assert exc.value.reason == "hash_mismatch"


def test_http_error_raises_typed(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, _ = fake_paper

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IngestionError) as exc:
            ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()
    assert exc.value.reason == "http_error"


def test_transport_error_wrapped(
    isolated_paper_dir: Path, fake_paper: tuple[PaperRef, bytes]
) -> None:
    ref, _ = fake_paper

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(IngestionError) as exc:
            ingest_paper(ref.paper_id, client=client)
    finally:
        client.close()
    assert exc.value.reason == "http_error"


# -- ingest_local_paper (post-MVP paper_examples corpus) -----------------


@pytest.fixture
def fake_local_paper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, bytes, Path]:
    """Replace the local paper_examples catalogue with a one-entry fake
    whose source file is under ``tmp_path``.

    Returns ``(LocalPaperRef, body, source_path)``.
    """
    from mvp.ingestion.papers_ingest import LocalPaperRef

    body = _make_pdf_bytes(
        "Fundamentals from text: attention-based analysis of 10-K filings."
    )
    digest = sha256_bytes(body)
    source_path = tmp_path / "fundamentals_text_fixture.pdf"
    source_path.write_bytes(body)
    ref = LocalPaperRef(
        paper_id="fake_local_paper",
        citation="Fake-Local, A. (2026). Fake Local Paper. Journal of Testing.",
        local_source_path=str(source_path),
        expected_sha256=digest,
        licensing_status="unknown_pending_review",
        source_description="Synthetic test fixture for ingest_local_paper.",
    )
    monkeypatch.setattr(papers_ingest, "_PAPER_EXAMPLES", (ref,))
    monkeypatch.setattr(papers_ingest, "_PAPER_EXAMPLES_INDEX", {ref.paper_id: ref})
    return ref, body, source_path


def test_local_paper_catalogue_registers_fundamentals_text() -> None:
    """The real post-MVP catalogue must register the first paper_examples entry."""
    from mvp.ingestion.papers_ingest import paper_examples

    entries = paper_examples()
    assert len(entries) >= 1
    fundamentals = next(
        (p for p in entries if p.paper_id == "fundamentals_text"), None
    )
    assert fundamentals is not None
    assert fundamentals.expected_sha256 == (
        "0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5"
    )
    assert fundamentals.licensing_status == "unknown_pending_review"
    assert fundamentals.local_source_path.endswith("fundamentals_text.pdf")


def test_local_paper_catalogue_registers_kim_2024_context() -> None:
    """Paper 2 of the post-MVP corpus must be registered with its pinned sha."""
    from mvp.ingestion.papers_ingest import paper_examples

    entries = paper_examples()
    paper2 = next(
        (
            p
            for p in entries
            if p.paper_id == "kim_2024_context_based_interpretation"
        ),
        None,
    )
    assert paper2 is not None
    assert paper2.expected_sha256 == (
        "013d9bbcd45ec4636dc3427561770c6489a29aa92e1b116281206344b442f533"
    )
    assert paper2.licensing_status == "unknown_pending_review"
    # Filename uses U+2010 hyphen (Wiley copy-paste artefact); confirm the
    # path in the catalogue carries that exact codepoint, not U+002D.
    assert "Context\u2010Based" in paper2.local_source_path
    assert "Journal of Accounting Research" in paper2.citation


def test_ingest_local_paper_happy_path(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    ref, body, source_path = fake_local_paper
    result = ingest_local_paper(ref.paper_id)

    assert isinstance(result, PaperIngestResult)
    assert result.was_cached is False
    assert result.sha256 == ref.expected_sha256
    assert result.source_url == f"file://{source_path}"
    assert result.licensing_status == "unknown_pending_review"

    pdf_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.pdf"
    meta_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.meta.json"
    abstract_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.abstract.txt"
    assert pdf_path.read_bytes() == body
    meta_obj = json.loads(meta_path.read_text())
    assert meta_obj["paper_id"] == ref.paper_id
    assert meta_obj["source_url"] == f"file://{source_path}"
    assert meta_obj["licensing_status"] == "unknown_pending_review"
    assert "Synthetic test fixture" in meta_obj["source_description"]
    assert abstract_path.exists()

    events = _read_manifest(isolated_paper_dir)
    assert len(events) == 1
    assert events[0]["event"] == "paper_ingested"
    assert events[0]["source"] == "local_paper_examples"


def test_ingest_local_paper_is_idempotent(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    ref, _, _ = fake_local_paper
    first = ingest_local_paper(ref.paper_id)
    second = ingest_local_paper(ref.paper_id)
    assert first.was_cached is False
    assert second.was_cached is True
    assert second.sha256 == first.sha256

    events = _read_manifest(isolated_paper_dir)
    assert [e["event"] for e in events] == [
        "paper_ingested",
        "paper_skipped_already_ingested",
    ]


def test_ingest_local_paper_unknown_id_raises(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    with pytest.raises(IngestionError) as exc:
        ingest_local_paper("not_registered_paper")
    assert exc.value.reason == "unknown_paper"


def test_ingest_local_paper_missing_source_raises(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    ref, _, source_path = fake_local_paper
    source_path.unlink()  # delete the local source file
    with pytest.raises(IngestionError) as exc:
        ingest_local_paper(ref.paper_id)
    assert exc.value.reason == "local_source_missing"


def test_ingest_local_paper_expected_hash_mismatch_raises(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    ref, _, source_path = fake_local_paper
    # Swap the source file out for different bytes — sha256 will no
    # longer match the pinned expected_sha256.
    source_path.write_bytes(_make_pdf_bytes("Different content."))
    with pytest.raises(IngestionError) as exc:
        ingest_local_paper(ref.paper_id)
    assert exc.value.reason == "expected_hash_mismatch"


def test_ingest_local_paper_on_disk_hash_mismatch_raises(
    isolated_paper_dir: Path,
    fake_local_paper: tuple[Any, bytes, Path],
) -> None:
    from mvp.ingestion.papers_ingest import ingest_local_paper

    ref, _, _ = fake_local_paper
    ingest_local_paper(ref.paper_id)
    # Tamper with the cached on-disk PDF.
    pdf_path = isolated_paper_dir / "papers" / f"{ref.paper_id}.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntampered\n%%EOF\n")
    with pytest.raises(IngestionError) as exc:
        ingest_local_paper(ref.paper_id)
    assert exc.value.reason == "hash_mismatch"
