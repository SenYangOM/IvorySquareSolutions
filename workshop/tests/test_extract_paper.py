"""Light tests for workshop.paper_to_skill.extract_paper.

Workshop is exempt from the full-test bar (``success_criteria.md``
§13.4) but a couple of hermetic checks on extract_paper pay for
themselves: they pin the formula-detection heuristic behaviour and
the PaperExtraction dataclass JSON-shape so a future paper-2 author
notices immediately if the extraction shape drifts.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf  # type: ignore[import-untyped]
import pytest

from workshop.paper_to_skill.extract_paper import (
    DetectedFormula,
    PaperExtraction,
    TocEntry,
    _find_formulas,
    _strip_journal_footers,
    extract_paper_pdf,
    top_toc_sections,
)


def _make_tiny_pdf(tmp_path: Path, page_texts: list[str]) -> Path:
    """Write a minimal one-or-more-page PDF with each string on its own page."""
    doc = pymupdf.open()
    for text in page_texts:
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=11)
    path = tmp_path / "tiny.pdf"
    doc.save(str(path))
    doc.close()
    return path


def test_find_formulas_detects_equation_n_references() -> None:
    pages = [
        "The model is defined by Equation 8 and Equation 9 below.",
        "As shown by Equation II in the appendix...",
    ]
    hits = list(_find_formulas(pages))
    # Three hits total: Equation 8 + Equation 9 (page 1) + Equation II (page 2).
    patterns = {h.pattern_matched for h in hits}
    assert "equation_n" in patterns
    assert "equation_roman" in patterns
    pages_hit = {h.page for h in hits}
    assert pages_hit == {1, 2}


def test_find_formulas_detects_linear_combination() -> None:
    pages = ["The Z score is Z = -4.84 + 0.528 * GMI + ..."]
    hits = list(_find_formulas(pages))
    # A hit from the linear-combination pattern (Z = -4.84 ...).
    assert any(h.pattern_matched == "linear_combination" for h in hits)


def test_find_formulas_detects_threshold_values() -> None:
    pages = [
        "A firm is flagged when M > -1.78. The P25 = 0.5012 threshold is fixed."
    ]
    hits = list(_find_formulas(pages))
    # Two threshold hits — one per regex capture.
    threshold_hits = [h for h in hits if h.pattern_matched == "threshold_value"]
    assert len(threshold_hits) >= 2


def test_extract_paper_pdf_happy_path(tmp_path: Path) -> None:
    pdf_path = _make_tiny_pdf(
        tmp_path,
        [
            "Title. This paper introduces Equation 1.",
            "Body. The function is Y = -0.5 + 1.2*X.",
        ],
    )
    extraction = extract_paper_pdf(pdf_path, paper_id="tiny_test")
    assert isinstance(extraction, PaperExtraction)
    assert extraction.paper_id == "tiny_test"
    assert extraction.source_path == str(pdf_path)
    assert extraction.page_count == 2
    assert len(extraction.pdf_sha256) == 64
    assert len(extraction.per_page_char_counts) == 2
    # detected_formulas is non-empty and contains our Equation 1 hit.
    assert any(
        f.match_text.lower().startswith("equation") for f in extraction.detected_formulas
    )


def test_extract_paper_pdf_raises_on_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "not_there.pdf"
    with pytest.raises(FileNotFoundError):
        extract_paper_pdf(missing, paper_id="missing")


def test_paper_extraction_to_json_dict_is_serializable(tmp_path: Path) -> None:
    """to_json_dict() output round-trips through json.dumps."""
    import json

    pdf_path = _make_tiny_pdf(tmp_path, ["Abstract\n\nBody body body.\n\n"])
    extraction = extract_paper_pdf(pdf_path, paper_id="tiny")
    js = json.dumps(extraction.to_json_dict())
    back = json.loads(js)
    assert back["paper_id"] == "tiny"
    assert back["page_count"] == 1
    # DetectedFormula dataclasses serialized as dicts.
    for f in back["detected_formulas"]:
        assert isinstance(f, dict)
        assert {"page", "pattern_matched", "match_text", "snippet"} <= set(f)


def test_detected_formula_is_frozen() -> None:
    """Dataclass is frozen — attempts to mutate raise FrozenInstanceError."""
    import dataclasses

    f = DetectedFormula(page=1, pattern_matched="eq", match_text="Equation 1", snippet="x")
    with pytest.raises(dataclasses.FrozenInstanceError):
        f.page = 2  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Paper-2 hardening: parenthesized equation labels, table/figure refs,
# Wiley journal footers, top_toc_sections helper.
# ---------------------------------------------------------------------------


def test_find_formulas_detects_paren_equation_labels() -> None:
    """Wiley J. Accounting Research style — equations labelled '(2)' end of line."""
    pages = [
        # The displayed-equation case: a comma+spaces followed by "(2)" at EOL.
        "earningsit+1 = γ0 + γ1·earningsit + ε,  (2)\n",
        # Sentence-form: equation references in prose like "see Equation (3)"
        # — should NOT match the paren_label pattern (it requires EOL).
        "We refer the reader to Equation (3) above.\n",
    ]
    hits = list(_find_formulas(pages))
    paren_hits = [h for h in hits if h.pattern_matched == "equation_paren_label"]
    # At least the page-1 EOL-anchored "(2)" must hit.
    assert len(paren_hits) >= 1
    assert any("(2)" in h.match_text for h in paren_hits)


def test_find_formulas_detects_table_or_figure_references() -> None:
    """Cross-references to tables and figures surface as a distinct pattern."""
    pages = [
        "As reported in table 7, panel A, contextuality is higher for loss firms. "
        "ﬁgure 1(a) illustrates the fully-connected ANN. "
        "Online appendix table OA-2 provides robustness checks.",
    ]
    hits = list(_find_formulas(pages))
    table_hits = [
        h for h in hits if h.pattern_matched == "numbered_table_or_figure"
    ]
    # 'table 7' + 'ﬁgure 1' + 'table OA-2' = 3 hits.
    assert len(table_hits) >= 3
    matched = " ".join(h.match_text for h in table_hits)
    assert "table 7" in matched
    assert "table OA-2" in matched


def test_strip_journal_footers_removes_wiley_boilerplate() -> None:
    """The Wiley footer signature is excised so it doesn't pollute snippets."""
    body = "The substantive content of the page lives here.\n\n"
    footer = (
        "12 1475679x, 0, Downloaded from "
        "https://onlinelibrary.wiley.com/doi/10.1111/1475-679X.12593 "
        "by University Of British Columbia, Wiley Online Library on [16/04/2026]. "
        "See the Terms and Conditions "
        "(https://onlinelibrary.wiley.com/terms-and-conditions) "
        "on Wiley Online Library for rules of use; OA articles are governed by "
        "the applicable Creative Commons License"
    )
    cleaned = _strip_journal_footers(body + "\n" + footer)
    assert "substantive content" in cleaned
    assert "onlinelibrary.wiley.com" not in cleaned
    assert "Creative Commons" not in cleaned


