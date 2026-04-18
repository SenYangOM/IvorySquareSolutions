"""L0 academic-paper ingestion.

Downloads the two MVP source papers (Beneish 1999, Altman 1968) from
publicly mirrored PDF URLs recorded in ``BUILD_REFS.md`` §3 into
``data/papers/<paper_id>.pdf`` and writes a companion metadata JSON
(``<paper_id>.meta.json``) plus an extracted first-page abstract
(``<paper_id>.abstract.txt``).

Paper mirrors are hosted off-sec.gov, so this module uses ``httpx.Client``
directly rather than :class:`mvp.lib.edgar.EdgarClient` — EDGAR's client is
scoped to sec.gov hosts only. The User-Agent is still declared as a
courtesy to the mirror host.

Per ``mvp_build_goal.md`` §13 decision 4, every paper's meta.json records
``licensing_status: "mirrored_pending_review"`` — the mirror copy is fine
for MVP paper-replication work, but a licensing review is required before
any redistribution.

Idempotence semantics match :mod:`mvp.ingestion.filings_ingest`: a second
call whose on-disk PDF matches the recorded sha256 returns
``was_cached=True`` and logs ``event: "paper_skipped_already_ingested"``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel, Field

from mvp.lib.errors import IngestionError
from mvp.lib.hashing import sha256_bytes, sha256_file
from mvp.lib.pdf_io import extract_text

# -- Paths ---------------------------------------------------------------

_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_PAPERS_DIR = _DATA_DIR / "papers"
_MANIFEST_PATH = _DATA_DIR / "manifest.jsonl"

_DEFAULT_USER_AGENT = "Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"

# Abstract extraction: take the first 2000 chars of page-1 text, per spec.
# Page 1 of both mirrors contains the abstract block; the cap keeps the
# file small and avoids accidentally including the introduction.
_ABSTRACT_CHAR_LIMIT = 2000


# -- Reference data ------------------------------------------------------


class PaperRef(BaseModel):
    """A single sample paper's canonical reference from BUILD_REFS.md §3."""

    model_config = {"frozen": True}

    paper_id: str
    citation: str
    source_url: str
    expected_sha256: str  # hash recorded in BUILD_REFS.md for cross-check


_SAMPLE_PAPERS: tuple[PaperRef, ...] = (
    PaperRef(
        paper_id="beneish_1999",
        citation=(
            "Beneish, M. D. (1999). The Detection of Earnings Manipulation. "
            "Financial Analysts Journal, 55(5), 24–36."
        ),
        source_url="https://www.calctopia.com/papers/beneish1999.pdf",
        expected_sha256=(
            "78b2f0143770c9c06871ba8e8d8fb764fc95a4dd379ae37e1c301d16c42faffe"
        ),
    ),
    PaperRef(
        paper_id="altman_1968",
        citation=(
            "Altman, E. I. (1968). Financial Ratios, Discriminant Analysis "
            "and the Prediction of Corporate Bankruptcy. "
            "The Journal of Finance, 23(4), 589–609."
        ),
        source_url="https://www.calctopia.com/papers/Altman1968.pdf",
        expected_sha256=(
            "34ba13a102ee4f1767762786e2720e9c6211e4d3d9252fb45856ca45cb21dd99"
        ),
    ),
)

_SAMPLE_INDEX: dict[str, PaperRef] = {p.paper_id: p for p in _SAMPLE_PAPERS}


# -- Post-MVP paper_examples corpus --------------------------------------
#
# The paper-to-skill workstream (post-MVP) processes user-supplied PDFs
# under ``/home/iv/research/Proj_ongoing/paper_examples/``. Those files
# are **local-only**: there is no remote mirror URL, no HTTP fetch. They
# are ingested via :func:`ingest_local_paper` instead of
# :func:`ingest_paper`. Each ``LocalPaperRef`` pins a ``local_source_path``
# and a ``licensing_status`` — the latter is ``unknown_pending_review``
# by default because the user-provided PDFs have not been through the
# §13-decision-4 licensing review that the two MVP papers went through.


