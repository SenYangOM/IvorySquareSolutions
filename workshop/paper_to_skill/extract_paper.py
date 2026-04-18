"""workshop.paper_to_skill.extract_paper — PDF → structured extraction.

Rough first-draft version written during the paper-onboarding of
``paper_examples/fundamentals_text.pdf`` (paper 1). Hardened on
paper 2 (Kim & Nikolaev 2024 J. Accounting Research) by adding
journal-format support — see ``_FORMULA_PATTERNS`` and
``_strip_journal_footers`` below.

What this script does
---------------------
1. Takes a PDF path and returns a :class:`PaperExtraction` with
   basic metadata and a structural summary — page count, table of
   contents, PDF sha256 (needed for manifest ``provenance.pdf_sha256``),
   detected formulas (anything matching ``Equation <n>`` or common
   math patterns), and the raw per-page text.
2. Has a ``--paper-id`` CLI mode that prints the extraction as JSON
   so the workshop user can eyeball it and copy fields into a new
   ``notes/<paper_id>.md`` methodologist-extraction file.
3. Provides a :func:`top_toc_sections` helper that returns just the
   level-2 (and optionally level-3) TOC entries for quick scanning
   of where a paper's headline analyses live. Added on paper 2 when
   the J. Accounting Research TOC was rich enough (8 level-2 + 18
   level-3 entries) that eyeballing the full TOC was wasteful.
4. Strips Wiley-style journal footers from formula snippets via
   :func:`_strip_journal_footers` so detected hits don't carry 200
   chars of "Downloaded from https://onlinelibrary.wiley.com/..."
   noise. Added on paper 2 — paper 1 was a working paper without
   journal footers, so this gap only surfaced when paper 2 landed.

What this script does NOT do
----------------------------
- Extract coefficients or thresholds from tables. That requires
  real table-to-structured-data parsing (camelot, tabula) which
  none of the MVP papers needed because their coefficients appear
  inline in the text. When paper 3 or 4 surfaces a paper where the
  coefficients live only in a scanned table, that's when this
  function grows.
- Classify the paper's construct into an L1/L2/L3 skill-layer
  decision. That remains a human (or ``quant_finance_methodologist``
  persona) judgment call documented in
  ``notes/<paper_id>.md`` §(a).
- Author the skill manifest. See ``draft_manifest.py`` (post-MVP —
  not written at paper-1/2 time because the manifest-authoring flow
  is still essentially copy-the-nearest-template-and-adapt; scripting
  that is premature until we see two or three more cases).

Usage
-----
As a library::

    from workshop.paper_to_skill.extract_paper import extract_paper_pdf
    extraction = extract_paper_pdf(
        Path('/home/iv/research/Proj_ongoing/paper_examples/fundamentals_text.pdf'),
        paper_id='fundamentals_text',
    )
    print(extraction.pdf_sha256)
    print(extraction.detected_formulas)

As a CLI::

    python -m workshop.paper_to_skill.extract_paper \
        --pdf /home/iv/research/Proj_ongoing/paper_examples/fundamentals_text.pdf \
        --paper-id fundamentals_text

The separation contract (SPEC_UPDATES §13.3) forbids ``mvp/`` from
importing anything under ``workshop/``. This script in turn MAY
import from ``mvp.lib.*`` (we rely on :mod:`mvp.lib.pdf_io` and
:mod:`mvp.lib.hashing`) but not from ``mvp.skills.*.skill`` — the
registry is the seam.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

import pymupdf  # type: ignore[import-untyped]

from mvp.lib.hashing import sha256_file


@dataclass(frozen=True)
class TocEntry:
    """One table-of-contents entry from the PDF's bookmarks."""

    level: int
    title: str
    page: int


@dataclass(frozen=True)
class DetectedFormula:
    """One formula mention detected in the paper's text.

    ``pattern_matched`` names the heuristic that fired (e.g.
    ``"equation_n"`` for an ``Equation 9``-style reference), and
    ``snippet`` is the surrounding text (± 80 chars) so a reviewer
    can eyeball whether the hit is a real equation or a stray phrase.
    """

    page: int
    pattern_matched: str
    match_text: str
    snippet: str


@dataclass(frozen=True)
class PaperExtraction:
    """Structured extraction output for one paper."""

    paper_id: str
    source_path: str
    pdf_sha256: str
    page_count: int
    toc: list[TocEntry] = field(default_factory=list)
    detected_formulas: list[DetectedFormula] = field(default_factory=list)
    per_page_char_counts: list[int] = field(default_factory=list)
    abstract_preview: str = ""

    def to_json_dict(self) -> dict:
        """JSON-serializable dict (dataclasses aren't serializable by default)."""
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# Public extraction API.
# ---------------------------------------------------------------------------


