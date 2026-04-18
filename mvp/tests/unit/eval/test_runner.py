"""Unit tests for mvp.eval.runner.

Covers the runner's pass/fail arithmetic against synthetic gold files
and stub skills — NOT the real 10 gold cases (that's the integration
test). Verifies:

- basic pass path: expected value, tolerance, within band.
- null-matches-null on score (indeterminate case).
- null-vs-number on score → within_tolerance=False.
- indeterminate-matches-indeterminate on flag.
- explainable_failure propagates from gold's known_deviation_explanation.
- must_cite enforcement against actual citations.
- warnings-must-include surfaces when a required warning is absent.
- confidence_in_range.
- metric aggregation (within + flag_match × m/z).
- json report shape is Pydantic-clean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from mvp.eval.gold_loader import load_gold_cases
from mvp.eval.runner import (
    CaseResult,
    EvalReport,
    _compute_metrics,
    _evaluate_case,
    _must_cite_met,
    format_console_report,
    run_eval,
)


# ---------------------------------------------------------------------------
# Stub skill + stub registry fixture.
# ---------------------------------------------------------------------------


class _StubSkill:
    """Skill stub — returns a canned output dict for ``run(inputs)``."""

    def __init__(self, canned_output: dict[str, Any]) -> None:
        self._canned = canned_output

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return self._canned


class _StubRegistry:
    def __init__(self, skills: dict[str, _StubSkill]) -> None:
        self._skills = skills

    def get(self, skill_id: str, *, version: str | None = None) -> _StubSkill:
        return self._skills[skill_id]


def _write_gold(
    gold_root: Path,
    *,
    skill_short: str,
    case_id: str,
    skill_id: str,
    score_key: str,
    expected_score: float | None,
    expected_flag: str,
    tolerance: float = 0.10,
    components: dict[str, Any] | None = None,
    must_cite: tuple[str, ...] = (),
    warnings_must_include: tuple[str, ...] = (),
    confidence_range: tuple[float, float] = (0.0, 1.0),
    known_deviation_explanation: str | None = None,
) -> Path:
    """Minimal-gold-YAML writer — enough shape for the loader."""
    gold_root.mkdir(parents=True, exist_ok=True)
    sub = gold_root / skill_short
    sub.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "case_id": case_id,
        "skill_id": skill_id,
        "skill_version": "0.1.0",
        "inputs": {"cik": "9999999999", "fiscal_year_end": "2023-12-31"},
        "expected": {
            score_key: {
                "value": expected_score,
                "tolerance": tolerance,
                "source_of_truth": "live_implementation",
                "rationale": "synthetic",
            },
            "flag": {"value": expected_flag, "rationale": "synthetic"},
            "components": components or {},
            "citation_expectations": {
                "must_cite": list(must_cite),
                "must_resolve": True,
            },
            "confidence": {
                "min": confidence_range[0],
                "max": confidence_range[1],
                "rationale": "synthetic",
            },
            "warnings_must_include": list(warnings_must_include),
        },
        "known_deviation_explanation": known_deviation_explanation,
        "authored_by_persona": "evaluation_agent",
        "authored_at": "2026-04-17",
        "gold_version": "0.1.0",
    }
    path = sub / f"{case_id}.yaml"
    path.write_text(yaml.safe_dump(entry, sort_keys=False), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Tests.
# ---------------------------------------------------------------------------


def test_basic_pass_path(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="toy_pass",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-2.40,
        expected_flag="manipulator_unlikely",
        must_cite=("revenue",),
    )
    stub = _StubSkill(
        canned_output={
            "m_score": -2.38,
            "flag": "manipulator_unlikely",
            "components": {},
            "citations": [
                {
                    "doc_id": "0000320193/acc1",
                    "statement_role": "income_statement",
                    "locator": "0000320193/acc1::income_statement::revenue",
                    "excerpt_hash": "a" * 64,
                    "value": 100.0,
                    "retrieved_at": "2026-04-17T00:00:00Z",
                }
            ],
            "confidence": 0.9,
            "warnings": [],
        }
    )
    # Load the gold via the real loader.
    cases = load_gold_cases(gold_root)
    assert len(cases) == 1
    result = _evaluate_case(case=cases[0], actual=stub.run({}))
    assert result.within_tolerance is True
    assert result.flag_match is True
    assert result.must_cite_satisfied is True
    assert result.confidence_in_range is True
    assert result.explainable_failure is None


def test_null_matches_null_on_indeterminate(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="altman",
        case_id="toy_indet",
        skill_id="compute_altman_z_score",
        score_key="z_score",
        expected_score=None,
        expected_flag="indeterminate",
        confidence_range=(0.0, 0.1),
    )
    stub = _StubSkill(
        canned_output={
            "z_score": None,
            "flag": "indeterminate",
            "components": {},
            "citations": [],
            "confidence": 0.0,
            "warnings": ["X3: inputs missing (ebit)"],
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub.run({}))
    assert result.within_tolerance is True  # null-matches-null
    assert result.flag_match is True
    assert result.confidence_in_range is True


def test_null_vs_number_fails_within_tolerance(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="altman",
        case_id="toy_half",
        skill_id="compute_altman_z_score",
        score_key="z_score",
        expected_score=None,
        expected_flag="indeterminate",
    )
    stub = _StubSkill(
        canned_output={
            "z_score": 5.0,
            "flag": "safe",
            "components": {},
            "citations": [],
            "confidence": 1.0,
            "warnings": [],
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub.run({}))
    assert result.within_tolerance is False  # number-vs-null fails
    assert result.flag_match is False


def test_explainable_failure_propagates(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="toy_deviation",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-1.50,
        expected_flag="manipulator_likely",
        tolerance=0.10,
        known_deviation_explanation="MVP TATA approximation drops two terms.",
    )
    stub = _StubSkill(
        canned_output={
            "m_score": -2.63,
            "flag": "manipulator_unlikely",
            "components": {},
            "citations": [],
            "confidence": 0.0,
            "warnings": ["tata_approximation"],
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub.run({}))
    assert result.within_tolerance is False
    assert result.flag_match is False
    assert result.explainable_failure is not None
    assert "TATA approximation" in result.explainable_failure


def test_must_cite_enforcement() -> None:
    # Direct call to _must_cite_met.
    actual = [
        {"locator": "doc/acc::income_statement::revenue"},
        {"locator": "doc/acc::balance_sheet::total_assets"},
    ]
    assert _must_cite_met(
        must_cite=("revenue (period=t)", "total_assets (period=t)"),
        actual_citations=actual,
    ) is True
    assert _must_cite_met(
        must_cite=("revenue (period=t)", "retained_earnings (period=t)"),
        actual_citations=actual,
    ) is False


def test_must_cite_market_value_of_equity_normalizes() -> None:
    actual = [
        {"locator": "market_data/equity_values::market_data::market_value_of_equity_0001024401_2000-12-31"}
    ]
    assert _must_cite_met(
        must_cite=("market_value_of_equity (fixture)",),
        actual_citations=actual,
    ) is True


def test_warnings_must_include_surfaces_gap(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="toy_warn",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-2.40,
        expected_flag="manipulator_unlikely",
        warnings_must_include=("tata_approximation",),
    )
    stub_missing_warn = _StubSkill(
        canned_output={
            "m_score": -2.40,
            "flag": "manipulator_unlikely",
            "components": {},
            "citations": [],
            "confidence": 0.85,
            "warnings": [],  # missing the required warning
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub_missing_warn.run({}))
    # note-level surface, not a hard fail on within/flag.
    assert any("tata_approximation" in n for n in result.notes)


def test_confidence_out_of_range(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="toy_conf",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-2.40,
        expected_flag="manipulator_unlikely",
        confidence_range=(0.7, 1.0),
    )
    stub_low_conf = _StubSkill(
        canned_output={
            "m_score": -2.40,
            "flag": "manipulator_unlikely",
            "components": {},
            "citations": [],
            "confidence": 0.2,  # below min
            "warnings": [],
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub_low_conf.run({}))
    assert result.confidence_in_range is False
    assert result.confidence_observed == pytest.approx(0.2)


def test_error_envelope_becomes_failing_case(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="toy_err",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-2.40,
        expected_flag="manipulator_unlikely",
    )
    stub = _StubSkill(
        canned_output={
            "error": {
                "error_code": "unknown_filing",
                "error_category": "input_validation",
                "human_message": "no filing for cik",
                "retry_safe": False,
                "suggested_remediation": "check cik",
                "skill_id": "compute_beneish_m_score",
                "skill_version": "0.1.0",
            }
        }
    )
    cases = load_gold_cases(gold_root)
    result = _evaluate_case(case=cases[0], actual=stub.run({}))
    assert result.within_tolerance is False
    assert result.flag_match is False
    assert result.actual_flag == "error"


def test_metric_aggregation_basic() -> None:
    # Build 3 m-score results (2 pass, 1 fail) and 2 z-score results (both pass).
    m_pass = CaseResult(
        case_id="m1",
        skill_id="compute_beneish_m_score",
        cik="1",
        fiscal_year_end="2023-01-01",
        expected_score=-2.0,
        actual_score=-2.05,
        within_tolerance=True,
        tolerance=0.10,
        expected_flag="manipulator_unlikely",
        actual_flag="manipulator_unlikely",
        flag_match=True,
        citation_count=10,
        must_cite_satisfied=True,
        confidence_observed=0.9,
        confidence_in_range=True,
    )
    m_fail = m_pass.model_copy(
        update={
            "case_id": "m2",
            "within_tolerance": False,
            "flag_match": False,
            "actual_score": 5.0,
        }
    )
    z_pass = m_pass.model_copy(
        update={"case_id": "z1", "skill_id": "compute_altman_z_score"}
    )
    metrics = _compute_metrics(
        [m_pass, m_fail, z_pass],
        citation_resolves=(30, 30),
        cases_present=(3, 3),
    )
    assert metrics.m_score_within_0_10 == (1, 2)
    assert metrics.m_score_flag_match_rate == (1, 2)
    assert metrics.z_score_within_0_10 == (1, 1)
    assert metrics.z_score_zone_match_rate == (1, 1)
    assert metrics.citation_resolves == (30, 30)


def test_run_eval_integration_with_stubs(tmp_path: Path) -> None:
    gold_root = tmp_path / "gold"
    _write_gold(
        gold_root,
        skill_short="beneish",
        case_id="case_m",
        skill_id="compute_beneish_m_score",
        score_key="m_score",
        expected_score=-2.40,
        expected_flag="manipulator_unlikely",
    )
    _write_gold(
        gold_root,
        skill_short="altman",
        case_id="case_z",
        skill_id="compute_altman_z_score",
        score_key="z_score",
        expected_score=7.50,
        expected_flag="safe",
    )
    stub_m = _StubSkill(
        canned_output={
            "m_score": -2.40,
            "flag": "manipulator_unlikely",
            "components": {},
            "citations": [],
            "confidence": 0.85,
            "warnings": [],
        }
    )
    stub_z = _StubSkill(
        canned_output={
            "z_score": 7.55,
            "flag": "safe",
            "components": {},
            "citations": [],
            "confidence": 1.0,
            "warnings": [],
        }
    )
    reg = _StubRegistry(
        {"compute_beneish_m_score": stub_m, "compute_altman_z_score": stub_z}
    )
    report = run_eval(gold_root=gold_root, registry=reg, write_report=False)
    assert isinstance(report, EvalReport)
    assert len(report.cases) == 2
    assert report.metrics.m_score_within_0_10 == (1, 1)
    assert report.metrics.z_score_within_0_10 == (1, 1)
    assert report.metrics.m_score_flag_match_rate == (1, 1)
    assert report.metrics.z_score_zone_match_rate == (1, 1)
    # Citation check sees zero citations but 0/0 = 1.0.
    assert report.metrics.citation_resolves == (0, 0)


def test_format_console_report_contains_metric_block() -> None:
    report = EvalReport(
        run_id="abc123",
        run_at="2026-04-17T00:00:00Z",
        gold_root="/tmp/gold",
        cases=[],
        metrics={
            "m_score_within_0_10": (4, 5),
            "m_score_flag_match_rate": (4, 5),
            "z_score_within_0_10": (5, 5),
            "z_score_zone_match_rate": (5, 5),
            "citation_resolves": (100, 100),
            "gold_present_for_all_cases": (10, 10),
        },
        explainable_failures=[],
    )
    text = format_console_report(report)
    assert "m_score_within_0.10" in text
    assert "4/5" in text
    assert "100/100" in text
