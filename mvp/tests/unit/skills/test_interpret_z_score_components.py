"""Unit tests for interpret_z_score_components."""

from __future__ import annotations

import pytest

from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


@pytest.mark.requires_live_data
def test_happy_path_apple_safe_zone() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_z_score_components")
    out = skill.run(
        {
            "cik": "0000320193",
            "fiscal_year_end": "2023-09-30",
            "components": {"X1": -0.005, "X2": -0.001, "X3": 0.324, "X4": 9.168, "X5": 1.087},
            "z_score": 7.65,
            "z_flag": "safe",
        }
    )
    assert "error" not in out
    assert len(out["component_interpretations"]) == 5
    comp_names = [c["component"] for c in out["component_interpretations"]]
    assert comp_names == ["X1", "X2", "X3", "X4", "X5"]
    assert "safe" in out["overall_interpretation"].lower()
    assert "Apple" in out["overall_interpretation"]


@pytest.mark.requires_live_data
def test_market_data_citation_for_x4() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_z_score_components")
    out = skill.run(
        {
            "cik": "0000320193",
            "fiscal_year_end": "2023-09-30",
            "components": {"X1": -0.005, "X2": -0.001, "X3": 0.324, "X4": 9.168, "X5": 1.087},
            "z_flag": "safe",
        }
    )
    assert "error" not in out
    # Expect one citation whose doc_id is the market-data fixture.
    mve_cits = [c for c in out["citations"] if c["doc_id"] == "market_data/equity_values"]
    assert len(mve_cits) == 1
    assert "market_value_of_equity" in mve_cits[0]["locator"]


@pytest.mark.requires_live_data
def test_indeterminate_composite_when_component_null() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_z_score_components")
    out = skill.run(
        {
            "cik": "0001690820",
            "fiscal_year_end": "2022-12-31",
            "components": {"X1": 0.23, "X2": -0.24, "X3": None, "X4": 0.05, "X5": 1.56},
            "z_flag": "indeterminate",
        }
    )
    assert "error" not in out
    # The X3 entry should have the indeterminate_null severity band.
    x3 = next(c for c in out["component_interpretations"] if c["component"] == "X3")
    assert x3["value"] is None
    assert x3["band_matched"]["severity"] == "indeterminate_null"
    assert any("null_components" in w or "indeterminate" in w.lower() for w in out["warnings"]) or \
           "indeterminate" in out["overall_interpretation"].lower()


def test_error_path_bad_components() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_z_score_components")
    out = skill.run(
        {
            "cik": "0000320193",
            "fiscal_year_end": "2023-09-30",
            "components": [1, 2, 3, 4, 5],  # list, not dict
        }
    )
    assert "error" in out
    assert out["error"]["error_code"] in {"input_validation", "bad_components"}
