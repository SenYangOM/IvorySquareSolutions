"""Unit tests for mvp.lib.pdf_io."""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.lib.errors import InputValidationError, PdfReadError
from mvp.lib.pdf_io import extract_text, iter_pages, pdf_page_count


def test_pdf_page_count(tiny_pdf: Path) -> None:
    assert pdf_page_count(tiny_pdf) == 2


def test_extract_text_whole_doc(tiny_pdf: Path) -> None:
    text = extract_text(tiny_pdf)
    assert "Page one body text." in text
    assert "Page two body text." in text
    # Form-feed delimiter is preserved between pages.
    assert "\f" in text


def test_extract_text_single_page(tiny_pdf: Path) -> None:
    t1 = extract_text(tiny_pdf, page=1)
    t2 = extract_text(tiny_pdf, page=2)
    assert "Page one" in t1 and "Page two" not in t1
    assert "Page two" in t2 and "Page one" not in t2


def test_extract_text_bad_page(tiny_pdf: Path) -> None:
    with pytest.raises(InputValidationError):
        extract_text(tiny_pdf, page=0)
    with pytest.raises(InputValidationError):
        extract_text(tiny_pdf, page=999)


def test_iter_pages(tiny_pdf: Path) -> None:
    pages = list(iter_pages(tiny_pdf))
    assert [p[0] for p in pages] == [1, 2]
    assert "PAGEMARK 1" in pages[0][1]
    assert "PAGEMARK 2" in pages[1][1]


def test_missing_file_raises_pdfreaderror(tmp_path: Path) -> None:
    with pytest.raises(PdfReadError) as exc:
        pdf_page_count(tmp_path / "missing.pdf")
    assert exc.value.reason == "file_not_found"


def test_directory_raises_pdfreaderror(tmp_path: Path) -> None:
    with pytest.raises(PdfReadError) as exc:
        extract_text(tmp_path)
    assert exc.value.reason == "is_a_directory"


def test_non_pdf_file_raises_pdfreaderror(tmp_path: Path) -> None:
    bad = tmp_path / "not_a_pdf.pdf"
    bad.write_bytes(b"not a pdf")
    with pytest.raises(PdfReadError):
        pdf_page_count(bad)
