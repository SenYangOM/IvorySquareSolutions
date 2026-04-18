"""Unit tests for analyze_for_red_flags (L4 composite)."""

from __future__ import annotations

import pytest

from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


@pytest.mark.requires_live_data
def test_enron_happy_path() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags")
    out = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    assert "error" not in out
    m = out["m_score_result"]
    z = out["z_score_result"]
    assert m["flag"] == "manipulator_likely"
    assert z["flag"] == "grey_zone"
    assert m["interpretations"], "must include per-component interpretations"
    assert z["interpretations"]
    # Provenance block is well-formed.
    prov = out["provenance"]
    assert prov["composite_skill_id"] == "analyze_for_red_flags"
    assert prov["composite_version"] == "0.1.0"
    assert set(prov["sub_skill_versions"].keys()) == {
        "compute_beneish_m_score",
        "compute_altman_z_score",
        "interpret_m_score_components",
        "interpret_z_score_components",
    }


@pytest.mark.requires_live_data
def test_apple_negative_control() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert "error" not in out
    assert out["m_score_result"]["flag"] == "manipulator_unlikely"
    assert out["z_score_result"]["flag"] == "safe"


@pytest.mark.requires_live_data
def test_carvana_indeterminate_cases() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags")
    out = skill.run({"cik": "0001690820", "fiscal_year_end": "2022-12-31"})
    assert "error" not in out
    assert out["m_score_result"]["flag"] == "indeterminate"
    assert out["z_score_result"]["flag"] == "indeterminate"


def test_error_unknown_filing_bubbles() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags")
    out = skill.run({"cik": "9999999999", "fiscal_year_end": "2030-12-31"})
    assert "error" in out
    # Composite should surface the sub-skill's error code with our prefix.
    assert out["error"]["error_code"].startswith("sub_skill_error.")


def test_determinism_two_back_to_back_runs() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags")
    a = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    b = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    # Redact timestamps + run ids.
    def redact(obj):
        if isinstance(obj, dict):
            return {
                k: ("<redacted>" if k in {"run_id", "run_at", "retrieved_at"} else redact(v))
                for k, v in obj.items()
            }
        if isinstance(obj, list):
            return [redact(x) for x in obj]
        return obj
    assert redact(a) == redact(b)
