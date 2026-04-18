"""Unit tests for :mod:`mvp.store.facts_store`.

Covers both fact sources:

* iXBRL via companyfacts JSON — a fabricated payload served via
  ``httpx.MockTransport`` through an :class:`EdgarClient` passed into
  ``get_facts``.
* manual_extraction via hand-authored YAML — tests both happy and
  malformed-fixture paths.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml

from mvp.lib.edgar import EdgarClient
from mvp.lib.errors import StoreError
from mvp.lib.hashing import hash_excerpt
from mvp.store import facts_store
from mvp.store.facts_store import get_facts


# --- Fixtures -----------------------------------------------------------


@pytest.fixture
def isolated_facts_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    (data / "companyfacts").mkdir(parents=True)
    (data / "manual_extractions").mkdir(parents=True)
    (data / "filings").mkdir(parents=True)
    monkeypatch.setattr(facts_store, "_DATA_DIR", data)
    monkeypatch.setattr(facts_store, "_COMPANYFACTS_DIR", data / "companyfacts")
    monkeypatch.setattr(facts_store, "_MANUAL_DIR", data / "manual_extractions")
    monkeypatch.setattr(facts_store, "_FILINGS_DIR", data / "filings")
    return data


def _mk_client(handler: Any) -> EdgarClient:
    return EdgarClient(transport=httpx.MockTransport(handler))


def _fabricate_companyfacts() -> dict[str, Any]:
    return {
        "cik": 1234567,
        "entityName": "Test Co",
        "facts": {
            "dei": {},
            "us-gaap": {
                "Revenues": {
                    "label": "Revenues",
                    "description": "",
                    "units": {
                        "USD": [
                            {
                                "start": "2023-01-01",
                                "end": "2023-12-31",
                                "val": 1_000_000_000,
                                "accn": "0001234567-24-000001",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                            {
                                "start": "2022-01-01",
                                "end": "2022-12-31",
                                "val": 800_000_000,
                                "accn": "0001234567-24-000001",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                            {
                                # Different accession — MUST be filtered out.
                                "start": "2021-01-01",
                                "end": "2021-12-31",
                                "val": 500_000_000,
                                "accn": "0000999999-22-000001",
                                "fy": 2021,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2022-02-15",
                            },
                        ]
                    },
                },
                "Assets": {
                    "label": "Total Assets",
                    "description": "",
                    "units": {
                        "USD": [
                            {
                                "end": "2023-12-31",
                                "val": 5_000_000_000,
                                "accn": "0001234567-24-000001",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                        ]
                    },
                },
                "SharesOutstanding": {
                    "label": "shares",
                    "description": "",
                    "units": {
                        # Non-USD units MUST be ignored.
                        "shares": [
                            {
                                "end": "2023-12-31",
                                "val": 100_000_000,
                                "accn": "0001234567-24-000001",
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                        ]
                    },
                },
            },
        },
    }


# --- companyfacts path --------------------------------------------------


def test_companyfacts_happy_path_filters_by_accession(
    isolated_facts_dirs: Path,
) -> None:
    payload = _fabricate_companyfacts()

    def handler(req: httpx.Request) -> httpx.Response:
        assert "CIK0001234567.json" in str(req.url)
        return httpx.Response(200, content=json.dumps(payload).encode("utf-8"))

    with _mk_client(handler) as client:
        facts = get_facts("1234567", "0001234567-24-000001", client=client)

    # 2 Revenues rows for our accession + 1 Assets row = 3. Shares
    # excluded (non-USD). Other accession's row excluded.
    assert len(facts) == 3
    concepts = {f.concept for f in facts}
    assert concepts == {"Revenues", "Assets"}

    # Revenues is duration (has period_start), Assets is instant.
    revs = [f for f in facts if f.concept == "Revenues"]
    assert all(f.period_start is not None for f in revs)
    assets = [f for f in facts if f.concept == "Assets"]
    assert all(a.period_start is None for a in assets)

    # Every fact carries the right source tag and a valid excerpt_hash.
    for f in facts:
        assert f.source == "ixbrl_companyfacts"
        assert len(f.excerpt_hash) == 64
        assert f.value > 0


def test_companyfacts_cache_is_reused(isolated_facts_dirs: Path) -> None:
    payload = _fabricate_companyfacts()
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=json.dumps(payload).encode("utf-8"))

    with _mk_client(handler) as client:
        facts_one = get_facts("1234567", "0001234567-24-000001", client=client)
        facts_two = get_facts("1234567", "0001234567-24-000001", client=client)

    assert call_count == 1
    assert len(facts_one) == len(facts_two)


def test_companyfacts_refresh_forces_redownload(isolated_facts_dirs: Path) -> None:
    payload = _fabricate_companyfacts()
    call_count = 0

    def handler(req: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=json.dumps(payload).encode("utf-8"))

    with _mk_client(handler) as client:
        get_facts("1234567", "0001234567-24-000001", client=client)
        get_facts("1234567", "0001234567-24-000001", client=client, refresh=True)

    assert call_count == 2


def test_companyfacts_non_json_response(isolated_facts_dirs: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json at all")

    with _mk_client(handler) as client, pytest.raises(StoreError) as ei:
        get_facts("1234567", "0001234567-24-000001", client=client)
    assert ei.value.reason == "companyfacts_unavailable"


def test_companyfacts_missing_us_gaap_block(isolated_facts_dirs: Path) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=json.dumps({"facts": {"dei": {}}}).encode("utf-8"))

    with _mk_client(handler) as client, pytest.raises(StoreError) as ei:
        get_facts("1234567", "0001234567-24-000001", client=client)
    assert ei.value.reason == "companyfacts_unavailable"


# --- manual_extraction path --------------------------------------------


def _write_manual(dir_: Path, cik: str, accession: str, payload: dict[str, Any]) -> Path:
    target = dir_ / cik / f"{accession}.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return target


def _valid_manual_payload(cik: str, accession: str) -> dict[str, Any]:
    excerpt = "Total revenues 100,789 40,112 31,260"
    return {
        "filing_id": f"{cik}/{accession}",
        "cik": cik,
        "accession": accession,
        "fiscal_period_end": "2000-12-31",
        "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
        "notes": "test fixture",
        "line_items": [
            {
                "name": "revenue",
                "statement_role": "income_statement",
                "value_usd": 100_789_000_000,
                "unit": "USD",
                "source_excerpt": excerpt,
                "excerpt_hash": hash_excerpt(excerpt),
                "notes": "top-line",
            },
            {
                "name": "total_assets",
                "statement_role": "balance_sheet",
                "value_usd": 65_503_000_000,
                "unit": "USD",
                "source_excerpt": "Total Assets $65,503 $33,381",
                "excerpt_hash": hash_excerpt("Total Assets $65,503 $33,381"),
            },
            {
                "name": "inventory",
                "statement_role": "balance_sheet",
                "value_usd": None,
                "unit": "USD",
                "source_excerpt": "(not reported)",
                "excerpt_hash": hash_excerpt("(not reported)"),
                "notes": "not reported in this filing",
            },
        ],
    }


def test_manual_extraction_happy_path(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"  # one of the pre-iXBRL accessions
    payload = _valid_manual_payload(cik, accession)
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)

    facts = get_facts(cik, accession)
    # The null inventory row is skipped (value_usd: None), so 2 facts.
    assert len(facts) == 2
    names = {f.concept for f in facts}
    assert names == {"revenue", "total_assets"}
    for f in facts:
        assert f.source == "manual_extraction"
    revenue = next(f for f in facts if f.concept == "revenue")
    assert revenue.value == Decimal("100789000000")
    assert revenue.period_start is not None  # duration
    assets = next(f for f in facts if f.concept == "total_assets")
    assert assets.period_start is None  # instant


def test_manual_extraction_missing_fixture(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_not_found"


def test_manual_extraction_invalid_data_quality_flag(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    payload = _valid_manual_payload(cik, accession)
    payload["data_quality_flag"] = "totally-wrong"
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_invalid"


def test_manual_extraction_rejects_non_canonical_name(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    payload = _valid_manual_payload(cik, accession)
    payload["line_items"][0]["name"] = "made_up_line"
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_invalid"


def test_manual_extraction_rejects_bad_excerpt_hash(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    payload = _valid_manual_payload(cik, accession)
    payload["line_items"][0]["excerpt_hash"] = "not-64-hex-chars"
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_invalid"


def test_manual_extraction_detects_duplicate_name(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    payload = _valid_manual_payload(cik, accession)
    payload["line_items"].append(
        dict(payload["line_items"][0])  # duplicate "revenue"
    )
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_invalid"


def test_manual_extraction_empty_line_items(isolated_facts_dirs: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    payload = _valid_manual_payload(cik, accession)
    payload["line_items"] = []
    _write_manual(isolated_facts_dirs / "manual_extractions", cik, accession, payload)
    with pytest.raises(StoreError) as ei:
        get_facts(cik, accession)
    assert ei.value.reason == "manual_extraction_invalid"
