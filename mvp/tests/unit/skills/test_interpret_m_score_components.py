"""Unit tests for interpret_m_score_components."""

from __future__ import annotations

import pytest

from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


@pytest.mark.requires_live_data
def test_happy_path_enron() -> None:
    r = _fresh_registry()
    m = r.get("compute_beneish_m_score").run(
        {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}
    )
    assert "error" not in m
    skill = r.get("interpret_m_score_components")
    out = skill.run(
        {
            "cik": "0001024401",
            "fiscal_year_end": "2000-12-31",
            "components": m["components"],
            "source_confidence": m.get("confidence"),
        }
    )
    assert "error" not in out
    assert len(out["component_interpretations"]) == 8
    comp_names = [c["component"] for c in out["component_interpretations"]]
    assert comp_names == ["DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA"]
    assert out["overall_interpretation"]
    assert "Enron" in out["overall_interpretation"]
    assert "2000-12-31" in out["overall_interpretation"]
    assert isinstance(out["citations"], list) and out["citations"], "must ship citations"


@pytest.mark.requires_live_data
def test_null_components_are_indeterminate() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_m_score_components")
    out = skill.run(
        {
            "cik": "0001690820",
            "fiscal_year_end": "2022-12-31",
            "components": {
                "DSRI": 1.16,
                "GMI": 1.64,
                "AQI": 1.23,
                "SGI": 1.06,
                "DEPI": None,
                "SGAI": 1.27,
                "LVGI": 1.21,
                "TATA": None,
            },
        }
    )
    assert "error" not in out
    nulls = [
        c["component"]
        for c in out["component_interpretations"]
        if c["value"] is None
    ]
    assert set(nulls) == {"DEPI", "TATA"}
    # indeterminate_null severity is the synthetic band.
    null_severities = [
        c["band_matched"]["severity"]
        for c in out["component_interpretations"]
        if c["value"] is None
    ]
    assert all(s == "indeterminate_null" for s in null_severities)
    # warning should enumerate the nulls.
    assert any("null_components" in w for w in out["warnings"])


def test_error_path_unknown_filing() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_m_score_components")
    out = skill.run(
        {
            "cik": "9999999999",
            "fiscal_year_end": "2024-12-31",
            "components": {
                "DSRI": 1.0, "GMI": 1.0, "AQI": 1.0, "SGI": 1.0,
                "DEPI": 1.0, "SGAI": 1.0, "LVGI": 1.0, "TATA": 0.01,
            },
        }
    )
    assert "error" in out, "unknown filing must return error envelope"
    assert out["error"]["error_code"] == "unknown_filing"


def test_bad_components_type() -> None:
    r = _fresh_registry()
    skill = r.get("interpret_m_score_components")
    out = skill.run(
        {
            "cik": "0000320193",
            "fiscal_year_end": "2023-09-30",
            "components": "not a dict",
        }
    )
    assert "error" in out
    # bad type is caught by either input-schema validation or the runtime check
    assert out["error"]["error_code"] in {"input_validation", "bad_components"}


@pytest.mark.requires_live_data
def test_pre_ixbrl_confidence_cap() -> None:
    """Pre-iXBRL filings cap confidence at 0.7."""
    r = _fresh_registry()
    skill = r.get("interpret_m_score_components")
    out = skill.run(
        {
            "cik": "0001024401",
            "fiscal_year_end": "2000-12-31",
            "components": {
                "DSRI": 1.0, "GMI": 1.0, "AQI": 1.0, "SGI": 1.0,
                "DEPI": 1.0, "SGAI": 1.0, "LVGI": 1.0, "TATA": 0.01,
            },
            "source_confidence": 1.0,
        }
    )
    assert "error" not in out
    assert out["confidence"] <= 0.7, f"confidence should be capped, got {out['confidence']}"
