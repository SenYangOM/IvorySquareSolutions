"""Registry unit tests.

Covers auto-discovery, version routing, catalog projections, and
error-raising on missing skills.
"""

from __future__ import annotations

import pytest

from mvp.skills.registry import Registry, reset_default_registry


EXPECTED_SKILL_IDS = {
    # 7 MVP skills (Phases 4–6)
    "extract_canonical_statements",
    "extract_mdna",
    "compute_beneish_m_score",
    "compute_altman_z_score",
    "interpret_m_score_components",
    "interpret_z_score_components",
    "analyze_for_red_flags",
    # Post-MVP paper_examples/ iteration 1 (fundamentals_text.pdf)
    "compute_mdna_upfrontedness",
    # Post-MVP paper_examples/ iteration 2 (kim_2024_context_based_interpretation.pdf)
    "compute_context_importance_signals",
    # Post-MVP paper_examples/ iteration 3 (bernard_2025_information_acquisition.pdf)
    "compute_business_complexity_signals",
    # Post-MVP paper_examples/ iteration 4 (ssrn-4429658.pdf; de Kok 2024)
    "compute_nonanswer_hedging_density",
    # Post-MVP paper_examples/ iteration 5 (ssrn-4480309.pdf; Bernard, Blankespoor, de Kok & Toynbee 2025)
    "predict_filing_complexity_from_determinants",
}


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


def test_bootstrap_discovers_all_expected_skills() -> None:
    r = _fresh_registry()
    ids = set(r.ids())
    missing = EXPECTED_SKILL_IDS - ids
    assert not missing, f"bootstrap missed: {missing}"
    # Should not pick up any extras from orphan dirs.
    assert EXPECTED_SKILL_IDS.issubset(ids)


def test_get_returns_latest_when_version_not_pinned() -> None:
    r = _fresh_registry()
    skill = r.get("compute_beneish_m_score")
    assert skill.id == "compute_beneish_m_score"
    assert skill.manifest.version == "0.1.0"


def test_get_with_explicit_version() -> None:
    r = _fresh_registry()
    skill = r.get("analyze_for_red_flags", version="0.1.0")
    assert skill.manifest.version == "0.1.0"


def test_get_unknown_skill_raises_key_error() -> None:
    r = _fresh_registry()
    with pytest.raises(KeyError):
        r.get("skill_that_does_not_exist")


def test_get_unknown_version_raises_key_error() -> None:
    r = _fresh_registry()
    with pytest.raises(KeyError):
        r.get("compute_beneish_m_score", version="9.9.9")


def test_mcp_catalog_shape() -> None:
    r = _fresh_registry()
    catalog = r.mcp_catalog()
    assert len(catalog) == len(EXPECTED_SKILL_IDS)
    for spec in catalog:
        assert set(spec.keys()) == {"name", "description", "inputSchema"}
        assert spec["inputSchema"].get("type") == "object"


def test_openai_catalog_shape() -> None:
    r = _fresh_registry()
    catalog = r.openai_catalog()
    assert len(catalog) == len(EXPECTED_SKILL_IDS)
    for spec in catalog:
        assert spec.get("type") == "function"
        fn = spec["function"]
        assert "name" in fn and "description" in fn and "parameters" in fn


def test_bootstrap_is_idempotent() -> None:
    r = _fresh_registry()
    before = len(r.list_skills())
    r.bootstrap()
    r.bootstrap()
    assert len(r.list_skills()) == before


def test_double_registration_raises() -> None:
    r = _fresh_registry()
    skill_cls = type(r.get("extract_mdna"))
    with pytest.raises(ValueError, match="already registered"):
        r.register(skill_cls)
