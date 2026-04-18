"""Phase 0 smoke demo.

Fetches Apple's (CIK 0000320193) most recent 10-K from SEC EDGAR via
``mvp.lib.edgar``, writes the submissions JSON to ``data/demo/``, downloads
the primary 10-K document (HTML), and prints a short snippet of extracted
text.

Does NOT require an Anthropic API key: the demo exercises the L0 HTTP path
and the stdlib HTML fallback only. No ``pymupdf`` path is exercised (10-K
primary docs are HTML, not PDF).

Run with:

    .venv/bin/python -m mvp.scripts.phase0_demo
"""

from __future__ import annotations

import html
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

from mvp.lib.edgar import EdgarClient

APPLE_CIK = "0000320193"
DEMO_DIR = Path(__file__).resolve().parent.parent / "data" / "demo"


class _VisibleTextExtractor(HTMLParser):
    """Collect visible text, skipping <script>/<style>/<head>."""

    _SKIP = {"script", "style", "head", "title", "meta", "link"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._buf: list[str] = []
        self._skip_depth = 0
        self.title: str | None = None
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        t = tag.lower()
        if t == "title":
            self._in_title = True
        if t in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        t = tag.lower()
        if t == "title":
            self._in_title = False
        if t in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._in_title and self.title is None:
            stripped = data.strip()
            if stripped:
                self.title = stripped
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._buf.append(text)

    def text(self) -> str:
        raw = " ".join(self._buf)
        # Collapse whitespace runs.
        return re.sub(r"\s+", " ", raw).strip()


def _extract_text(body: bytes) -> tuple[str | None, str]:
    """Return ``(title, first_body_text)`` from an HTML payload."""
    decoded = body.decode("utf-8", errors="replace")
    parser = _VisibleTextExtractor()
    parser.feed(decoded)
    parser.close()
    return parser.title, parser.text()


def _pick_most_recent_10k(submissions: dict) -> tuple[str, str, str]:
    """Return ``(accession, primary_document, fiscal_period_end)`` for the newest 10-K."""
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    accessions = recent.get("accessionNumber", [])
    primary_docs = recent.get("primaryDocument", [])
    periods = recent.get("reportDate", [])
    for form, accession, primary, period in zip(forms, accessions, primary_docs, periods):
        if form == "10-K":
            return accession, primary, period
    raise RuntimeError("no 10-K found in Apple's recent submissions")


def main() -> int:
    DEMO_DIR.mkdir(parents=True, exist_ok=True)

    with EdgarClient() as client:
        submissions = client.fetch_submissions(APPLE_CIK)
        subs_path = DEMO_DIR / "apple_submissions.json"
        subs_path.write_text(
            json.dumps(submissions, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        accession, primary_doc, period = _pick_most_recent_10k(submissions)

        # Verify the filing index is reachable (exercises fetch_filing_index).
        index = client.fetch_filing_index(APPLE_CIK, accession)
        index_items = index.get("directory", {}).get("item", [])
        primary_in_index = any(it.get("name") == primary_doc for it in index_items)
        if not primary_in_index:
            print(
                f"warning: primary doc {primary_doc} not listed in index.json for {accession}",
                file=sys.stderr,
            )

        accession_nodash = accession.replace("-", "")
        doc_url = (
            "https://www.sec.gov/Archives/edgar/data/"
            f"{int(APPLE_CIK)}/{accession_nodash}/{primary_doc}"
        )
        body = client.fetch_document(doc_url)

    title, body_text = _extract_text(body)
    snippet = body_text[:200]

    print(f"accession: {accession}")
    print(f"fiscal_period_end: {period}")
    print(f"primary_document: {primary_doc}")
    print(f"title: {title!r}")
    print(f"first_200_chars: {snippet!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
