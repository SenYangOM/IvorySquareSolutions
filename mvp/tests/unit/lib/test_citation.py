"""Unit tests for mvp.lib.citation."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from mvp.lib.citation import Citation, build_locator
from mvp.lib.hashing import sha256_text

GOOD_HASH = sha256_text("anything", normalize_newlines=False)


def test_build_locator_happy() -> None:
    loc = build_locator("0000320193-23-000106", "balance_sheet", "Receivables")
    assert loc == "0000320193-23-000106::balance_sheet::Receivables"


@pytest.mark.parametrize(
    "args",
    [
        ("", "balance_sheet", "x"),
        ("f", "", "x"),
        ("f", "r", ""),
        ("f::x", "r", "x"),
        ("f", "r::x", "x"),
        ("f", "r", "x::y"),
    ],
)
def test_build_locator_rejects(args: tuple[str, str, str]) -> None:
    with pytest.raises(ValueError):
        build_locator(*args)


def test_citation_roundtrip() -> None:
    c = Citation(
        doc_id="0000320193-23-000106",
        statement_role="balance_sheet",
        locator=build_locator("0000320193-23-000106", "balance_sheet", "Receivables"),
        excerpt_hash=GOOD_HASH,
        value=1234.5,
        retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    dumped = c.model_dump()
    reloaded = Citation.model_validate(dumped)
    assert reloaded == c


def test_citation_rejects_bad_hash() -> None:
    with pytest.raises(ValidationError):
        Citation(
            doc_id="x",
            statement_role=None,
            locator="a::b::c",
            excerpt_hash="notahex",
            value=None,
            retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_citation_rejects_uppercase_hash() -> None:
    with pytest.raises(ValidationError):
        Citation(
            doc_id="x",
            statement_role=None,
            locator="a::b::c",
            excerpt_hash=GOOD_HASH.upper(),
            value=None,
            retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_citation_rejects_bad_locator() -> None:
    with pytest.raises(ValidationError):
        Citation(
            doc_id="x",
            statement_role=None,
            locator="not-a-locator",
            excerpt_hash=GOOD_HASH,
            value=None,
            retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        )


def test_citation_accepts_optional_statement_role() -> None:
    c = Citation(
        doc_id="paper_beneish_1999",
        statement_role=None,
        locator="paper_beneish_1999::abstract::para_1",
        excerpt_hash=GOOD_HASH,
        value="Detect earnings manipulation",
        retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    assert c.statement_role is None


def test_citation_is_frozen() -> None:
    c = Citation(
        doc_id="x",
        statement_role="income_statement",
        locator="x::income_statement::Revenue",
        excerpt_hash=GOOD_HASH,
        value=1.0,
        retrieved_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ValidationError):
        c.doc_id = "y"  # type: ignore[misc]
