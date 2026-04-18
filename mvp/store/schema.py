"""Pydantic models shared by the L1 store and the L2 standardization layer.

Four models, all frozen + ``extra="forbid"`` so drift between producers and
consumers fails loudly at Pydantic validation time rather than silently
carrying extra fields forward:

* :class:`DocRecord` — a filing as it lives in the L1 doc store
  (``data/filings/<cik>/<accession>/``). Produced by
  :mod:`mvp.store.doc_store`.
* :class:`FactRecord` — one XBRL fact (concept + value + period), either
  sourced from SEC's pre-extracted ``companyfacts`` JSON or from a
  hand-authored manual-extraction YAML for pre-iXBRL filings. Produced
  by :mod:`mvp.store.facts_store`.
* :class:`CanonicalLineItem` — one line on a canonical statement (e.g.
  ``revenue``), carrying the value, unit, the period it covers, the
  citation back to source, and the raw XBRL ``source_concept`` (or
  ``None`` for manually extracted items).
* :class:`CanonicalStatement` — the three canonical statements
  (``income_statement``, ``balance_sheet``, ``cash_flow_statement``)
  produced by :mod:`mvp.standardize.statements`.

All values in ``value_usd`` are expressed in whole US dollars (fully
scaled). A missing value is represented by ``value_usd=None`` + a
``notes`` string explaining why — never a ``0``. This rule is enforced
only at the convention level (Pydantic allows both); the canonical
statement builder is the only producer and it honours it.

The ``statement_role`` / ``line_item`` naming vocabulary is fixed here
so downstream rule templates and skill manifests can reference it
without re-deriving it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from mvp.lib.citation import Citation

# --- Literal type aliases -----------------------------------------------

StatementRole = Literal["income_statement", "balance_sheet", "cash_flow_statement"]
"""The three canonical statement roles we emit. Narrow-on-purpose."""

CanonicalUnit = Literal["USD", "USD_thousands", "USD_millions", "shares", "ratio"]
"""Unit tags for canonical line items. ``USD`` means fully scaled dollars."""

FactSource = Literal["ixbrl_companyfacts", "manual_extraction"]
"""Where a :class:`FactRecord` came from."""

DataQualityFlag = Literal["ixbrl_companyfacts", "pre_ixbrl_sgml_manual_extraction"]
"""Tagged on every :class:`CanonicalStatement` so downstream confidence
degrades automatically for manually extracted pre-iXBRL filings."""


# --- Doc store ----------------------------------------------------------


class DocRecord(BaseModel):
    """A single immutable filing in the L1 doc store.

    Attributes
    ----------
    doc_id:
        Stable identifier of the form ``"<cik>/<accession>"`` — the same
        string used in :class:`Citation.doc_id` everywhere downstream. No
        ``"::"`` because that separator is reserved for locators.
    cik:
        10-digit zero-padded issuer CIK.
    accession:
        Dashed accession number (``"0000320193-23-000106"``).
    source_path:
        Absolute path to the primary document on disk.
    content_type:
        Best-effort MIME type inferred from the extension: ``"text/html"``,
        ``"text/plain"``, or ``"application/octet-stream"`` as a fallback.
    sha256:
        64-char lowercase hex digest of the primary-document bytes.
        Recomputed on read to detect silent corruption (P2).
    byte_len:
        Size of the primary document in bytes.
    fetched_at:
        When the filing was fetched from EDGAR (recorded by L0 ingestion).
    data_quality_flag:
        Optional flag copied from the ingestion ``meta.json``. Present for
        pre-iXBRL filings (value ``"pre_ixbrl_sgml"``), absent for iXBRL
        filings. Used by L2 to decide the manual-vs-companyfacts path.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    doc_id: str = Field(min_length=3)
    cik: str = Field(pattern=r"^\d{10}$")
    accession: str = Field(min_length=1)
    source_path: str = Field(min_length=1)
    content_type: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_len: int = Field(ge=0)
    fetched_at: datetime
    data_quality_flag: str | None = None


# --- Facts store --------------------------------------------------------