class LocalPaperRef(BaseModel):
    """A paper sourced from a local file (post-MVP paper_examples corpus).

    Unlike :class:`PaperRef`, a ``LocalPaperRef`` does not reach out over
    HTTP — the PDF bytes are already on the local filesystem at
    ``local_source_path``. The ``expected_sha256`` is computed from the
    on-disk source at registration time (see
    ``workshop/paper_to_skill/extract_paper.py``'s ``sha256_of``
    helper) and pinned into this catalogue so a silent file swap under
    ``paper_examples/`` gets caught on re-ingest.
    """

    model_config = {"frozen": True}

    paper_id: str
    citation: str
    local_source_path: str
    expected_sha256: str
    licensing_status: Literal[
        "unknown_pending_review", "mirrored_pending_review"
    ] = "unknown_pending_review"
    source_description: str = ""


_PAPER_EXAMPLES: tuple[LocalPaperRef, ...] = (
    LocalPaperRef(
        paper_id="fundamentals_text",
        citation=(
            "Kim, A. G., Muhn, M., Nikolaev, V. V., & Zhang, Y. "
            "(November 2024). Learning Fundamentals from Text. "
            "University of Chicago Booth School of Business Working Paper."
        ),
        local_source_path=(
            "/home/iv/research/Proj_ongoing/paper_examples/fundamentals_text.pdf"
        ),
        expected_sha256=(
            "0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5"
        ),
        licensing_status="unknown_pending_review",
        source_description=(
            "User-provided PDF under paper_examples/. Origin: Chicago Booth "
            "working paper, PDF metadata shows LaTeX + pdfTeX, creation "
            "date 2026-04-12. Licensing status pending review — the PDF "
            "appears to be a pre-publication working draft circulated by "
            "the authors; verify distribution rights before any external use."
        ),
    ),
    LocalPaperRef(
        paper_id="kim_2024_context_based_interpretation",
        citation=(
            "Kim, A. G., & Nikolaev, V. V. (2024). "
            "Context-Based Interpretation of Financial Information. "
            "Journal of Accounting Research, accepted 31 October 2024. "
            "DOI: 10.1111/1475-679X.12593."
        ),
        local_source_path=(
            "/home/iv/research/Proj_ongoing/paper_examples/"
            "J of Accounting Research - 2024 - KIM - Context\u2010Based "
            "Interpretation of Financial Information.pdf"
        ),
        expected_sha256=(
            "013d9bbcd45ec4636dc3427561770c6489a29aa92e1b116281206344b442f533"
        ),
        licensing_status="unknown_pending_review",
        source_description=(
            "User-provided PDF under paper_examples/. Origin: Journal of "
            "Accounting Research, Wiley Online Library, accepted 2024-10-31, "
            "DOI 10.1111/1475-679X.12593. Filename uses the U+2010 hyphen "
            "rather than U+002D (Wiley copy-paste artefact). Licensing "
            "status pending review — the PDF appears to be a publisher-"
            "downloaded copy; check distribution rights before any external "
            "use."
        ),
    ),
    LocalPaperRef(
        paper_id="dekok_2024_gllm_nonanswers",
        citation=(
            "de Kok, T. (June 2024). ChatGPT for Textual Analysis? How to use "
            "Generative LLMs in Accounting Research. University of Washington "
            "working paper, SSRN 4429658."
        ),
        local_source_path=(
            "/home/iv/research/Proj_ongoing/paper_examples/ssrn-4429658.pdf"
        ),
        expected_sha256=(
            "2650e3e5c853a8ca1d7dae8e14622c64617e295e75b9d4407f0e84bccd79ba4a"
        ),
        licensing_status="unknown_pending_review",
        source_description=(
            "User-provided PDF under paper_examples/. Origin: SSRN working "
            "paper 4429658, dated June 2024, author Ties de Kok (UW). Case "
            "study classifies earnings-call non-answers via GLLMs; Online "
            "Appendix 3 Step 1 prints the full keyword list from Gow et al. "
            "(2021) as used as the rule-based non-answer filter. Licensing "
            "status pending review \u2014 the PDF appears to be an SSRN-"
            "downloaded working paper; a journal publication may follow."
        ),
    ),
    LocalPaperRef(
        paper_id="bernard_2025_information_acquisition",
        citation=(
            "Bernard, D., Cade, N. L., Connors, E. H., & de Kok, T. (2025). "
            "Descriptive evidence on small business managers' information "
            "choices. Review of Accounting Studies, 30, 3254-3294. "
            "DOI: 10.1007/s11142-025-09885-5."
        ),
        local_source_path=(
            "/home/iv/research/Proj_ongoing/paper_examples/"
            "s11142-025-09885-5.pdf"
        ),
        expected_sha256=(
            "1760a4c614f6051052beff0fad61587bdd344bea700f5205e24e5142399d8290"
        ),
        licensing_status="unknown_pending_review",
        source_description=(
            "User-provided PDF under paper_examples/. Origin: Review of "
            "Accounting Studies, Springer, accepted 2025-04-08 / published "
            "online 2025-06-04, DOI 10.1007/s11142-025-09885-5. Filename is "
            "the Springer-DOI-style identifier. Licensing status pending "
            "review — the PDF appears to be a publisher copy; check "
            "distribution rights before any external use."
        ),
    ),
    LocalPaperRef(
        paper_id="bernard_2025_gpt_complexity",
        citation=(
            "Bernard, D., Blankespoor, E., de Kok, T., & Toynbee, S. "
            "(December 2025). Using GPT to measure business complexity. "
            "Forthcoming, The Accounting Review. SSRN 4480309."
        ),
        local_source_path=(
            "/home/iv/research/Proj_ongoing/paper_examples/ssrn-4480309.pdf"
        ),
        expected_sha256=(
            "a4e82cafd4d51cdf22ede47dd29a8294c2ecc38c7da337f7874061630a0a6564"
        ),
        licensing_status="unknown_pending_review",
        source_description=(
            "User-provided PDF under paper_examples/. Origin: SSRN working "
            "paper 4480309, dated December 2025, forthcoming in The "
            "Accounting Review. Constructs a filing-level business-complexity "
            "measure from a fine-tuned Llama-3 8b that predicts iXBRL tags on "
            "footnote text; the paper's companion website (with model "
            "weights) is promised but not yet available at paper-onboarding "
            "time. Licensing status pending review \u2014 the PDF appears to "
            "be an SSRN-downloaded working paper; a journal publication is "
            "expected in due course."
        ),
    ),
)

