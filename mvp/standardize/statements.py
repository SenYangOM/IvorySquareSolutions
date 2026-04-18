"""L2 canonical-statement builder.

Takes a filing id (``"<cik>/<accession>"``), pulls facts from
:mod:`mvp.store.facts_store`, and produces three
:class:`mvp.store.schema.CanonicalStatement` objects — one each for
income statement, balance sheet, cash-flow statement — with one
:class:`mvp.store.schema.CanonicalLineItem` per canonical name that the
statement covers.

For each canonical name, the builder tries the concept list in
:data:`mvp.standardize.mappings.CONCEPT_MAPPINGS` in order and picks the
first concept that has a fact matching the filing's fiscal-period-end.
Every mapping attempt (chose / missing_concept / missing_period) is
logged to ``data/standardize_mapping_log.jsonl`` — one line per
``(filing_id × canonical_name)`` pair — so an accounting expert can
review the concept-selection decisions without reading Python.

Output JSON files land under
``data/canonical/<cik>/<accession>/{income_statement,balance_sheet,cash_flow_statement}.json``.
They are overwritten atomically on rebuild.

Citation contract
-----------------
Every line item with a non-null ``value_usd`` carries a
:class:`mvp.lib.citation.Citation` pointing to
``filing_id::<statement_role>::<canonical_name>`` with the right
``excerpt_hash``:

* companyfacts-sourced: sha256(``concept|accession|value|end``) — the
  same hash :func:`mvp.store.facts_store._fact_from_companyfacts_item`
  computes.
* manual-extraction-sourced: the ``excerpt_hash`` from the YAML row.

For null values (concept missing from companyfacts for the period),
the citation's ``excerpt_hash`` is the hash of the canonical sentinel
string ``"<no-fact|{filing_id}|{canonical_name}>"`` — a real but
deliberately non-resolvable hash that round-trips back to a
``missing_concept`` row in the mapping log.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

from mvp.lib.citation import Citation, build_locator
from mvp.lib.errors import StoreError
from mvp.store.doc_store import get_doc
from mvp.store.facts_store import get_facts
from mvp.store.schema import (
    CanonicalLineItem,
    CanonicalStatement,
    DataQualityFlag,
    FactRecord,
    StatementRole,
)

from .mappings import CONCEPT_MAPPINGS, IS_INSTANT_ITEM, LINE_ITEM_STATEMENT

# Paths — tests monkeypatch these.
_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_CANONICAL_DIR = _DATA_DIR / "canonical"
_MAPPING_LOG_PATH = _DATA_DIR / "standardize_mapping_log.jsonl"

_STATEMENT_ROLES: tuple[StatementRole, ...] = (
    "income_statement",
    "balance_sheet",
    "cash_flow_statement",
)


# --- Public API ---------------------------------------------------------


def build_canonical_statements(filing_id: str) -> list[CanonicalStatement]:
    """Return the three canonical statements for ``filing_id``.

    Always returns three :class:`CanonicalStatement` objects (IS, BS, CF)
    in that order. Every canonical line item appears in the output,
    either with a real ``value_usd`` or with ``value_usd=None`` + a
    ``notes`` string explaining why.

    Side effects: appends one line to ``data/standardize_mapping_log.jsonl``
    per canonical line item and writes the three JSON outputs under
    ``data/canonical/<cik>/<accession>/``.
    """
    doc = get_doc(filing_id)  # verifies sha256; propagates StoreError
    fpe = _parse_fpe_from_meta(filing_id)
    is_ixbrl = doc.data_quality_flag != "pre_ixbrl_sgml"
    data_quality_flag: DataQualityFlag = (
        "ixbrl_companyfacts" if is_ixbrl else "pre_ixbrl_sgml_manual_extraction"
    )

    facts = get_facts(doc.cik, doc.accession)

    # Group facts by concept for quick lookup. Multiple facts per concept
    # can exist (different periods, or the same concept reported for
    # both the current and prior year). We keep them all and match by
    # period below.
    by_concept: dict[str, list[FactRecord]] = {}
    for f in facts:
        by_concept.setdefault(f.concept, []).append(f)

    # One pass over all 16 canonical names; bucket results by statement.
    by_statement: dict[StatementRole, list[CanonicalLineItem]] = {r: [] for r in _STATEMENT_ROLES}
    log_rows: list[dict[str, Any]] = []

    for canonical_name, statement_role in LINE_ITEM_STATEMENT.items():
        role_literal = cast(StatementRole, statement_role)
        item, log_row = _resolve_line_item(
            filing_id=filing_id,
            canonical_name=canonical_name,
            statement_role=role_literal,
            fpe=fpe,
            by_concept=by_concept,
            data_quality_flag=data_quality_flag,
        )
        by_statement[role_literal].append(item)
        log_rows.append(log_row)

    # Assemble statements in the canonical IS → BS → CF order.
    statements: list[CanonicalStatement] = []
    for role in _STATEMENT_ROLES:
        stmt = CanonicalStatement(
            filing_id=filing_id,
            cik=doc.cik,
            accession=doc.accession,
            statement_role=role,
            fiscal_period_end=fpe,
            data_quality_flag=data_quality_flag,
            line_items=tuple(by_statement[role]),
        )
        statements.append(stmt)

    _append_mapping_log(log_rows)
    _write_canonical_json(doc.cik, doc.accession, statements)
    return statements


# --- Per-line-item resolution ------------------------------------------


def _resolve_line_item(
    *,
    filing_id: str,
    canonical_name: str,
    statement_role: StatementRole,
    fpe: date,
    by_concept: dict[str, list[FactRecord]],
    data_quality_flag: DataQualityFlag,
) -> tuple[CanonicalLineItem, dict[str, Any]]:
    """Return ``(line_item, mapping_log_row)`` for one canonical name.

    For manual-extraction filings, the fact's concept equals the
    canonical name directly — we still walk the concept list (first
    element is the canonical name itself after we prepend) so both
    paths share one control flow.
    """
    candidates = CONCEPT_MAPPINGS[canonical_name]
    if data_quality_flag == "pre_ixbrl_sgml_manual_extraction":
        # Manual-extraction facts key on the canonical name — prepend it
        # to the candidate list so the lookup finds them. We don't fall
        # through to us-gaap names for these filings; the ordered-list
        # mapping is for companyfacts only.
        candidates = (canonical_name, *candidates)

    tried: list[str] = []
    is_instant = IS_INSTANT_ITEM[canonical_name]

    chose_concept: str | None = None
    chose_fact: FactRecord | None = None
    for concept in candidates:
        tried.append(concept)
        matching = _select_fact_for_period(
            by_concept.get(concept, []),
            fpe=fpe,
            is_instant=is_instant,
        )
        if matching is not None:
            chose_concept = concept
            chose_fact = matching
            break

    citation_retrieved_at = datetime.now(timezone.utc)
    locator = build_locator(filing_id, statement_role, canonical_name)

    if chose_fact is None:
        # No concept matched. Build a null line item with a sentinel
        # citation hash so downstream schema validation still passes.
        reason = "missing_concept" if candidates else "no_candidates"
        sentinel_hash = hashlib.sha256(
            f"<no-fact|{filing_id}|{canonical_name}>".encode("utf-8")
        ).hexdigest()
        item = CanonicalLineItem(
            name=canonical_name,
            value_usd=None,
            unit="USD",
            period_start=None if is_instant else date(fpe.year, 1, 1),
            period_end=fpe,
            citation=Citation(
                doc_id=filing_id,
                statement_role=statement_role,
                locator=locator,
                excerpt_hash=sentinel_hash,
                value=None,
                retrieved_at=citation_retrieved_at,
            ),
            source_concept=None,
            notes=f"No fact found for any of the candidate concepts: {', '.join(tried)}",
        )
        log_row = {
            "filing_id": filing_id,
            "canonical_name": canonical_name,
            "statement_role": statement_role,
            "tried": tried,
            "chose": None,
            "reason": reason,
        }
        return item, log_row

    # We have a fact. Use its excerpt_hash (the store already set it to
    # either the companyfacts triple hash or the YAML's excerpt_hash).
    value_for_citation = float(chose_fact.value)
    # For manual extraction, source_concept is None (the YAML's `name`
    # is the canonical name itself — there's no underlying XBRL tag).
    src_source_is_manual = chose_fact.source == "manual_extraction"
    source_concept = None if src_source_is_manual else chose_concept
    # In the manual path, the first candidate we tried IS the canonical
    # name (prepended above), so a match on it is not noteworthy. In the
    # companyfacts path a fallback-concept match IS noteworthy.
    notes: str | None = None
    matched_the_preferred = chose_concept == candidates[0]
    matched_manual_canonical = src_source_is_manual and chose_concept == canonical_name
    if not matched_the_preferred and not matched_manual_canonical:
        notes = (
            f"Matched fallback concept {chose_concept!r} "
            f"(preferred {candidates[0]!r} not present for this filing period)."
        )

    item = CanonicalLineItem(
        name=canonical_name,
        value_usd=chose_fact.value,
        unit="USD",
        period_start=chose_fact.period_start,
        period_end=chose_fact.period_end,
        citation=Citation(
            doc_id=filing_id,
            statement_role=statement_role,
            locator=locator,
            excerpt_hash=chose_fact.excerpt_hash,
            value=value_for_citation,
            retrieved_at=citation_retrieved_at,
        ),
        source_concept=source_concept,
        notes=notes,
    )
    log_row = {
        "filing_id": filing_id,
        "canonical_name": canonical_name,
        "statement_role": statement_role,
        "tried": tried,
        "chose": chose_concept,
        "reason": "matched",
    }
    return item, log_row


def _select_fact_for_period(
    facts: list[FactRecord],
    *,
    fpe: date,
    is_instant: bool,
) -> FactRecord | None:
    """Return the fact whose period matches the filing's fiscal-period-end, or ``None``.

    For instant facts (balance-sheet): ``period_end == fpe``.

    For duration facts (income / cash-flow): ``period_end == fpe`` AND
    the span is approximately one year — we accept any span ≥300 days
    to cover 52/53-week fiscal-year quirks (e.g. Apple sometimes has
    364 days, sometimes 371). Quarterly facts with the same period_end
    would otherwise leak in; filtering on span ≥300 days excludes
    them cleanly.
    """
    matches: list[FactRecord] = []
    for f in facts:
        if f.period_end != fpe:
            continue
        if is_instant:
            if f.period_start is not None:
                # Instant concept with a start date — not what we want.
                continue
            matches.append(f)
        else:
            if f.period_start is None:
                continue
            span_days = (f.period_end - f.period_start).days
            if span_days < 300:
                # Filter out Q4-only stubs that end on FYE.
                continue
            matches.append(f)
    if not matches:
        return None
    # Multiple candidates can arise when companyfacts reports the same
    # concept under several filings covering the same period; prefer the
    # one whose accession matches the filing we're standardizing.
    # (facts_store already filters to the filing's accession, so
    # ``matches`` is already accession-scoped; this is belt-and-braces.)
    return matches[0]


# --- Fiscal-period-end lookup ------------------------------------------


def _parse_fpe_from_meta(filing_id: str) -> date:
    """Read the filing's fiscal_period_end from its ``meta.json``."""
    cik, accession = filing_id.split("/", 1)
    meta_path = _MVP_ROOT / "data" / "filings" / cik / accession / "meta.json"
    if not meta_path.exists():
        raise StoreError(
            f"meta.json missing for {filing_id}: {meta_path}",
            reason="not_found",
            filing_id=filing_id,
        )
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    raw = meta.get("fiscal_period_end")
    if not isinstance(raw, str):
        raise StoreError(
            f"meta.json for {filing_id} missing fiscal_period_end",
            reason="meta_missing_field",
            filing_id=filing_id,
        )
    return date.fromisoformat(raw)