class FactRecord(BaseModel):
    """A single XBRL-concept fact, period-annotated.

    For facts sourced from companyfacts JSON the structure maps 1:1 onto
    an entry under ``facts.us-gaap.<Concept>.units.USD[]``. For facts
    sourced from manual extraction, ``concept`` is the canonical line-item
    name (e.g. ``"revenue"``) — there is no real XBRL concept behind it —
    and ``context_ref`` is ``None``.

    Attributes
    ----------
    cik:
        10-digit zero-padded issuer CIK.
    accession:
        Dashed accession number this fact was reported in.
    concept:
        For companyfacts: the us-gaap element name (e.g. ``"Assets"``,
        ``"RevenueFromContractWithCustomerExcludingAssessedTax"``).
        For manual_extraction: the canonical line-item name.
    value:
        Fully scaled value in ``unit``. Integers come in as ``int``; we
        widen to ``Decimal`` via Pydantic's coercion for safe arithmetic.
    unit:
        Unit tag (``"USD"`` for nearly everything at MVP).
    period_start:
        Duration-fact start date; ``None`` for instant facts (balance
        sheet items).
    period_end:
        Duration-fact end date OR instant-fact as-of date. Always present.
    decimals:
        XBRL ``decimals`` attribute from the source filing. ``None`` when
        companyfacts doesn't include it (it usually doesn't) or for
        manual-extraction facts.
    context_ref:
        Original XBRL context reference, if retained. ``None`` for
        companyfacts-sourced facts (not carried through) and for
        manual-extraction facts.
    source:
        ``"ixbrl_companyfacts"`` or ``"manual_extraction"``.
    excerpt_hash:
        For manual_extraction: the sha256 of the normalized source excerpt.
        For companyfacts: a deterministic hash over
        ``(concept|accession|value|end)`` — enough to round-trip back to
        the companyfacts triple when resolving a citation.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cik: str = Field(pattern=r"^\d{10}$")
    accession: str = Field(min_length=1)
    concept: str = Field(min_length=1)
    value: Decimal
    unit: str = Field(min_length=1)
    period_start: date | None = None
    period_end: date
    decimals: int | None = None
    context_ref: str | None = None
    source: FactSource
    excerpt_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


# --- Canonical statements (L2 output) -----------------------------------


class CanonicalLineItem(BaseModel):
    """One line on a canonical statement.

    A line with a genuinely missing value (e.g. pre-iXBRL filing that
    does not split out a component) carries ``value_usd=None`` and a
    ``notes`` string explaining why. Consumers must treat ``None`` as
    "not available" — never as zero.

    Attributes
    ----------
    name:
        Canonical name from the flat list in §2 of the Phase 2 brief
        (e.g. ``"revenue"``, ``"trade_receivables_net"``).
    value_usd:
        Scalar value in whole US dollars. ``None`` for not-available.
    unit:
        One of :data:`CanonicalUnit`. Almost always ``"USD"``.
    period_start:
        Start of the period for duration-type items; ``None`` for
        instant-type items.
    period_end:
        End of the period (duration) or as-of date (instant).
    citation:
        Provenance record pointing back to the source (companyfacts
        triple, or the manual-extraction YAML row).
    source_concept:
        For companyfacts-sourced items: the us-gaap element that matched.
        For manual-extraction items: ``None`` (the concept is the canonical
        name itself).
    notes:
        Free-form annotation: always populated when ``value_usd is None``,
        otherwise optional (e.g. ``"reported as operating income; no
        separate EBIT line"``).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    value_usd: Decimal | None = None
    unit: CanonicalUnit = "USD"
    period_start: date | None = None
    period_end: date
    citation: Citation
    source_concept: str | None = None
    notes: str | None = None


class CanonicalStatement(BaseModel):
    """One of the three canonical statements for a single filing.

    Attributes
    ----------
    filing_id:
        Doc-store doc_id of the form ``"<cik>/<accession>"``.
    cik, accession:
        Denormalised for consumer convenience; must match ``filing_id``.
    statement_role:
        ``income_statement`` / ``balance_sheet`` / ``cash_flow_statement``.
    fiscal_period_end:
        The filing's fiscal-period-end date. Balance-sheet items use this
        as their instant date; income-statement / cash-flow items use
        their own period_start/period_end per the source.
    data_quality_flag:
        ``"ixbrl_companyfacts"`` for iXBRL filings, or
        ``"pre_ixbrl_sgml_manual_extraction"`` for the four SGML filings.
    line_items:
        All 16 canonical line items (see the Phase 2 brief). Items
        with no available value still appear, with ``value_usd=None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    filing_id: str = Field(min_length=3)
    cik: str = Field(pattern=r"^\d{10}$")
    accession: str = Field(min_length=1)
    statement_role: StatementRole
    fiscal_period_end: date
    data_quality_flag: DataQualityFlag
    line_items: tuple[CanonicalLineItem, ...]


__all__ = [
    "CanonicalLineItem",
    "CanonicalStatement",
    "CanonicalUnit",
    "DataQualityFlag",
    "DocRecord",
    "FactRecord",
    "FactSource",
    "StatementRole",
]
