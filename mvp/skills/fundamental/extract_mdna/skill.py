"""extract_mdna — L1 fundamental skill.

Deterministic extractor for Part II, Item 7 (Management's Discussion
and Analysis) from a 10-K filing. One finder works across the two
substrates in scope:

- iXBRL HTML filings (Apple, Microsoft, Carvana) — the finder locates
  the "Item 7" text fragment that appears in a heading ``<span>`` and
  bounds the section at the next "Item 7A" or "Item 8" heading.
- Pre-iXBRL SGML text filings (Enron, WorldCom) — identical substring
  search works because SEC-mandated headings carry the same "Item 7"
  and "Item 8" tokens. No HTML, so the stripper is a no-op.

When the finder cannot identify both bounds, the skill returns
``section_text=null`` + a warning rather than emitting a guessed
window. P2 "no silent fallback" — the agent sees the failure.
"""

from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import find_filing
from mvp.lib.citation import Citation, build_locator
from mvp.lib.errors import ErrorCategory, LibError
from mvp.lib.hashing import hash_excerpt, sha256_text
from mvp.skills._base import Skill
from mvp.store.doc_store import get_doc_text


class ExtractMdna(Skill):
    id = "extract_mdna"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fiscal_year_end = str(inputs["fiscal_year_end"])
        ref = find_filing(cik, fiscal_year_end)
        if ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} "
                f"fiscal_year_end={fiscal_year_end!r}"
            )
        filing_id = f"{ref.cik}/{ref.accession}"
        text = get_doc_text(filing_id)

        start, end = _find_section_bounds(text)
        if start is None or end is None or end <= start:
            return {
                "section_text": None,
                "citations": [],
                "start_offset": 0,
                "end_offset": 0,
                "warnings": [
                    f"could not locate Item 7 / Item 8 section bounds in filing "
                    f"{filing_id}; returning indeterminate"
                ],
            }

        raw_section = text[start:end]
        section_text = _strip_html_to_text(raw_section)
        locator = build_locator(filing_id, "mdna", "item_7")
        citation = Citation(
            doc_id=filing_id,
            statement_role=None,
            locator=locator,
            excerpt_hash=hash_excerpt(section_text),
            value=None,
            retrieved_at=datetime.now(timezone.utc),
        )
        return {
            "section_text": section_text,
            "citations": [citation.model_dump(mode="json")],
            "start_offset": start,
            "end_offset": end,
            "warnings": [],
        }


# ---------------------------------------------------------------------------
# Section-finder + stripper.
# ---------------------------------------------------------------------------


_ITEM_TOKEN_RE = re.compile(
    r"""Item[\s\u00A0]*(?:&\#160;)?[\s\u00A0]*7[\s\u00A0]*\.""",
    re.IGNORECASE,
)
_ITEM_7A_RE = re.compile(
    r"""Item[\s\u00A0]*(?:&\#160;)?[\s\u00A0]*7A[\s\u00A0]*\.""",
    re.IGNORECASE,
)
_ITEM_8_RE = re.compile(
    r"""Item[\s\u00A0]*(?:&\#160;)?[\s\u00A0]*8[\s\u00A0]*\.""",
    re.IGNORECASE,
)


def _find_section_bounds(text: str) -> tuple[int | None, int | None]:
    """Return ``(start, end)`` byte offsets of Item 7 within ``text``.

    Strategy:
    1. Iterate matches of ``Item 7.`` (with the trailing dot — this
       filters out inline references to "Item 7" without the dot).
    2. For each candidate, look forward for an ``Item 7A.`` or ``Item 8.``
       within the next ~500 KB. The first candidate whose forward-end
       is within range is the heading we want.
    3. Return the start offset of the "Item 7." token and the start
       offset of the bounding "Item 7A." / "Item 8." marker.

    Returns ``(None, None)`` if no viable pair was found.
    """
    max_section = 600_000
    # iterate all "Item 7." candidates — the heading usually isn't the
    # first match (there may be references earlier). We scan all and
    # take the last candidate whose successor ends within max_section.
    candidates: list[int] = [m.start() for m in _ITEM_TOKEN_RE.finditer(text)]
    for start in reversed(candidates):
        # Look for 7A first (more restrictive), then 8.
        end_candidates: list[int] = []
        for pat in (_ITEM_7A_RE, _ITEM_8_RE):
            m = pat.search(text, start + 1, start + 1 + max_section)
            if m is not None:
                end_candidates.append(m.start())
        if not end_candidates:
            continue
        end = min(end_candidates)
        if end - start < 2000:
            # Too short to be a real section body; probably matched a
            # cross-reference. Keep walking.
            continue
        return start, end
    return None, None


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"[ \t\xa0]+")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")


def _strip_html_to_text(s: str) -> str:
    """Strip HTML/iXBRL tags and decode entities to plain UTF-8 text."""
    # Replace block-level close tags with newlines so paragraph boundaries
    # survive the tag strip.
    block_closers = ["</p>", "</div>", "</tr>", "</td>", "</li>", "</h1>",
                     "</h2>", "</h3>", "</h4>", "</span>"]
    for tag in block_closers:
        s = s.replace(tag, f"{tag}\n")
        s = s.replace(tag.upper(), f"{tag}\n")
    # Strip all remaining tags.
    stripped = _TAG_RE.sub("", s)
    # Decode HTML entities.
    decoded = html.unescape(stripped)
    # Collapse horizontal whitespace runs; collapse 3+ newlines to 2.
    lines = [_WHITESPACE_RE.sub(" ", ln).strip() for ln in decoded.split("\n")]
    joined = "\n".join(lines)
    joined = _MULTINEWLINE_RE.sub("\n\n", joined).strip()
    return joined


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


SKILL = ExtractMdna