_PAPER_EXAMPLES_INDEX: dict[str, LocalPaperRef] = {
    p.paper_id: p for p in _PAPER_EXAMPLES
}


# -- Public model --------------------------------------------------------


class PaperIngestResult(BaseModel):
    """Result of an ``ingest_paper`` or ``ingest_local_paper`` call.

    Mirrors the on-disk ``<paper_id>.meta.json`` 1:1, plus ``path``,
    ``abstract_path``, and ``was_cached``.
    """

    paper_id: str
    citation: str
    source_url: str
    path: str
    abstract_path: str
    fetched_at: str
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    size_bytes: int
    licensing_status: Literal[
        "mirrored_pending_review", "unknown_pending_review"
    ] = "mirrored_pending_review"
    was_cached: bool = False


# -- Public API ----------------------------------------------------------


def ingest_paper(
    paper_id: str,
    client: httpx.Client | None = None,
) -> PaperIngestResult:
    """Ingest a sample paper into ``data/papers/<paper_id>.{pdf,meta.json,abstract.txt}``.

    Parameters
    ----------
    paper_id:
        Snake-case stable identifier (``"beneish_1999"`` or
        ``"altman_1968"``).
    client:
        Optional :class:`httpx.Client`. When ``None`` a fresh client is
        constructed (and closed) inside this call.

    Returns
    -------
    PaperIngestResult

    Raises
    ------
    IngestionError
        - ``reason="unknown_paper"`` if ``paper_id`` is not a sample
          paper.
        - ``reason="hash_mismatch"`` if the PDF on disk differs from the
          recorded sha256.
        - ``reason="expected_hash_mismatch"`` if the freshly-downloaded
          body does not match the hash pinned in ``BUILD_REFS.md``. This
          guards against a mirror-source swap going unnoticed.
        - ``reason="http_error"`` on non-success HTTP status (wrapping
          the underlying :class:`httpx.HTTPError`).
        - ``reason="pdf_abstract_extract"`` if the abstract cannot be
          extracted from page 1 of the PDF.
    """
    ref = _SAMPLE_INDEX.get(paper_id)
    if ref is None:
        raise IngestionError(
            f"no sample paper registered for paper_id={paper_id!r}",
            reason="unknown_paper",
            target=paper_id,
        )

    pdf_path = _PAPERS_DIR / f"{paper_id}.pdf"
    meta_path = _PAPERS_DIR / f"{paper_id}.meta.json"
    abstract_path = _PAPERS_DIR / f"{paper_id}.abstract.txt"

    cached = _try_load_cached(ref, pdf_path, meta_path, abstract_path)
    if cached is not None:
        _append_manifest(
            {
                "event": "paper_skipped_already_ingested",
                "paper_id": paper_id,
                "path": str(pdf_path),
                "sha256": cached.sha256,
                "ingested_at": _utc_now_iso(),
            }
        )
        return cached

    owns_client = client is None
    active_client = (
        client
        if client is not None
        else httpx.Client(
            timeout=30.0,
            headers={"User-Agent": _DEFAULT_USER_AGENT, "Accept": "application/pdf"},
            follow_redirects=True,
        )
    )
    try:
        try:
            resp = active_client.get(ref.source_url)
        except httpx.HTTPError as exc:
            raise IngestionError(
                f"HTTP error fetching {ref.source_url}: {exc}",
                reason="http_error",
                target=ref.source_url,
            ) from exc
        if resp.status_code >= 400:
            raise IngestionError(
                f"HTTP {resp.status_code} fetching {ref.source_url}",
                reason="http_error",
                target=ref.source_url,
            )
        body = resp.content
    finally:
        if owns_client:
            active_client.close()

    if not body:
        raise IngestionError(
            f"empty body from {ref.source_url}",
            reason="size_mismatch",
            target=paper_id,
        )

    digest = sha256_bytes(body)
    if digest != ref.expected_sha256:
        raise IngestionError(
            (
                f"downloaded paper {paper_id} sha256 {digest} does not match "
                f"BUILD_REFS.md pinned {ref.expected_sha256} — mirror may have "
                "changed; investigate before re-running"
            ),
            reason="expected_hash_mismatch",
            target=paper_id,
        )

    _PAPERS_DIR.mkdir(parents=True, exist_ok=True)

    stage_pdf = pdf_path.with_suffix(".pdf.partial")
    stage_pdf.write_bytes(body)
    stage_pdf.replace(pdf_path)

    # Extract the abstract only after the PDF is durably on disk, because
    # pdf_io operates on a file path and not bytes.
    try:
        page1 = extract_text(pdf_path, page=1)
    except Exception as exc:
        # Keep the PDF and meta un-written so the next run retries cleanly.
        pdf_path.unlink(missing_ok=True)
        raise IngestionError(
            f"failed to extract abstract from {pdf_path}: {exc}",
            reason="pdf_abstract_extract",
            target=str(pdf_path),
        ) from exc

    abstract = page1[:_ABSTRACT_CHAR_LIMIT]

    stage_abs = abstract_path.with_suffix(".txt.partial")
    stage_abs.write_text(abstract, encoding="utf-8")
    stage_abs.replace(abstract_path)

    fetched_at = _utc_now_iso()
    meta: dict[str, object] = {
        "paper_id": paper_id,
        "citation": ref.citation,
        "source_url": ref.source_url,
        "fetched_at": fetched_at,
        "sha256": digest,
        "size_bytes": len(body),
        "licensing_status": "mirrored_pending_review",
        "abstract_path": abstract_path.name,
    }

    stage_meta = meta_path.with_suffix(".json.partial")
    stage_meta.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    stage_meta.replace(meta_path)

    _append_manifest(
        {
            "event": "paper_ingested",
            "paper_id": paper_id,
            "path": str(pdf_path),
            "sha256": digest,
            "ingested_at": fetched_at,
        }
    )

    return PaperIngestResult(
        paper_id=paper_id,
        citation=ref.citation,
        source_url=ref.source_url,
        path=str(pdf_path),
        abstract_path=str(abstract_path),
        fetched_at=fetched_at,
        sha256=digest,
        size_bytes=len(body),
        licensing_status="mirrored_pending_review",
        was_cached=False,
    )


