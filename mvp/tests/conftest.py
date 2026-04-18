"""Shared test fixtures.

Fixtures defined here are hermetic — they don't hit the network and don't
depend on files outside the test tree. The PDF fixture is generated
inline via ``pymupdf`` so the repo carries no binary test data.

This module also registers the ``requires_live_data`` marker and a
collection hook that skips any test marked with it when the live
ingested corpus (Apple's FY2023 10-K filing, used as the sentinel) is
absent from ``data/filings/``. In a fresh clone — where ``data/filings/``
is ``.gitignore``-d and therefore empty — the 39 live-data-dependent
tests skip cleanly; after ``mvp ingest`` they run. Rationale + the split
of marked vs. hermetic tests is recorded in SPEC_UPDATES.md under the
``2026-04-17 — Hermetic pytest gate (Phase 8 fixer)`` section.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf  # type: ignore[import-untyped]
import pytest


# ---------------------------------------------------------------------------
# Live-data gating.
# ---------------------------------------------------------------------------


_MVP_ROOT = Path(__file__).resolve().parents[1]
# Sentinel directory that only exists after `mvp ingest filings --batch all`.
# Apple's CIK-0000320193 is chosen because every live-data test in the
# suite touches at least one Apple FY2023 artifact (Apple appears in
# Altman/Beneish gold cases, parity tests, and citation-resolver tests);
# its presence is a sufficient proxy for the full 10-filing corpus.
_LIVE_DATA_SENTINEL = _MVP_ROOT / "data" / "filings" / "0000320193"


def _live_data_present() -> bool:
    """Return True if the live ingested filings corpus is on disk.

    A directory that exists but is empty counts as absent — guards against
    the `git checkout` pattern where `.gitkeep` or parent dirs might linger.
    """
    if not _LIVE_DATA_SENTINEL.is_dir():
        return False
    # Must contain at least one child (an accession directory).
    return any(_LIVE_DATA_SENTINEL.iterdir())


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``requires_live_data`` marker.

    This is ``--strict-markers``-compatible: once registered here, any
    stray typo like ``@pytest.mark.requres_live_data`` will fail at
    collection time under strict mode.
    """
    config.addinivalue_line(
        "markers",
        "requires_live_data: test depends on an ingested filings corpus "
        "under data/filings/. Automatically skipped on a fresh clone; "
        "run `mvp ingest filings --batch all` to enable.",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip ``requires_live_data``-marked tests when live corpus is absent.

    The check runs once per collection (``_live_data_present()`` is not
    memoised but the I/O is a single ``Path.iterdir``).
    """
    if _live_data_present():
        return
    skip_marker = pytest.mark.skip(
        reason=(
            "requires ingested filings corpus under data/filings/; "
            "run `mvp ingest filings --batch all` to enable"
        )
    )
    for item in items:
        if "requires_live_data" in item.keywords:
            item.add_marker(skip_marker)


# ---------------------------------------------------------------------------
# Generic hermetic fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture
def tiny_pdf(tmp_path: Path) -> Path:
    """A 2-page PDF whose contents are predictable for text-extraction tests."""
    doc = pymupdf.open()
    for i, text in enumerate(["Page one body text.", "Page two body text."], start=1):
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        # Mark the page number in a separate area to make iter_pages verifiable.
        page.insert_text((72, 120), f"PAGEMARK {i}", fontsize=10)
    out = tmp_path / "tiny.pdf"
    doc.save(out)
    doc.close()
    return out
