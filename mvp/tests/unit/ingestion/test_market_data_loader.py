"""Unit tests for ``mvp.ingestion.market_data_loader``.

Covers:

- Happy-path load of the real on-disk fixture (5 entries, all within
  tolerance).
- Per-validator rule: MVE consistency (1% tolerance), positive numbers,
  ISO date format.
- Structural errors: missing file, malformed YAML, missing 'entries',
  duplicate ``(cik, fiscal_year_end)``.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mvp.ingestion.market_data_loader import (
    EquityValueEntry,
    load_equity_values,
)
from mvp.lib.errors import IngestionError


# -- Helpers --------------------------------------------------------------


def _write(path: Path, payload: dict | list | str) -> Path:
    if isinstance(payload, str):
        path.write_text(payload, encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def _good_entry(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "cik": "0000320193",
        "issuer": "Apple Inc",
        "fiscal_year_end": "2023-09-30",
        "shares_outstanding": 15552752000,
        "share_price_usd": 171.21,
        "market_value_of_equity_usd": 2662807717920,
        "price_source": "https://example.com/price",
        "shares_source": "10-K cover page",
        "notes": "",
    }
    base.update(overrides)
    return base


# -- Happy path against the real fixture ---------------------------------


def test_real_fixture_loads_five_entries() -> None:
    entries = load_equity_values()
    assert len(entries) == 5
    issuers = {e.issuer for e in entries}
    assert issuers == {
        "Enron Corp",
        "WorldCom Inc",
        "Apple Inc",
        "Microsoft Corporation",
        "Carvana Co",
    }
    for e in entries:
        assert isinstance(e, EquityValueEntry)
        assert len(e.cik) == 10 and e.cik.isdigit()
        # MVE consistency is enforced at construction time; re-check here
        # as a belt-and-braces assertion that the fixture stays clean.
        implied = e.shares_outstanding * e.share_price_usd
        assert abs(implied - e.market_value_of_equity_usd) / e.market_value_of_equity_usd <= 0.01


def test_worldcom_flag_surfaces() -> None:
    entries = load_equity_values()
    wc = next(e for e in entries if e.issuer == "WorldCom Inc")
    assert wc.market_cap_source == "estimated_from_aggregated_market_cap"


def test_carvana_flag_surfaces() -> None:
    entries = load_equity_values()
    cv = next(e for e in entries if e.issuer == "Carvana Co")
    assert cv.shares_source_flag == "cover_page_post_fye"


# -- Validator rules -----------------------------------------------------


def test_mve_consistency_violation_raises(tmp_path: Path) -> None:
    # Price off by 10× → MVE massively inconsistent with shares * price.
    bad = _good_entry(share_price_usd=17.12)  # recorded MVE assumed $171.21
    path = _write(tmp_path / "eq.yaml", {"entries": [bad]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "entry_validation"
    assert "tolerance" in str(exc.value)


def test_mve_consistency_just_under_tolerance_passes(tmp_path: Path) -> None:
    # 0.9% drift — under the 1% bar, should load.
    entry = _good_entry(
        shares_outstanding=1_000_000,
        share_price_usd=100.00,
        market_value_of_equity_usd=100_900_000,  # 0.9% above implied 100M
    )
    path = _write(tmp_path / "eq.yaml", {"entries": [entry]})
    entries = load_equity_values(path)
    assert len(entries) == 1


def test_mve_consistency_just_over_tolerance_fails(tmp_path: Path) -> None:
    # 1.5% drift — over the 1% bar.
    entry = _good_entry(
        shares_outstanding=1_000_000,
        share_price_usd=100.00,
        market_value_of_equity_usd=101_500_000,
    )
    path = _write(tmp_path / "eq.yaml", {"entries": [entry]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "entry_validation"


@pytest.mark.parametrize(
    "field,value",
    [
        ("shares_outstanding", 0),
        ("shares_outstanding", -1),
        ("share_price_usd", 0),
        ("share_price_usd", -5.0),
        ("market_value_of_equity_usd", 0),
    ],
)
def test_non_positive_numbers_rejected(
    tmp_path: Path, field: str, value: float
) -> None:
    entry = _good_entry(**{field: value})
    path = _write(tmp_path / "eq.yaml", {"entries": [entry]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "entry_validation"


@pytest.mark.parametrize(
    "date",
    ["2023/09/30", "09-30-2023", "2023-13-01", "2023-09-32", "not-a-date"],
)
def test_invalid_fiscal_year_end_rejected(tmp_path: Path, date: str) -> None:
    entry = _good_entry(fiscal_year_end=date)
    path = _write(tmp_path / "eq.yaml", {"entries": [entry]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "entry_validation"


def test_bad_cik_pattern_rejected(tmp_path: Path) -> None:
    entry = _good_entry(cik="12345")
    path = _write(tmp_path / "eq.yaml", {"entries": [entry]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "entry_validation"


# -- Structural errors ---------------------------------------------------


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(IngestionError) as exc:
        load_equity_values(tmp_path / "does_not_exist.yaml")
    assert exc.value.reason == "yaml_not_found"


def test_malformed_yaml_raises(tmp_path: Path) -> None:
    path = tmp_path / "eq.yaml"
    path.write_text("entries: [\n- foo: bar\n- not valid]]]]", encoding="utf-8")
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "yaml_invalid"


def test_missing_entries_key_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "eq.yaml", {"something_else": []})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "yaml_invalid"


def test_empty_entries_list_raises(tmp_path: Path) -> None:
    path = _write(tmp_path / "eq.yaml", {"entries": []})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "yaml_invalid"


def test_root_not_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / "eq.yaml"
    path.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "yaml_invalid"


def test_entry_not_mapping_raises(tmp_path: Path) -> None:
    path = tmp_path / "eq.yaml"
    path.write_text("entries:\n  - just-a-string\n", encoding="utf-8")
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "yaml_invalid"


def test_duplicate_cik_and_year_raises(tmp_path: Path) -> None:
    e = _good_entry()
    path = _write(tmp_path / "eq.yaml", {"entries": [e, dict(e)]})
    with pytest.raises(IngestionError) as exc:
        load_equity_values(path)
    assert exc.value.reason == "duplicate_cik"
