"""Thin facade over ``pymupdf`` (a.k.a. ``fitz``).

Callers should import only from this module; direct ``pymupdf`` usage in
skill/agent code is a layer violation and will be rejected in review.

All functions close their document on exit. Failures raise
:class:`mvp.lib.errors.PdfReadError` with ``path`` and ``reason`` fields so
the skill boundary can surface a structured error.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pymupdf  # type: ignore[import-untyped]

from .errors import InputValidationError, PdfReadError

_FORM_FEED = "\f"


def pdf_page_count(pdf_path: Path) -> int:
    """Return the number of pages in the PDF at ``pdf_path``.

    Raises
    ------
    PdfReadError
        On any failure to open or read the document.
    """
    path = _coerce_path(pdf_path)
    doc = _open(path)
    try:
        return doc.page_count
    finally:
        doc.close()


def extract_text(pdf_path: Path, *, page: int | None = None) -> str:
    """Extract text from a PDF.

    Parameters
    ----------
    pdf_path:
        Absolute or relative path to a PDF file.
    page:
        1-indexed page number. If ``None`` (the default) the whole document
        is returned with form-feed (``\\f``) separators between pages; this
        preserves page boundaries for downstream slicers.

    Raises
    ------
    InputValidationError
        If ``page`` is out of range.
    PdfReadError
        If the file cannot be opened or a page cannot be rendered.
    """
    path = _coerce_path(pdf_path)
    doc = _open(path)
    try:
        if page is None:
            chunks: list[str] = []
            for i in range(doc.page_count):
                try:
                    chunks.append(doc.load_page(i).get_text("text"))
                except Exception as exc:  # pragma: no cover - pymupdf internal failure
                    raise PdfReadError(
                        f"failed to extract text from page {i + 1}",
                        path=str(path),
                        reason=f"{type(exc).__name__}: {exc}",
                    ) from exc
            return _FORM_FEED.join(chunks)

        if not isinstance(page, int) or page < 1:
            raise InputValidationError("page must be a 1-indexed positive integer")
        if page > doc.page_count:
            raise InputValidationError(
                f"page {page} is out of range (document has {doc.page_count} pages)"
            )
        try:
            return doc.load_page(page - 1).get_text("text")
        except Exception as exc:  # pragma: no cover - pymupdf internal failure
            raise PdfReadError(
                f"failed to extract text from page {page}",
                path=str(path),
                reason=f"{type(exc).__name__}: {exc}",
            ) from exc
    finally:
        doc.close()


def iter_pages(pdf_path: Path) -> Iterator[tuple[int, str]]:
    """Yield ``(page_number_1_indexed, page_text)`` for every page.

    Pages are produced lazily; the underlying document is kept open until
    the generator is exhausted or garbage-collected. Callers who stop
    iterating early should ``close()`` the generator to release the handle.

    Raises
    ------
    PdfReadError
        On open failure (raised before the first yield).
    """
    path = _coerce_path(pdf_path)
    doc = _open(path)
    try:
        for i in range(doc.page_count):
            try:
                text = doc.load_page(i).get_text("text")
            except Exception as exc:  # pragma: no cover - pymupdf internal failure
                raise PdfReadError(
                    f"failed to extract text from page {i + 1}",
                    path=str(path),
                    reason=f"{type(exc).__name__}: {exc}",
                ) from exc
            yield i + 1, text
    finally:
        doc.close()


def _coerce_path(pdf_path: Path) -> Path:
    path = Path(pdf_path)
    if not path.exists():
        raise PdfReadError(
            f"PDF not found: {path}", path=str(path), reason="file_not_found"
        )
    if path.is_dir():
        raise PdfReadError(
            f"expected a PDF file, got a directory: {path}",
            path=str(path),
            reason="is_a_directory",
        )
    return path


def _open(path: Path) -> pymupdf.Document:
    try:
        return pymupdf.open(path)
    except Exception as exc:
        raise PdfReadError(
            f"failed to open PDF: {path}",
            path=str(path),
            reason=f"{type(exc).__name__}: {exc}",
        ) from exc
