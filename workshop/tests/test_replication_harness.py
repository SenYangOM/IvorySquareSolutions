"""Unit tests for workshop/paper_to_skill/replication_harness.py.

First-version tests authored during Paper 4 onboarding. The harness's
expectation-checking logic is pure functions; those get unit-tested
directly against synthetic inputs. The full-run path against a real
shipped skill is exercised by a regression-style test that uses the
Paper 4 skill's own manifest.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workshop.paper_to_skill.replication_harness import (
    ExampleResult,
    HarnessReport,
    _check_expectations,
    _format_expected_score,
    run_harness,
)


# ---------------------------------------------------------------------------
# _check_expectations — pure-function tests.
# ---------------------------------------------------------------------------


def test_all_none_expectations_yields_liveness_pass() -> None:
    passed, reason = _check_expectations(
        actual_score=0.5,
        actual_flag="typical_hedging",
        expected_flag=None,
        expected_score_range=None,
        expected_score_tolerance=None,
    )
    assert passed is True
    assert "liveness" in reason


def test_flag_exact_match_passes() -> None:
    passed, reason = _check_expectations(
        actual_score=0.5,
        actual_flag="typical_hedging",
        expected_flag="typical_hedging",
        expected_score_range=None,
        expected_score_tolerance=None,
    )
    assert passed is True
    assert "expectations met" in reason


def test_flag_mismatch_fails() -> None:
    passed, reason = _check_expectations(
        actual_score=0.5,
        actual_flag="high_hedging",
        expected_flag="typical_hedging",
        expected_score_range=None,
        expected_score_tolerance=None,
    )
    assert passed is False
    assert "flag" in reason
    assert "typical_hedging" in reason
    assert "high_hedging" in reason


def test_score_range_inclusive_pass() -> None:
    # Boundaries are inclusive — 0.15 in [0.15, 0.35] passes.
    for actual in (0.15, 0.25, 0.35):
        passed, _ = _check_expectations(
            actual_score=actual,
            actual_flag=None,
            expected_flag=None,
            expected_score_range=[0.15, 0.35],
            expected_score_tolerance=None,
        )
        assert passed, f"score {actual} should pass range [0.15, 0.35]"


def test_score_outside_range_fails() -> None:
    passed, reason = _check_expectations(
        actual_score=0.50,
        actual_flag=None,
        expected_flag=None,
        expected_score_range=[0.15, 0.35],
        expected_score_tolerance=None,
    )
    assert passed is False
    assert "outside" in reason


def test_null_score_with_range_fails() -> None:
    passed, reason = _check_expectations(
        actual_score=None,
        actual_flag=None,
        expected_flag=None,
        expected_score_range=[0.15, 0.35],
        expected_score_tolerance=None,
    )
    assert passed is False
    assert "null" in reason


def test_score_tolerance_within_passes() -> None:
    passed, _ = _check_expectations(
        actual_score=0.50,
        actual_flag=None,
        expected_flag=None,
        expected_score_range=None,
        expected_score_tolerance={"value": 0.52, "tolerance": 0.05},
    )
    assert passed is True


def test_score_tolerance_outside_fails() -> None:
    passed, reason = _check_expectations(
        actual_score=0.70,
        actual_flag=None,
        expected_flag=None,
        expected_score_range=None,
        expected_score_tolerance={"value": 0.52, "tolerance": 0.05},
    )
    assert passed is False
    assert "outside" in reason


def test_flag_and_score_both_must_pass() -> None:
    # Flag right, score wrong -> fail.
    passed, reason = _check_expectations(
        actual_score=0.50,
        actual_flag="typical_hedging",
        expected_flag="typical_hedging",
        expected_score_range=[0.15, 0.35],
        expected_score_tolerance=None,
    )
    assert passed is False
    assert "0.5" in reason

    # Score right, flag wrong -> fail.
    passed, reason = _check_expectations(
        actual_score=0.20,
        actual_flag="high_hedging",
        expected_flag="typical_hedging",
        expected_score_range=[0.15, 0.35],
        expected_score_tolerance=None,
    )
    assert passed is False
    assert "flag" in reason


# ---------------------------------------------------------------------------
# _format_expected_score — helper.
# ---------------------------------------------------------------------------


def test_format_expected_score_range() -> None:
    assert _format_expected_score([0.15, 0.35], None) == "[0.15, 0.35]"


def test_format_expected_score_tolerance() -> None:
    assert (
        _format_expected_score(None, {"value": 0.5, "tolerance": 0.05})
        == "0.5 ± 0.05"
    )


def test_format_expected_score_none() -> None:
    assert _format_expected_score(None, None) is None


# ---------------------------------------------------------------------------
# HarnessReport — summary line formatting.
# ---------------------------------------------------------------------------


def test_harness_report_summary_line_pass() -> None:
    report = HarnessReport(
        skill_id="compute_foo",
        total=3,
        passed=3,
        failed=0,
        results=(),
    )
    line = report.summary_line()
    assert "[PASS]" in line
    assert "compute_foo" in line
    assert "3/3" in line


def test_harness_report_summary_line_fail() -> None:
    report = HarnessReport(
        skill_id="compute_foo",
        total=3,
        passed=2,
        failed=1,
        results=(),
    )
    line = report.summary_line()
    assert "[FAIL]" in line
    assert "2/3" in line


def test_harness_report_all_passed_requires_nonempty() -> None:
    """An empty report is NOT all-passed (avoids a silent 0/0 success
    hiding a misconfigured call)."""
    report = HarnessReport(
        skill_id="compute_foo", total=0, passed=0, failed=0, results=()
    )
    assert report.all_passed is False


# ---------------------------------------------------------------------------
# Full-run regression test against the Paper 4 skill manifest.
# ---------------------------------------------------------------------------


_PAPER_4_MANIFEST = (
    "/mnt/nvme2/iv/research/Proj_ongoing/mvp/skills/paper_derived/"
    "compute_nonanswer_hedging_density/manifest.yaml"
)


@pytest.mark.skipif(
    not Path(_PAPER_4_MANIFEST).exists(),
    reason="Paper-4 manifest not found at expected path",
)
def test_run_harness_against_paper_4_manifest_passes() -> None:
    """Regression test: run the harness against Paper 4's shipped
    manifest. All 3 examples should pass (as liveness checks, since
    the Paper-4 examples don't yet have typed expectation fields).
    Skips when the data/filings/ corpus is absent — the same
    convention mvp/tests/conftest.py uses for requires_live_data.
    """
    if not Path("/mnt/nvme2/iv/research/Proj_ongoing/mvp/data/filings/0000320193").exists():
        pytest.skip("MVP live-data corpus not present")

    report = run_harness(Path(_PAPER_4_MANIFEST))
    assert report.skill_id == "compute_nonanswer_hedging_density"
    assert report.total == 3
    assert report.all_passed, f"not all passed: {report.per_example_lines()}"
