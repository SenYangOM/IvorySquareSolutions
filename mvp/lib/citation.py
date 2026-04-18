"""Citation model + locator helpers.

Every output claim made by a skill must carry a :class:`Citation` pointing
back to the source passage (``mvp_build_goal.md`` §6 ``citation_contract``).
The locator format is fixed at ``filing_id::statement_role::line_item`` and
validated on construction so drift can't accumulate.

This module defines *only* the Pydantic model and the locator builder. It
does **not** resolve citations against the doc store; that's a later-phase
concern.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
# The filing_id part allows "/" as the doc-id separator
# (``"<cik>/<accession>"``). The statement_role and line_item parts are
# restricted to alphanumerics / dot / dash / underscore / space — the
# space accommodates free-form line-item names in locators for narrative
# skills; the separator "::" is forbidden inside any part (enforced by
# :func:`build_locator`).
_LOCATOR_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._\-/]*::[A-Za-z0-9][A-Za-z0-9._\-]*::[A-Za-z0-9][A-Za-z0-9._\- ]*$"
)
_LOCATOR_PART_FORBID = "::"

HashStr = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$", min_length=64, max_length=64)]
LocatorStr = Annotated[str, Field(min_length=5)]


class Citation(BaseModel):
    """A single (passage → value) provenance record.

    Every field on every skill output that the citation contract names must
    be accompanied by one of these records. The pair
    ``(doc_id, locator)`` is stable — agents can re-resolve it later via a
    ``resolve_citation`` skill without having to rescrape.

    Attributes
    ----------
    doc_id:
        Stable identifier for the source document in the doc store
        (typically the filing accession number or a paper's stable id).
    statement_role:
        Optional canonical statement role (``income_statement``,
        ``balance_sheet``, ``cash_flow_statement``) when the citation comes
        from a financial statement. ``None`` for narrative citations.
    locator:
        Path inside the document: ``filing_id::statement_role::line_item``.
        See :func:`build_locator`.
    excerpt_hash:
        SHA-256 of the cited passage text, lowercase hex. Used by
        ``eval/citation_check.py`` to detect drift.
    value:
        The value this citation supports. ``float`` for numeric facts,
        ``str`` for narrative excerpts, or ``None`` when the citation is a
        cross-reference without its own value.
    retrieved_at:
        When the underlying passage was fetched from the doc store.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str = Field(min_length=1)
    statement_role: str | None = None
    locator: LocatorStr
    excerpt_hash: HashStr
    value: float | str | None = None
    retrieved_at: datetime

    @field_validator("excerpt_hash")
    @classmethod
    def _check_hash(cls, v: str) -> str:
        if not _HASH_RE.match(v):
            raise ValueError("excerpt_hash must be a 64-character lowercase hex SHA-256")
        return v

    @field_validator("locator")
    @classmethod
    def _check_locator(cls, v: str) -> str:
        if not _LOCATOR_RE.match(v):
            raise ValueError(
                "locator must be 'filing_id::statement_role::line_item' "
                "with alphanumeric/dot/dash/underscore parts"
            )
        return v


def build_locator(filing_id: str, statement_role: str, line_item: str) -> str:
    """Compose a locator string in the canonical format.

    The three parts are joined with ``"::"``. Each part must be non-empty
    and must not itself contain ``"::"``. This is the format specified in
    ``mvp_build_goal.md`` §6 ``citation_contract.locator_format``.

    Raises
    ------
    ValueError
        If any part is empty or contains the separator.
    """
    for name, part in (
        ("filing_id", filing_id),
        ("statement_role", statement_role),
        ("line_item", line_item),
    ):
        if not isinstance(part, str) or not part.strip():
            raise ValueError(f"{name} must be a non-empty string")
        if _LOCATOR_PART_FORBID in part:
            raise ValueError(f"{name} must not contain '::'")
    return f"{filing_id}::{statement_role}::{line_item}"