# Formula-detection heuristics. Each entry is ``(pattern_name, compiled_regex)``.
#
# Paper 1 (Kim, Muhn, Nikolaev & Zhang 2024 working paper) cited
# equations as "Equation 8" / "Equation 9" — the first two patterns
# below cover that.
#
# Paper 2 (Kim & Nikolaev 2024 J. Accounting Research) cites equations
# as parenthesized numbers ``(1)``, ``(2)``, ``(3)``, ``(4)`` after a
# multi-line displayed equation block (Wiley journal style). The
# ``equation_paren_label`` pattern matches that. The paper also has
# ~50 cross-references to tables and figures (e.g. "table 7, panel A",
# "ﬁgure 1(a)", "online appendix table OA-2"); the
# ``numbered_table_or_figure`` pattern surfaces those so a methodologist
# can quickly tell which tables the paper's argument hangs on.
#
# When paper 3 or later needs LaTeX-style inline math like ``\beta_1`` or
# ``\sum_{k=1}^N``, add the pattern here.
_FORMULA_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("equation_n", re.compile(r"\bEquation\s+(\d+)\b", re.IGNORECASE)),
    ("equation_roman", re.compile(r"\bEquation\s+(I{1,3}|IV|V|VI+)\b")),
    # Parenthesized equation labels at end-of-line, the Wiley convention.
    # Matches "(1)", "(2)", ... "(99)" but ONLY when preceded by either
    # whitespace+comma+space (",  (3)" — the displayed-equation case) or
    # at start of line. This dampens false positives on inline ranges
    # like "Tables (3) and (4)" by requiring nothing alphanumeric to the
    # immediate left of the open-paren.
    (
        "equation_paren_label",
        re.compile(r"(?:^|[\s,;])\((\d{1,2})\)\s*$", re.MULTILINE),
    ),
    # "Z-score = 0.012X_1 + ..." style — matches "variable = <coefficient>*X<i>"
    ("linear_combination", re.compile(r"\b[A-Z]\s*=\s*[-−]?\s*\d+\.\d+")),
    # Threshold phrasing — "M > -1.78", "Z < 1.81", "P25 = 0.5012"
    (
        "threshold_value",
        re.compile(
            r"\b(?:[A-Z]\s*[<>≤≥]\s*[-−]?\s*\d+\.\d+|P\d+\s*=\s*\d+\.\d+)"
        ),
    ),
    # Cross-references to tables + figures. Useful for "which tables
    # does this paper's argument hang on?" — surfaces high-impact
    # references like "table 9" in Kim & Nikolaev 2024 (the
    # context-based earnings persistence headline result).
    (
        "numbered_table_or_figure",
        re.compile(
            r"\b(?:Table|table|Figure|figure|ﬁgure|Appendix|appendix)\s+"
            r"(?:[A-Z]+-?\d+|\d+(?:\s*[Pp]anel\s+[A-Z])?)\b"
        ),
    ),
)

_ABSTRACT_HINT_RE = re.compile(
    r"\bAbstract\s*\n+(?P<body>.{100,2000}?)\n\n", re.DOTALL
)

# Wiley-style journal-footer signature, applied per-page-text before
# snippet extraction so detected formulas don't carry 200 chars of
# legal-notice noise. Matches the boilerplate that appears at the
# bottom of every page in J. Accounting Research / Wiley Online Library
# downloads.
_WILEY_FOOTER_RE = re.compile(
    r"\s*\d+\s*1475679x,\s*\d+,\s*Downloaded from https://onlinelibrary\.wiley\.com.*?"
    r"on Wiley Online Library for rules of use; OA articles are governed by "
    r"the applicable Creative Commons License",
    re.DOTALL,
)


def extract_paper_pdf(pdf_path: Path, *, paper_id: str) -> PaperExtraction:
    """Extract structure from one PDF.

    Parameters
    ----------
    pdf_path:
        Absolute path to the PDF. Must exist and be a readable PDF.
    paper_id:
        Stable snake_case id for the paper (e.g. ``"fundamentals_text"``).
        Purely labeling — not validated against any catalogue here,
        because the ingestion catalogue in :mod:`mvp.ingestion.papers_ingest`
        is a separate concern.

    Returns
    -------
    PaperExtraction
        Populated with metadata, TOC (empty if the PDF has no
        bookmarks), per-page character counts, abstract preview, and
        detected-formula hits.

    Raises
    ------
    FileNotFoundError
        If ``pdf_path`` does not exist.
    """
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found at {pdf_path}")

    pdf_sha = sha256_file(pdf_path)
    doc = pymupdf.open(str(pdf_path))
    try:
        pages_text = [doc[i].get_text() for i in range(len(doc))]
        toc_raw = doc.get_toc()
    finally:
        doc.close()

    toc = [TocEntry(level=int(lvl), title=str(title), page=int(page))
           for lvl, title, page in toc_raw]
    per_page_chars = [len(t) for t in pages_text]

    formulas = list(_find_formulas(pages_text))

    abstract_preview = _extract_abstract_preview(pages_text[0] if pages_text else "")

    return PaperExtraction(
        paper_id=paper_id,
        source_path=str(pdf_path),
        pdf_sha256=pdf_sha,
        page_count=len(pages_text),
        toc=toc,
        detected_formulas=formulas,
        per_page_char_counts=per_page_chars,
        abstract_preview=abstract_preview,
    )


