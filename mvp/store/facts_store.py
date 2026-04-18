"""L1 facts store: unified access to XBRL facts across iXBRL and pre-iXBRL filings.

For the six iXBRL filings (Apple, Microsoft, Carvana) this module fetches
SEC's pre-extracted ``companyfacts`` JSON from
``https://data.sec.gov/api/xbrl/companyfacts/CIK<cik>.json``, caches it
under ``data/companyfacts/CIK<cik>.json``, and filters the per-concept
fact lists to those matching a given ``(cik, accession)``.

For the four pre-iXBRL SGML filings (Enron FY1999/FY2000, WorldCom
FY2000/FY2001) it reads the hand-authored manual-extraction YAML at
``data/manual_extractions/<cik>/<accession>.yaml`` and returns a
synthetic :class:`FactRecord` list tagged ``source="manual_extraction"``.

The returned ``FactRecord`` list is the single substrate the L2
standardize layer (``mvp.standardize.statements``) consumes — it does
not care which source the facts came from.

Cache semantics
---------------
Per-CIK companyfacts JSON is cached under ``data/companyfacts/``. A call
with the cache present is a no-op HTTP-wise; pass ``refresh=True`` to
force a re-download. No size / age based invalidation (the facts
themselves are immutable for a given filing, and a later filing that
restates an earlier period simply appears as an additional fact under a
different ``accn``).

CLI
---
``python -m mvp.store.facts_store --cik <cik> --accession <accession>``
prints the count of ``FactRecord`` entries and the first few concept
names. Purely diagnostic.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from mvp.lib.edgar import EdgarClient, normalize_cik
from mvp.lib.errors import LibError, StoreError

from .schema import FactRecord

# Module-level paths — tests monkeypatch these onto ``tmp_path``.
_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_COMPANYFACTS_DIR = _DATA_DIR / "companyfacts"
_MANUAL_DIR = _DATA_DIR / "manual_extractions"
_FILINGS_DIR = _DATA_DIR / "filings"

# --- Canonical line-item names allowed in manual-extraction YAMLs.
# Import lazily to avoid a circular when standardize/mappings imports
# schema (it doesn't, but this is belt-and-braces).
_CANONICAL_LINE_ITEMS: frozenset[str] = frozenset(
    {
        "revenue",
        "cost_of_goods_sold",
        "gross_profit",
        "selling_general_admin_expense",
        "depreciation_and_amortization",
        "ebit",
        "trade_receivables_net",
        "inventory",
        "property_plant_equipment_net",
        "total_assets",
        "current_assets",
        "current_liabilities",
        "long_term_debt",
        "total_liabilities",
        "retained_earnings",
        "cash_flow_from_operating_activities",
    }
)

_STATEMENT_ROLES: frozenset[str] = frozenset(
    {"income_statement", "balance_sheet", "cash_flow_statement"}
)

# Pre-iXBRL accessions — mirror of the set in ``mvp.ingestion.filings_ingest``
# but we re-declare here to avoid a cross-layer ingestion import from store.
# The set is load-bearing: a filing in this set MUST have a manual_extractions
# YAML and will NOT be looked up in companyfacts.
_PRE_IXBRL_ACCESSIONS: frozenset[str] = frozenset(
    {
        "0001024401-01-500010",
        "0001024401-00-000002",
        "0001005477-02-001226",
        "0000912057-01-505916",
    }
)


# --- Public API ---------------------------------------------------------


def get_facts(
    cik: str,
    accession: str,
    *,
    refresh: bool = False,
    client: EdgarClient | None = None,
) -> list[FactRecord]:
    """Return all facts available for ``(cik, accession)``.

    Parameters
    ----------
    cik:
        10-digit zero-padded CIK (or anything :func:`normalize_cik` accepts).
    accession:
        Dashed EDGAR accession (``"0000320193-23-000106"``). Manually-
        extracted accessions are routed to the YAML reader; all others
        go through companyfacts.
    refresh:
        When ``True`` the per-CIK companyfacts JSON is re-downloaded
        even if a cache exists. No effect for manual-extraction filings.
    client:
        Optional :class:`EdgarClient`. A fresh one is constructed (and
        closed) inside this call when ``None``. Tests inject a
        ``MockTransport``-backed client here.

    Raises
    ------
    StoreError
        - ``reason="manual_extraction_not_found"`` if a pre-iXBRL filing's
          YAML is missing.
        - ``reason="manual_extraction_invalid"`` if the YAML fails schema
          checks.
        - ``reason="companyfacts_unavailable"`` if the SEC endpoint
          returned non-JSON or missing ``facts`` block.
    EdgarHttpError, RateLimitExceeded
        Propagated from the underlying EDGAR client on network/HTTP error.
    """
    cik_norm = normalize_cik(cik)
    if accession in _PRE_IXBRL_ACCESSIONS:
        return _load_manual_extraction(cik_norm, accession)
    return _load_from_companyfacts(cik_norm, accession, refresh=refresh, client=client)


def _load_manual_extraction(cik: str, accession: str) -> list[FactRecord]:
    path = _MANUAL_DIR / cik / f"{accession}.yaml"
    if not path.exists():
        raise StoreError(
            f"manual extraction fixture not found for {cik}/{accession} at {path}",
            reason="manual_extraction_not_found",
            filing_id=f"{cik}/{accession}",
        )
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StoreError(
            f"unable to read manual extraction {path}: {exc}",
            reason="manual_extraction_unreadable",
            filing_id=f"{cik}/{accession}",
        ) from exc
    try:
        payload = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise StoreError(
            f"manual extraction {path} is not valid YAML: {exc}",
            reason="manual_extraction_invalid",
            filing_id=f"{cik}/{accession}",
        ) from exc

    if not isinstance(payload, dict):
        raise StoreError(
            f"manual extraction {path} must be a YAML mapping, got {type(payload).__name__}",
            reason="manual_extraction_invalid",
            filing_id=f"{cik}/{accession}",
        )

    # Top-level header validation.
    expected_filing_id = f"{cik}/{accession}"
    for field in ("filing_id", "cik", "accession", "fiscal_period_end", "data_quality_flag", "line_items"):
        if field not in payload:
            raise StoreError(
                f"manual extraction {path} missing required field {field!r}",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )
    if payload["filing_id"] != expected_filing_id:
        raise StoreError(
            f"manual extraction {path} has filing_id={payload['filing_id']!r}, "
            f"expected {expected_filing_id!r}",
            reason="manual_extraction_invalid",
            filing_id=expected_filing_id,
        )
    if payload["cik"] != cik or payload["accession"] != accession:
        raise StoreError(
            f"manual extraction {path} cik/accession mismatch with request",
            reason="manual_extraction_invalid",
            filing_id=expected_filing_id,
        )
    if payload["data_quality_flag"] != "pre_ixbrl_sgml_manual_extraction":
        raise StoreError(
            f"manual extraction {path} must carry data_quality_flag="
            f"'pre_ixbrl_sgml_manual_extraction'; got {payload['data_quality_flag']!r}",
            reason="manual_extraction_invalid",
            filing_id=expected_filing_id,
        )

    try:
        period_end = date.fromisoformat(str(payload["fiscal_period_end"]))
    except ValueError as exc:
        raise StoreError(
            f"manual extraction {path} has invalid fiscal_period_end: {exc}",
            reason="manual_extraction_invalid",
            filing_id=expected_filing_id,
        ) from exc

    line_items = payload["line_items"]
    if not isinstance(line_items, list) or not line_items:
        raise StoreError(
            f"manual extraction {path} line_items must be a non-empty list",
            reason="manual_extraction_invalid",
            filing_id=expected_filing_id,
        )

    # IS + CF duration-period start is the prior year's FPE + 1 day;
    # BS line items are instant at the FPE. For fiscal periods ending
    # 12/31, that's 1/1 of the same year. For non-calendar fiscal years
    # (Apple 9/30, Microsoft 6/30) this rule still holds; we just don't
    # use it for manual_extraction filings because all four are
    # calendar-year.
    period_start = _infer_period_start(period_end)

    facts: list[FactRecord] = []
    seen_names: set[str] = set()
    for idx, entry in enumerate(line_items):
        if not isinstance(entry, dict):
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] must be a mapping",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )
        for field in ("name", "statement_role", "value_usd", "unit", "source_excerpt", "excerpt_hash"):
            if field not in entry:
                raise StoreError(
                    f"manual extraction {path} line_items[{idx}] missing {field!r}",
                    reason="manual_extraction_invalid",
                    filing_id=expected_filing_id,
                )
        name = str(entry["name"])
        if name not in _CANONICAL_LINE_ITEMS:
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] name={name!r} is not a canonical line item",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )
        if name in seen_names:
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] duplicates name={name!r}",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )
        seen_names.add(name)

        role = str(entry["statement_role"])
        if role not in _STATEMENT_ROLES:
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] statement_role={role!r} invalid",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )

        value_usd_raw = entry["value_usd"]
        value: Decimal
        if value_usd_raw is None:
            # Sentinel for "not reported in this filing". We encode as
            # Decimal("NaN") in the FactRecord so the builder can detect
            # it without a separate field. But schema requires Decimal;
            # use a distinct strategy: skip null facts entirely at the
            # facts_store level. The standardize layer will handle the
            # null by failing to find the concept and recording a
            # missing_concept log entry.
            continue
        try:
            value = Decimal(str(value_usd_raw))
        except Exception as exc:
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] value_usd not a number: {exc}",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            ) from exc

        excerpt_hash = str(entry["excerpt_hash"])
        if len(excerpt_hash) != 64 or not all(c in "0123456789abcdef" for c in excerpt_hash):
            raise StoreError(
                f"manual extraction {path} line_items[{idx}] excerpt_hash must be 64-char hex",
                reason="manual_extraction_invalid",
                filing_id=expected_filing_id,
            )

        is_instant = role == "balance_sheet"
        facts.append(
            FactRecord(
                cik=cik,
                accession=accession,
                concept=name,
                value=value,
                unit=str(entry["unit"]),
                period_start=None if is_instant else period_start,
                period_end=period_end,
                decimals=None,
                context_ref=None,
                source="manual_extraction",
                excerpt_hash=excerpt_hash,
            )
        )
    return facts


def _infer_period_start(fpe: date) -> date:
    """For a calendar-year fiscal-period-end, return Jan 1 of that year.

    The four manual-extraction filings are all calendar-year; for
    non-calendar filers companyfacts already carries the ``start`` date
    directly so this helper is never called on their facts.
    """
    return date(fpe.year, 1, 1)


# --- companyfacts path --------------------------------------------------


def _companyfacts_cache_path(cik: str) -> Path:
    return _COMPANYFACTS_DIR / f"CIK{cik}.json"


def _companyfacts_url(cik: str) -> str:
    return f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"


def _load_from_companyfacts(
    cik: str,
    accession: str,
    *,
    refresh: bool,
    client: EdgarClient | None,
) -> list[FactRecord]:
    cache_path = _companyfacts_cache_path(cik)
    if refresh or not cache_path.exists():
        _download_companyfacts(cik, cache_path, client=client)

    try:
        raw = cache_path.read_bytes()
    except OSError as exc:
        raise StoreError(
            f"unable to read companyfacts cache {cache_path}: {exc}",
            reason="companyfacts_unreadable",
            filing_id=f"{cik}/{accession}",
        ) from exc
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise StoreError(
            f"companyfacts cache {cache_path} is not valid JSON: {exc}",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        ) from exc

    if not isinstance(payload, dict) or "facts" not in payload or "us-gaap" not in payload.get("facts", {}):
        raise StoreError(
            f"companyfacts payload for {cik} missing facts.us-gaap block",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        )

    us_gaap: dict[str, Any] = payload["facts"]["us-gaap"]
    records: list[FactRecord] = []
    for concept, concept_block in us_gaap.items():
        units = concept_block.get("units", {})
        for unit, items in units.items():
            if unit != "USD":
                # We only consume USD facts at MVP; share-count / ratio
                # units are not on the M-Score / Altman path.
                continue
            for item in items:
                if item.get("accn") != accession:
                    continue
                records.append(_fact_from_companyfacts_item(cik, accession, concept, unit, item))
    return records


def _download_companyfacts(cik: str, dest: Path, *, client: EdgarClient | None) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    owns_client = client is None
    active = client if client is not None else EdgarClient()
    try:
        body = active.fetch_document(_companyfacts_url(cik))
    finally:
        if owns_client:
            active.close()
    # Atomic write.
    stage = dest.with_suffix(dest.suffix + ".partial")
    stage.write_bytes(body)
    stage.replace(dest)


def _fact_from_companyfacts_item(
    cik: str,
    accession: str,
    concept: str,
    unit: str,
    item: dict[str, Any],
) -> FactRecord:
    end_raw = item.get("end")
    if not isinstance(end_raw, str):
        raise StoreError(
            f"companyfacts item for {concept} missing 'end' field",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        )
    try:
        period_end = date.fromisoformat(end_raw)
    except ValueError as exc:
        raise StoreError(
            f"companyfacts item {concept} 'end' not ISO date: {exc}",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        ) from exc

    start_raw = item.get("start")
    period_start: date | None = None
    if isinstance(start_raw, str):
        try:
            period_start = date.fromisoformat(start_raw)
        except ValueError as exc:
            raise StoreError(
                f"companyfacts item {concept} 'start' not ISO date: {exc}",
                reason="companyfacts_unavailable",
                filing_id=f"{cik}/{accession}",
            ) from exc

    val = item.get("val")
    if val is None:
        raise StoreError(
            f"companyfacts item {concept} missing 'val'",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        )
    try:
        value = Decimal(str(val))
    except Exception as exc:
        raise StoreError(
            f"companyfacts item {concept} val not numeric: {exc}",
            reason="companyfacts_unavailable",
            filing_id=f"{cik}/{accession}",
        ) from exc

    decimals_raw = item.get("decimals")
    decimals: int | None
    if decimals_raw is None:
        decimals = None
    else:
        try:
            decimals = int(decimals_raw)
        except (TypeError, ValueError):
            decimals = None

    # Deterministic hash over concept|accession|value|end — enough to
    # round-trip back to the companyfacts triple when resolving citations.
    digest_src = f"{concept}|{accession}|{value}|{end_raw}"
    excerpt_hash = hashlib.sha256(digest_src.encode("utf-8")).hexdigest()

    return FactRecord(
        cik=cik,
        accession=accession,
        concept=concept,
        value=value,
        unit=unit,
        period_start=period_start,
        period_end=period_end,
        decimals=decimals,
        context_ref=None,
        source="ixbrl_companyfacts",
        excerpt_hash=excerpt_hash,
    )


# --- CLI ----------------------------------------------------------------


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvp.store.facts_store",
        description="Print the facts-store contents for a single filing.",
    )
    parser.add_argument("--cik", required=True, help="10-digit CIK (or raw int).")
    parser.add_argument("--accession", required=True, help="Dashed EDGAR accession.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Force re-download of companyfacts JSON even if cached.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)
    try:
        facts = get_facts(args.cik, args.accession, refresh=args.refresh)
    except LibError as exc:
        print(f"[error] {exc.error_code}: {exc.message}", file=sys.stderr)
        return 2
    print(f"{len(facts)} facts for {args.cik}/{args.accession}")
    # Show first 10 unique concepts for a quick eyeball.
    concepts_seen: list[str] = []
    for f in facts:
        if f.concept not in concepts_seen:
            concepts_seen.append(f.concept)
        if len(concepts_seen) >= 10:
            break
    for c in concepts_seen:
        print(f"  concept: {c}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