# --- Output writers ----------------------------------------------------


def _append_mapping_log(rows: list[dict[str, Any]]) -> None:
    _MAPPING_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _MAPPING_LOG_PATH.open("a", encoding="utf-8") as f:
        for row in rows:
            # Stamp each row with a run timestamp so a reviewer can
            # distinguish multiple re-runs in the log.
            row = {"logged_at": datetime.now(timezone.utc).isoformat(), **row}
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _write_canonical_json(
    cik: str,
    accession: str,
    statements: list[CanonicalStatement],
) -> None:
    out_dir = _CANONICAL_DIR / cik / accession
    out_dir.mkdir(parents=True, exist_ok=True)
    for stmt in statements:
        out_path = out_dir / f"{stmt.statement_role}.json"
        payload = _statement_to_jsonable(stmt)
        stage = out_path.with_suffix(".json.partial")
        stage.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=_json_default) + "\n",
            encoding="utf-8",
        )
        stage.replace(out_path)


def _statement_to_jsonable(stmt: CanonicalStatement) -> dict[str, Any]:
    return stmt.model_dump(mode="json")


def _json_default(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        # Emit Decimal as its string form — preserves full precision
        # while staying JSON-valid.
        return str(obj)
    raise TypeError(f"type not JSON-serialisable: {type(obj).__name__}")


__all__ = [
    "build_canonical_statements",
]
