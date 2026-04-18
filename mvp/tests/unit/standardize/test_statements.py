"""Unit tests for :mod:`mvp.standardize.statements`.

Hermetic: fabricates a ``data/filings/`` + ``data/companyfacts/``
fixture under ``tmp_path`` and monkeypatches the module-level paths in
all three modules that touch these trees (``doc_store``,
``facts_store``, ``statements``). No network; no real files.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from mvp.lib.hashing import hash_excerpt, sha256_bytes
from mvp.standardize import statements as stmt_mod
from mvp.standardize.statements import build_canonical_statements
from mvp.store import doc_store, facts_store


# --- Fixtures -----------------------------------------------------------


@pytest.fixture
def isolated_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    data = tmp_path / "data"
    (data / "filings").mkdir(parents=True)
    (data / "companyfacts").mkdir(parents=True)
    (data / "manual_extractions").mkdir(parents=True)
    (data / "canonical").mkdir(parents=True)
    # Wire every module to the sandbox.
    monkeypatch.setattr(doc_store, "_DATA_DIR", data)
    monkeypatch.setattr(doc_store, "_FILINGS_DIR", data / "filings")
    monkeypatch.setattr(facts_store, "_DATA_DIR", data)
    monkeypatch.setattr(facts_store, "_COMPANYFACTS_DIR", data / "companyfacts")
    monkeypatch.setattr(facts_store, "_MANUAL_DIR", data / "manual_extractions")
    monkeypatch.setattr(facts_store, "_FILINGS_DIR", data / "filings")
    monkeypatch.setattr(stmt_mod, "_MVP_ROOT", tmp_path)
    monkeypatch.setattr(stmt_mod, "_DATA_DIR", data)
    monkeypatch.setattr(stmt_mod, "_CANONICAL_DIR", data / "canonical")
    monkeypatch.setattr(stmt_mod, "_MAPPING_LOG_PATH", data / "standardize_mapping_log.jsonl")
    return data


def _write_filing(
    data: Path,
    cik: str,
    accession: str,
    *,
    body: bytes,
    ext: str = ".htm",
    fpe: str = "2023-12-31",
    data_quality_flag: str | None = None,
) -> str:
    fd = data / "filings" / cik / accession
    fd.mkdir(parents=True, exist_ok=True)
    (fd / f"primary_document{ext}").write_bytes(body)
    meta: dict[str, Any] = {
        "cik": cik,
        "accession_number": accession,
        "filing_type": "10-K",
        "fiscal_period_end": fpe,
        "filed_at": "2024-02-15",
        "source_url": "https://example.invalid/",
        "primary_document": f"p{ext}",
        "primary_document_ext": ext,
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sha256": sha256_bytes(body),
        "size_bytes": len(body),
    }
    if data_quality_flag is not None:
        meta["data_quality_flag"] = data_quality_flag
    (fd / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return f"{cik}/{accession}"


def _fake_companyfacts(cik: str, accession: str, fy_end: str = "2023-12-31") -> dict[str, Any]:
    """Minimal companyfacts payload with Revenues, Assets, and CFO."""
    fy_start = "2023-01-01"
    return {
        "cik": int(cik),
        "entityName": "Test Co",
        "facts": {
            "dei": {},
            "us-gaap": {
                "RevenueFromContractWithCustomerExcludingAssessedTax": {
                    "label": "Rev",
                    "description": "",
                    "units": {
                        "USD": [
                            {
                                "start": fy_start,
                                "end": fy_end,
                                "val": 1_000_000_000,
                                "accn": accession,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                        ]
                    },
                },
                "Assets": {
                    "label": "A",
                    "description": "",
                    "units": {
                        "USD": [
                            {
                                "end": fy_end,
                                "val": 5_000_000_000,
                                "accn": accession,
                                "fy": 2023,
                                "fp": "FY",
                                "form": "10-K",
                                "filed": "2024-02-15",
                            },
                        ]
                    },
                },
                "NetCashProvidedByUsedInOperatingActivities": {
                    "label": "CFO",
                    "description": "",
                    "units": {
                        "USD": [
                            {
                                "start": fy_start,
                                "end": fy_end,
                                "val": 300_000_000,
                                "accn": accession,
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


# --- iXBRL path tests --------------------------------------------------


def test_ixbrl_path_builds_three_statements(isolated_tree: Path) -> None:
    cik = "0000321000"
    accession = "0000321000-24-000001"
    fid = _write_filing(isolated_tree, cik, accession, body=b"<html>x</html>")
    # Plant a companyfacts cache so no HTTP.
    (isolated_tree / "companyfacts" / f"CIK{cik}.json").write_text(
        json.dumps(_fake_companyfacts(cik, accession)), encoding="utf-8"
    )

    stmts = build_canonical_statements(fid)
    assert len(stmts) == 3
    roles = [s.statement_role for s in stmts]
    assert roles == ["income_statement", "balance_sheet", "cash_flow_statement"]
    for s in stmts:
        assert s.data_quality_flag == "ixbrl_companyfacts"
        # Every statement has its full line-item complement.
        names = {li.name for li in s.line_items}
        if s.statement_role == "income_statement":
            assert {"revenue", "ebit", "cost_of_goods_sold"} <= names
        elif s.statement_role == "balance_sheet":
            assert {"total_assets", "retained_earnings"} <= names
        elif s.statement_role == "cash_flow_statement":
            assert {"cash_flow_from_operating_activities"} == names


def test_ixbrl_revenue_gets_real_value_and_citation(isolated_tree: Path) -> None:
    cik = "0000321000"
    accession = "0000321000-24-000001"
    fid = _write_filing(isolated_tree, cik, accession, body=b"<html>x</html>")
    (isolated_tree / "companyfacts" / f"CIK{cik}.json").write_text(
        json.dumps(_fake_companyfacts(cik, accession)), encoding="utf-8"
    )
    stmts = build_canonical_statements(fid)
    is_stmt = next(s for s in stmts if s.statement_role == "income_statement")
    rev = next(li for li in is_stmt.line_items if li.name == "revenue")
    assert rev.value_usd is not None and int(rev.value_usd) == 1_000_000_000
    assert rev.source_concept == "RevenueFromContractWithCustomerExcludingAssessedTax"
    assert rev.citation.doc_id == fid
    assert rev.citation.locator.endswith("::income_statement::revenue")
    assert len(rev.citation.excerpt_hash) == 64


def test_ixbrl_missing_concept_returns_null_with_notes(isolated_tree: Path) -> None:
    cik = "0000321000"
    accession = "0000321000-24-000001"
    fid = _write_filing(isolated_tree, cik, accession, body=b"<html>x</html>")
    (isolated_tree / "companyfacts" / f"CIK{cik}.json").write_text(
        json.dumps(_fake_companyfacts(cik, accession)), encoding="utf-8"
    )
    stmts = build_canonical_statements(fid)
    is_stmt = next(s for s in stmts if s.statement_role == "income_statement")
    # COGS wasn't provided in the fabricated payload.
    cogs = next(li for li in is_stmt.line_items if li.name == "cost_of_goods_sold")
    assert cogs.value_usd is None
    assert cogs.notes is not None
    assert cogs.source_concept is None
    # Citation exists but points to a sentinel hash, still 64-hex.
    assert len(cogs.citation.excerpt_hash) == 64


def test_mapping_log_records_every_line_item(isolated_tree: Path) -> None:
    cik = "0000321000"
    accession = "0000321000-24-000001"
    fid = _write_filing(isolated_tree, cik, accession, body=b"<html>x</html>")
    (isolated_tree / "companyfacts" / f"CIK{cik}.json").write_text(
        json.dumps(_fake_companyfacts(cik, accession)), encoding="utf-8"
    )
    build_canonical_statements(fid)
    log_path = isolated_tree / "standardize_mapping_log.jsonl"
    rows = [json.loads(line) for line in log_path.read_text().splitlines() if line.strip()]
    # 16 canonical line items → 16 rows per run.
    assert len(rows) == 16
    for r in rows:
        assert r["filing_id"] == fid
        assert r["canonical_name"] in {
            "revenue", "cost_of_goods_sold", "gross_profit",
            "selling_general_admin_expense", "depreciation_and_amortization",
            "ebit", "trade_receivables_net", "inventory",
            "property_plant_equipment_net", "total_assets", "current_assets",
            "current_liabilities", "long_term_debt", "total_liabilities",
            "retained_earnings", "cash_flow_from_operating_activities",
        }
        assert r["reason"] in {"matched", "missing_concept"}


def test_canonical_json_files_are_written(isolated_tree: Path) -> None:
    cik = "0000321000"
    accession = "0000321000-24-000001"
    fid = _write_filing(isolated_tree, cik, accession, body=b"<html>x</html>")
    (isolated_tree / "companyfacts" / f"CIK{cik}.json").write_text(
        json.dumps(_fake_companyfacts(cik, accession)), encoding="utf-8"
    )
    build_canonical_statements(fid)
    out_dir = isolated_tree / "canonical" / cik / accession
    for role in ("income_statement", "balance_sheet", "cash_flow_statement"):
        assert (out_dir / f"{role}.json").exists()
    is_json = json.loads((out_dir / "income_statement.json").read_text())
    assert is_json["statement_role"] == "income_statement"
    assert is_json["filing_id"] == fid
    assert any(li["name"] == "revenue" for li in is_json["line_items"])


# --- manual_extraction path tests ---------------------------------------


def _write_manual_yaml(data: Path, cik: str, accession: str, fpe: str) -> None:
    path = data / "manual_extractions" / cik / f"{accession}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    excerpt = "Total revenues 100,789 40,112 31,260"
    payload = {
        "filing_id": f"{cik}/{accession}",
        "cik": cik,
        "accession": accession,
        "fiscal_period_end": fpe,
        "data_quality_flag": "pre_ixbrl_sgml_manual_extraction",
        "notes": "unit test fixture",
        "line_items": [
            {
                "name": "revenue",
                "statement_role": "income_statement",
                "value_usd": 100_789_000_000,
                "unit": "USD",
                "source_excerpt": excerpt,
                "excerpt_hash": hash_excerpt(excerpt),
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
                "name": "cash_flow_from_operating_activities",
                "statement_role": "cash_flow_statement",
                "value_usd": 4_779_000_000,
                "unit": "USD",
                "source_excerpt": "Net Cash Provided by Operating Activities 4,779 1,228 1,640",
                "excerpt_hash": hash_excerpt(
                    "Net Cash Provided by Operating Activities 4,779 1,228 1,640"
                ),
            },
        ],
    }
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")


def test_manual_path_tags_pre_ixbrl_data_quality(isolated_tree: Path) -> None:
    # Use one of the known pre-iXBRL accessions so facts_store routes to
    # the manual_extractions YAML.
    cik = "0001024401"
    accession = "0001024401-01-500010"
    fid = _write_filing(
        isolated_tree,
        cik,
        accession,
        body=b"sgml body",
        ext=".txt",
        fpe="2000-12-31",
        data_quality_flag="pre_ixbrl_sgml",
    )
    _write_manual_yaml(isolated_tree, cik, accession, "2000-12-31")
    stmts = build_canonical_statements(fid)
    for s in stmts:
        assert s.data_quality_flag == "pre_ixbrl_sgml_manual_extraction"


def test_manual_path_uses_yaml_excerpt_hash(isolated_tree: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    fid = _write_filing(
        isolated_tree, cik, accession, body=b"body", ext=".txt",
        fpe="2000-12-31", data_quality_flag="pre_ixbrl_sgml",
    )
    _write_manual_yaml(isolated_tree, cik, accession, "2000-12-31")
    stmts = build_canonical_statements(fid)
    is_stmt = next(s for s in stmts if s.statement_role == "income_statement")
    rev = next(li for li in is_stmt.line_items if li.name == "revenue")
    assert rev.value_usd is not None
    # The excerpt_hash on the citation must match the YAML-recorded hash
    # (hash_excerpt of the source_excerpt).
    assert rev.citation.excerpt_hash == hash_excerpt(
        "Total revenues 100,789 40,112 31,260"
    )


def test_manual_path_period_dates(isolated_tree: Path) -> None:
    cik = "0001024401"
    accession = "0001024401-01-500010"
    fid = _write_filing(
        isolated_tree, cik, accession, body=b"body", ext=".txt",
        fpe="2000-12-31", data_quality_flag="pre_ixbrl_sgml",
    )
    _write_manual_yaml(isolated_tree, cik, accession, "2000-12-31")
    stmts = build_canonical_statements(fid)
    is_stmt = next(s for s in stmts if s.statement_role == "income_statement")
    bs_stmt = next(s for s in stmts if s.statement_role == "balance_sheet")
    rev = next(li for li in is_stmt.line_items if li.name == "revenue")
    ta = next(li for li in bs_stmt.line_items if li.name == "total_assets")
    assert rev.period_start == date(2000, 1, 1)
    assert rev.period_end == date(2000, 12, 31)
    assert ta.period_start is None
    assert ta.period_end == date(2000, 12, 31)
