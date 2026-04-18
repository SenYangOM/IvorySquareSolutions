"""End-to-end integration test for the Phase 5 eval gate.

Runs the real eval runner against the 10 authored gold YAMLs and
asserts the §4.2 pass-rate targets:

- m_score_within_0.10 >= 4/5
- m_score_flag_match_rate >= 4/5
- z_score_within_0.10 >= 4/5
- z_score_zone_match_rate >= 4/5
- citation_resolves = 100%
- gold_present_for_all_cases == total_yaml_count

This is the gate-passing test for success_criteria.md §1 item 2.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.eval.citation_check import check_citations
from mvp.eval.runner import run_eval
from mvp.skills.registry import Registry, reset_default_registry


_MVP_ROOT = Path(__file__).resolve().parents[2]
_GOLD_ROOT = _MVP_ROOT / "eval" / "gold"


@pytest.fixture(autouse=True)
def _fresh_registry() -> None:
    """Each test gets a fresh registry so ordering doesn't matter."""
    reset_default_registry()


@pytest.mark.requires_live_data
def test_eval_runner_meets_phase5_gate() -> None:
    report = run_eval(gold_root=_GOLD_ROOT, write_report=False)
    m = report.metrics
    # §4.2 gate: ≥ 4/5 on both score-within and flag-match for both skills.
    assert m.m_score_within_0_10[0] >= 4, report.metrics
    assert m.m_score_flag_match_rate[0] >= 4, report.metrics
    assert m.z_score_within_0_10[0] >= 4, report.metrics
    assert m.z_score_zone_match_rate[0] >= 4, report.metrics
    # All gold files load (≥ 10 MVP cases; paper-onboarding iterations
    # may grow this). Numerator must equal denominator.
    assert m.gold_present_for_all_cases[0] == m.gold_present_for_all_cases[1]
    assert m.gold_present_for_all_cases[0] >= 10


def test_eval_runner_surfaces_worldcom_known_deviation() -> None:
    """WorldCom Beneish is the documented 1-of-5 fail; must be surfaced as explainable."""
    report = run_eval(gold_root=_GOLD_ROOT, write_report=False)
    wc = next(
        (r for r in report.cases if r.case_id == "worldcom_2001_beneish"), None
    )
    assert wc is not None
    assert not wc.within_tolerance
    assert wc.explainable_failure is not None
    assert "TATA approximation" in wc.explainable_failure


@pytest.mark.requires_live_data
def test_citation_check_reports_100_pct() -> None:
    """§4.3 gate: zero citation failures."""
    report = check_citations(gold_root=_GOLD_ROOT)
    assert report.total_citations > 0
    assert len(report.failures) == 0, [f.model_dump() for f in report.failures]
    assert report.resolution_rate == 1.0


def test_every_gold_case_loads_and_has_sensible_shape() -> None:
    """Cheap shape-level guards for reviewability.

    The MVP ships 10 gold cases (5 Beneish + 5 Altman). Post-MVP paper-
    onboarding iterations add opportunistic cases per §7 of the
    per-paper criteria — we assert the MVP floor is intact (5 each
    for Beneish and Altman) and that any additional skills that ship
    gold cases at least pass the basic rationale / must-cite shape
    contract.
    """
    from mvp.eval.gold_loader import load_gold_cases

    cases = load_gold_cases(_GOLD_ROOT)
    assert len(cases) >= 10
    # MVP baseline: 5/5 by skill on Beneish + Altman.
    by_skill: dict[str, int] = {}
    for c in cases:
        by_skill[c.skill_id] = by_skill.get(c.skill_id, 0) + 1
    assert by_skill.get("compute_beneish_m_score") == 5
    assert by_skill.get("compute_altman_z_score") == 5
    # Every gold has a non-empty rationale on its score expectation.
    for c in cases:
        assert c.score_expectation.rationale.strip(), c.case_id
    # MVP Beneish + Altman cases all ship ≥ 7 must_cite line items.
    # Post-MVP narrative-layer skills (e.g. mdna_upfrontedness) cite a
    # single MD&A section, so their must_cite list is smaller; we
    # relax to ≥ 1 for those and keep the ≥ 7 bar for the MVP skills
    # where it applies.
    for c in cases:
        if c.skill_id in ("compute_beneish_m_score", "compute_altman_z_score"):
            assert len(c.citation_expectation.must_cite) >= 7, c.case_id
        else:
            assert len(c.citation_expectation.must_cite) >= 1, c.case_id


def test_eval_report_is_pydantic_json_clean() -> None:
    """JSON round-trip equivalence (up to timestamps) for reviewer audit use."""
    report = run_eval(gold_root=_GOLD_ROOT, write_report=False)
    s = report.model_dump_json()
    from mvp.eval.runner import EvalReport

    round_trip = EvalReport.model_validate_json(s)
    assert round_trip.model_dump() == report.model_dump()