def test_strip_journal_footers_no_op_for_working_papers() -> None:
    """A page without the Wiley signature passes through unchanged."""
    text = (
        "Working paper text. Equation 8 introduces the upfrontedness "
        "measure. No journal footer here.\n"
    )
    assert _strip_journal_footers(text) == text


def test_top_toc_sections_filters_to_max_level() -> None:
    """top_toc_sections drops entries deeper than the requested level."""
    entries = [
        TocEntry(level=1, title="Title", page=1),
        TocEntry(level=2, title="1. Introduction", page=2),
        TocEntry(level=2, title="3. Methodology", page=10),
        TocEntry(level=3, title="3.1 Encoding", page=10),
        TocEntry(level=3, title="3.2 Modeling", page=12),
        TocEntry(level=4, title="3.2.1 Detail", page=13),
    ]
    extraction = PaperExtraction(
        paper_id="x",
        source_path="/x.pdf",
        pdf_sha256="0" * 64,
        page_count=20,
        toc=entries,
    )
    level_2 = top_toc_sections(extraction, max_level=2)
    assert {t.level for t in level_2} == {1, 2}
    assert len(level_2) == 3

    level_3 = top_toc_sections(extraction, max_level=3)
    assert {t.level for t in level_3} == {1, 2, 3}
    assert len(level_3) == 5


def test_top_toc_sections_rejects_zero_level() -> None:
    """max_level must be >= 1."""
    extraction = PaperExtraction(
        paper_id="x",
        source_path="/x.pdf",
        pdf_sha256="0" * 64,
        page_count=1,
    )
    with pytest.raises(ValueError):
        top_toc_sections(extraction, max_level=0)