def _find_formulas(pages_text: Iterable[str]) -> Iterable[DetectedFormula]:
    """Yield :class:`DetectedFormula` hits across every page.

    Duplicates are NOT de-duplicated (a paper that cites "Equation 8"
    five times produces five hits — that is useful signal about which
    equations matter). A future hardening pass could group by
    ``match_text`` and report frequencies.

    Each page's text is passed through :func:`_strip_journal_footers`
    before scanning so detected formulas in journal-format PDFs don't
    carry the publisher's legal-notice footer in their snippet.
    """
    for page_idx, text in enumerate(pages_text, start=1):
        cleaned = _strip_journal_footers(text)
        for pattern_name, compiled in _FORMULA_PATTERNS:
            for m in compiled.finditer(cleaned):
                lo = max(0, m.start() - 80)
                hi = min(len(cleaned), m.end() + 80)
                snippet = cleaned[lo:hi].replace("\n", " ").strip()
                yield DetectedFormula(
                    page=page_idx,
                    pattern_matched=pattern_name,
                    match_text=m.group(0),
                    snippet=snippet,
                )


def _strip_journal_footers(page_text: str) -> str:
    """Remove Wiley-style journal-footer boilerplate from a page's text.

    Returns ``page_text`` unchanged if no footer signature is found,
    so working papers (which have no journal footer) pass through
    untouched. Working papers were the only paper-1 case, so this
    function is a no-op there; it earns its keep on paper 2 onward.
    """
    return _WILEY_FOOTER_RE.sub("", page_text)


def top_toc_sections(
    extraction: PaperExtraction, *, max_level: int = 2
) -> list[TocEntry]:
    """Return only the top-N levels of ``extraction.toc``.

    Useful when a paper's TOC is rich enough that the full list is too
    long to eyeball. Paper 2 (Kim & Nikolaev 2024) has 26 TOC entries
    across 4 levels; ``max_level=2`` returns the 8 main sections, which
    is the right starting point for the methodologist's
    "where does the headline result live?" scan.

    Parameters
    ----------
    extraction:
        A :class:`PaperExtraction`.
    max_level:
        Inclusive upper bound on TOC entry depth. ``max_level=1``
        returns only the title; ``max_level=2`` adds the main
        sections; ``max_level=3`` adds subsections; etc.

    Returns
    -------
    list[TocEntry]
        Filtered TOC entries in document order.
    """
    if max_level < 1:
        raise ValueError(f"max_level must be >= 1, got {max_level}")
    return [t for t in extraction.toc if t.level <= max_level]


def _extract_abstract_preview(page_one_text: str) -> str:
    """Best-effort abstract extraction from page 1.

    Looks for a line containing "Abstract" followed by prose; returns
    the first 1000 chars of the matched block. Returns an empty string
    if the heuristic misses (some papers don't label the abstract
    explicitly).
    """
    m = _ABSTRACT_HINT_RE.search(page_one_text)
    if m is None:
        return ""
    body = m.group("body").strip()
    return body[:1000]


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workshop.paper_to_skill.extract_paper",
        description=(
            "Extract structural metadata from a paper PDF for the "
            "paper-onboarding workflow. Output is JSON on stdout."
        ),
    )
    p.add_argument(
        "--pdf",
        type=Path,
        required=True,
        help="Absolute path to the PDF.",
    )
    p.add_argument(
        "--paper-id",
        required=True,
        help="Stable snake_case id for the paper.",
    )
    p.add_argument(
        "--max-formula-hits",
        type=int,
        default=40,
        help=(
            "Truncate the detected_formulas list at this many entries "
            "when printing JSON (keeps stdout readable). The full list "
            "is still available via the Python API."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        extraction = extract_paper_pdf(args.pdf, paper_id=args.paper_id)
    except FileNotFoundError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    out = extraction.to_json_dict()
    if args.max_formula_hits >= 0:
        out["detected_formulas"] = out["detected_formulas"][: args.max_formula_hits]
        out["detected_formulas_truncated_at"] = args.max_formula_hits
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "DetectedFormula",
    "PaperExtraction",
    "TocEntry",
    "extract_paper_pdf",
    "main",
    "top_toc_sections",
]
