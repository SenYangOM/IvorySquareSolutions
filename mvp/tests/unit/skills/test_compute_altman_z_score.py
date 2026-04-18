"""Unit tests for compute_altman_z_score."""

from __future__ import annotations

import pytest

from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


@pytest.mark.requires_live_data
def test_apple_safe_zone() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert "error" not in out
    assert out["flag"] == "safe"
    assert out["z_score"] > 2.99
    assert all(
        out["components"][k] is not None for k in ("X1", "X2", "X3", "X4", "X5")
    )
    # Must carry at least one citation per component source + 1 for market-data.
    doc_ids = {c["doc_id"] for c in out["citations"]}
    assert "market_data/equity_values" in doc_ids


@pytest.mark.requires_live_data
def test_worldcom_distress() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "0000723527", "fiscal_year_end": "2001-12-31"})
    assert "error" not in out
    assert out["flag"] == "distress"
    assert out["z_score"] < 1.81
    assert any(
        "market_value_estimated" in w for w in out["warnings"]
    ), "WorldCom FY2001 should surface the estimated-MVE warning"


@pytest.mark.requires_live_data
def test_enron_grey_zone() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    assert "error" not in out
    assert out["flag"] == "grey_zone"
    assert 1.81 <= out["z_score"] <= 2.99


@pytest.mark.requires_live_data
def test_carvana_indeterminate_x3_null() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "0001690820", "fiscal_year_end": "2022-12-31"})
    assert "error" not in out
    assert out["flag"] == "indeterminate"
    assert out["z_score"] is None
    assert out["components"]["X3"] is None


def test_error_unknown_filing() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "9999999999", "fiscal_year_end": "2030-12-31"})
    assert "error" in out
    assert out["error"]["error_code"] == "unknown_filing"


@pytest.mark.requires_live_data
def test_x5_coefficient_is_exactly_0999() -> None:
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert "error" not in out
    assert out["provenance"]["coefficients"]["X5"] == 0.999


@pytest.mark.requires_live_data
def test_pre_ixbrl_reduces_confidence() -> None:
    """Enron (pre-iXBRL) should land at a lower confidence than Apple (iXBRL)."""
    r = _fresh_registry()
    skill = r.get("compute_altman_z_score")
    enron = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    apple = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert enron["confidence"] < apple["confidence"]