def sample_papers() -> tuple[PaperRef, ...]:
    """Return the hardcoded Phase 1 sample-paper references."""
    return _SAMPLE_PAPERS


def paper_examples() -> tuple[LocalPaperRef, ...]:
    """Return the registered post-MVP ``paper_examples/`` corpus entries.

    Each entry is a local-file-sourced PDF under
    ``/home/iv/research/Proj_ongoing/paper_examples/`` that the
    paper-to-skill workstream processes one at a time. Use
    :func:`ingest_local_paper` to bring one into the mvp data store.
    """
    return _PAPER_EXAMPLES


def ingest_local_paper(paper_id: str) -> PaperIngestResult:
    """Ingest a ``paper_examples/`` corpus paper from its local file.

    Parallel to :func:`ingest_paper`, but reads bytes from
    ``local_source_path`` instead of fetching over HTTP. Writes the
    same three artifacts — ``<paper_id>.pdf``, ``<paper_id>.meta.json``,
    ``<paper_id>.abstract.txt`` — under ``data/papers/``, and appends a
    ``paper_ingested`` event to ``data/manifest.jsonl``. Idempotent:
    a second call whose on-disk PDF matches the pinned sha256 returns
    ``was_cached=True`` and logs ``paper_skipped_already_ingested``.

    Parameters
    ----------
    paper_id:
        Snake-case stable identifier registered in ``_PAPER_EXAMPLES``
        (e.g. ``"fundamentals_text"``).

    Returns
    -------
    PaperIngestResult
        The same shape as :func:`ingest_paper` returns, with
        ``source_url`` set to ``file://<absolute_local_source_path>`` so
        downstream code (manifests, skill provenance) can treat the
        field uniformly.

    Raises
    ------
    IngestionError
        - ``reason="unknown_paper"`` if ``paper_id`` is not in the
          local catalogue.
        - ``reason="local_source_missing"`` if ``local_source_path`` does
          not exist.
        - ``reason="expected_hash_mismatch"`` if the local file's sha256
          does not match the pinned ``expected_sha256`` — this guards
          against a silent file swap under ``paper_examples/``.
        - ``reason="hash_mismatch"`` if a cached on-disk copy at
          ``data/papers/<paper_id>.pdf`` no longer matches its recorded
          meta sha256.
        - ``reason="pdf_abstract_extract"`` if the first-page abstract
          cannot be extracted from the PDF.
    """
    ref = _PAPER_EXAMPLES_INDEX.get(paper_id)
    if ref is None:
        raise IngestionError(
            f"no paper_examples entry registered for paper_id={paper_id!r}",
            reason="unknown_paper",
            target=paper_id,
        )

    pdf_path = _PAPERS_DIR / f"{paper_id}.pdf"
    meta_path = _PAPERS_DIR / f"{paper_id}.meta.json"
    abstract_path = _PAPERS_DIR / f"{paper_id}.abstract.txt"

    source_path = Path(ref.local_source_path)
    source_url = f"file://{source_path}"

    cached = _try_load_cached_local(ref, pdf_path, meta_path, abstract_path, source_url)
    if cached is not None:
        _append_manifest(
            {
                "event": "paper_skipped_already_ingested",
                "paper_id": paper_id,
                "path": str(pdf_path),
                "sha256": cached.sha256,
                "ingested_at": _utc_now_iso(),
            }
        )
        return cached

    if not source_path.is_file():
        raise IngestionError(
            f"local source PDF not found at {source_path}",
            reason="local_source_missing",
            target=str(source_path),
        )
    body = source_path.read_bytes()

    if not body:
        raise IngestionError(
            f"local source PDF at {source_path} is empty",
            reason="size_mismatch",
            target=paper_id,
        )

    digest = sha256_bytes(body)
    if digest != ref.expected_sha256:
        raise IngestionError(
            (
                f"local paper {paper_id} at {source_path} sha256 {digest} "
                f"does not match pinned {ref.expected_sha256} — the source "
                "file under paper_examples/ may have been swapped; "
                "investigate before re-running"
            ),
            reason="expected_hash_mismatch",
            target=paper_id,
        )

    _PAPERS_DIR.mkdir(parents=True, exist_ok=True)

    stage_pdf = pdf_path.with_suffix(".pdf.partial")
    stage_pdf.write_bytes(body)
    stage_pdf.replace(pdf_path)

    try:
        page1 = extract_text(pdf_path, page=1)
    except Exception as exc:
        pdf_path.unlink(missing_ok=True)
        raise IngestionError(
            f"failed to extract abstract from {pdf_path}: {exc}",
            reason="pdf_abstract_extract",
            target=str(pdf_path),
        ) from exc

    abstract = page1[:_ABSTRACT_CHAR_LIMIT]

    stage_abs = abstract_path.with_suffix(".txt.partial")
    stage_abs.write_text(abstract, encoding="utf-8")
    stage_abs.replace(abstract_path)

    fetched_at = _utc_now_iso()
    meta: dict[str, object] = {
        "paper_id": paper_id,
        "citation": ref.citation,
        "source_url": source_url,
        "source_description": ref.source_description,
        "fetched_at": fetched_at,
        "sha256": digest,
        "size_bytes": len(body),
        "licensing_status": ref.licensing_status,
        "abstract_path": abstract_path.name,
    }

    stage_meta = meta_path.with_suffix(".json.partial")
    stage_meta.write_text(
        json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    stage_meta.replace(meta_path)

    _append_manifest(
        {
            "event": "paper_ingested",
            "paper_id": paper_id,
            "path": str(pdf_path),
            "sha256": digest,
            "ingested_at": fetched_at,
            "source": "local_paper_examples",
        }
    )

    return PaperIngestResult(
        paper_id=paper_id,
        citation=ref.citation,
        source_url=source_url,
        path=str(pdf_path),
        abstract_path=str(abstract_path),
        fetched_at=fetched_at,
        sha256=digest,
        size_bytes=len(body),
        licensing_status=ref.licensing_status,
        was_cached=False,
    )


def _try_load_cached_local(
    ref: LocalPaperRef,
    pdf_path: Path,
    meta_path: Path,
    abstract_path: Path,
    source_url: str,
) -> PaperIngestResult | None:
    """Cache-probe for ``ingest_local_paper`` — mirrors :func:`_try_load_cached`."""
    if not (pdf_path.exists() and meta_path.exists() and abstract_path.exists()):
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

    actual_hash = sha256_file(pdf_path)
    if actual_hash != recorded_hash:
        raise IngestionError(
            (
                f"hash mismatch for {pdf_path}: meta recorded {recorded_hash}"
                f" but file hashes to {actual_hash}"
            ),
            reason="hash_mismatch",
            target=str(pdf_path),
        )

    return PaperIngestResult(
        paper_id=str(meta.get("paper_id", ref.paper_id)),
        citation=str(meta.get("citation", ref.citation)),
        source_url=str(meta.get("source_url", source_url)),
        path=str(pdf_path),
        abstract_path=str(abstract_path),
        fetched_at=str(meta.get("fetched_at", _utc_now_iso())),
        sha256=recorded_hash,
        size_bytes=int(meta.get("size_bytes", pdf_path.stat().st_size)),
        licensing_status=str(
            meta.get("licensing_status", ref.licensing_status)
        ),  # type: ignore[arg-type]
        was_cached=True,
    )


# -- Internals -----------------------------------------------------------


def _try_load_cached(
    ref: PaperRef,
    pdf_path: Path,
    meta_path: Path,
    abstract_path: Path,
) -> PaperIngestResult | None:
    # All three artifacts must be present to count as a cache hit — a
    # half-written state should re-run from scratch.
    if not (pdf_path.exists() and meta_path.exists() and abstract_path.exists()):
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

    actual_hash = sha256_file(pdf_path)
    if actual_hash != recorded_hash:
        raise IngestionError(
            (
                f"hash mismatch for {pdf_path}: meta recorded {recorded_hash}"
                f" but file hashes to {actual_hash}"
            ),
            reason="hash_mismatch",
            target=str(pdf_path),
        )

    return PaperIngestResult(
        paper_id=str(meta.get("paper_id", ref.paper_id)),
        citation=str(meta.get("citation", ref.citation)),
        source_url=str(meta.get("source_url", ref.source_url)),
        path=str(pdf_path),
        abstract_path=str(abstract_path),
        fetched_at=str(meta.get("fetched_at", _utc_now_iso())),
        sha256=recorded_hash,
        size_bytes=int(meta.get("size_bytes", pdf_path.stat().st_size)),
        licensing_status="mirrored_pending_review",
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


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvp.ingestion.papers_ingest",
        description="Ingest academic papers for the Phase 1 sample set.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--batch",
        choices=["all"],
        help="Ingest both sample papers (Beneish 1999 + Altman 1968).",
    )
    group.add_argument(
        "--paper-id",
        dest="paper_id",
        choices=sorted(_SAMPLE_INDEX.keys()),
        help="Ingest a single paper by stable id.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    with httpx.Client(
        timeout=30.0,
        headers={"User-Agent": _DEFAULT_USER_AGENT, "Accept": "application/pdf"},
        follow_redirects=True,
    ) as client:
        if args.batch is not None:
            for ref in _SAMPLE_PAPERS:
                result = ingest_paper(ref.paper_id, client=client)
                status = "cached" if result.was_cached else "fetched"
                print(
                    f"[{status}] {result.paper_id} size={result.size_bytes} "
                    f"sha256={result.sha256[:12]}"
                )
        else:
            result = ingest_paper(args.paper_id, client=client)
            json.dump(
                result.model_dump(), sys.stdout, indent=2, ensure_ascii=False
            )
            sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
