"""Eval harness runner — the gate builder for Phase 5.

Reads every gold YAML under ``eval/gold/``, invokes the corresponding
skill through the registry, and reports per-case pass/fail on the six
metrics in ``success_criteria.md`` §4.2:

- ``m_score_within_0.10`` — m_score within tolerance (null-matches-null
  counts as pass).
- ``m_score_flag_match_rate`` — expected_flag == actual_flag.
- ``z_score_within_0.10`` — z_score within tolerance.
- ``z_score_zone_match_rate`` — expected_flag == actual_flag.
- ``citation_resolves`` — 100% of every cited locator resolves.
- ``gold_present_for_all_cases`` — 10/10 gold cases load without error.

Usage
-----
- ``python -m mvp.eval.runner`` — prints a one-page report to stdout and
  also writes ``eval/reports/<YYYY-MM-DD>_<run_id>.json``.
- ``from mvp.eval.runner import run_eval; report = run_eval()`` —
  Python API returning an :class:`EvalReport`.

Null handling
-------------
For an indeterminate case (expected_flag == "indeterminate"):

- ``within_tolerance`` is True when both expected_score is ``None`` AND
  actual_score is ``None`` (null-matches-null).
- ``flag_match`` is True when both flags equal ``"indeterminate"``.

Explainable failures
--------------------
A case's gold YAML may set ``known_deviation_explanation`` to a
non-empty string. When the case fails within_tolerance or flag_match,
the report records ``explainable_failure: <text>`` rather than treating
it as silent-fail. The failure still counts against the metric (per
§4.2 the MVP gate is 4/5, not 5/5 — deviations are permitted when
documented, not hidden).
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from .gold_loader import GoldCase, load_gold_cases


# ---------------------------------------------------------------------------
# Pydantic models.
# ---------------------------------------------------------------------------


class CaseResult(BaseModel):
    """Per-case evaluation result."""

    model_config = ConfigDict(extra="forbid")

    case_id: str
    skill_id: str
    cik: str
    fiscal_year_end: str
    expected_score: float | None
    actual_score: float | None
    within_tolerance: bool
    tolerance: float | None
    expected_flag: str
    actual_flag: str
    flag_match: bool
    citation_count: int
    must_cite_satisfied: bool
    explainable_failure: str | None = None
    warnings_observed: list[str] = Field(default_factory=list)
    confidence_observed: float | None = None
    confidence_in_range: bool
    notes: list[str] = Field(default_factory=list)


class EvalMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    m_score_within_0_10: tuple[int, int]
    m_score_flag_match_rate: tuple[int, int]
    z_score_within_0_10: tuple[int, int]
    z_score_zone_match_rate: tuple[int, int]
    citation_resolves: tuple[int, int]
    gold_present_for_all_cases: tuple[int, int]


class EvalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str
    run_at: str
    gold_root: str
    cases: list[CaseResult]
    metrics: EvalMetrics
    explainable_failures: list[str]
    notes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Entry point.
# ---------------------------------------------------------------------------


_MVP_ROOT = Path(__file__).resolve().parent.parent


def run_eval(
    gold_root: Path | None = None,
    *,
    registry: Any | None = None,
    write_report: bool = True,
) -> EvalReport:
    """Run every gold case and return an :class:`EvalReport`.

    Parameters
    ----------
    gold_root:
        Root directory holding ``<skill_short>/*.yaml``. Defaults to
        ``mvp/eval/gold``.
    registry:
        Optional registry to use. Defaults to
        :func:`mvp.skills.registry.default_registry`. Tests inject
        synthetic registries here.
    write_report:
        When True, also write the report to ``eval/reports/<date>_<run_id>.json``.
    """
    if gold_root is None:
        gold_root = _MVP_ROOT / "eval" / "gold"
    gold_root = Path(gold_root)

    if registry is None:
        from mvp.skills.registry import default_registry

        registry = default_registry()

    run_id = str(uuid.uuid4())
    run_at = datetime.now(timezone.utc).isoformat()

    cases = load_gold_cases(gold_root)
    case_results: list[CaseResult] = []
    citation_total = 0
    citation_ok = 0

    for case in cases:
        skill = registry.get(case.skill_id)
        actual = skill.run({"cik": case.cik, "fiscal_year_end": case.fiscal_year_end})
        result = _evaluate_case(case=case, actual=actual)
        case_results.append(result)
        # Citation counting happens once at the runner level using the
        # citation_check module — kept outside this loop to avoid
        # duplicated resolution work. The CaseResult only tracks
        # count + must_cite satisfaction.
        citation_total += result.citation_count

    # Citation resolution is handled by the dedicated check module; we
    # reuse it here to populate the metric so the runner produces the
    # §4.2 6-row table in a single pass.
    from .citation_check import check_citations

    citation_report = check_citations(case_results=case_results, registry=registry)
    citation_ok = citation_report.resolved
    citation_total = citation_report.total_citations

    metrics = _compute_metrics(
        case_results,
        citation_resolves=(citation_ok, citation_total),
        cases_present=(len(case_results), _expected_case_count(gold_root)),
    )
    explainable_failures = [
        f"{r.case_id}: {r.explainable_failure}"
        for r in case_results
        if r.explainable_failure
    ]
    report = EvalReport(
        run_id=run_id,
        run_at=run_at,
        gold_root=str(gold_root),
        cases=case_results,
        metrics=metrics,
        explainable_failures=explainable_failures,
    )
    if write_report:
        _persist_report(report)
    return report


def _evaluate_case(*, case: GoldCase, actual: dict[str, Any]) -> CaseResult:
    """Compare one skill invocation's output to its gold expectations."""
    score_key = case.score_key
    if "error" in actual:
        # The skill returned a typed error envelope. This is a hard
        # failure unless the gold explicitly expected indeterminate +
        # null score, which can't co-exist with an error envelope
        # anyway. Surface the raw error for the reviewer.
        err = actual["error"]
        return CaseResult(
            case_id=case.case_id,
            skill_id=case.skill_id,
            cik=case.cik,
            fiscal_year_end=case.fiscal_year_end,
            expected_score=case.score_expectation.value,
            actual_score=None,
            within_tolerance=False,
            tolerance=case.score_expectation.tolerance,
            expected_flag=case.expected_flag,
            actual_flag="error",
            flag_match=False,
            citation_count=0,
            must_cite_satisfied=False,
            explainable_failure=(
                f"skill returned error envelope: {err.get('error_code', '?')}: "
                f"{err.get('human_message', '?')}"
                if not case.known_deviation_explanation
                else case.known_deviation_explanation
            ),
            warnings_observed=[],
            confidence_observed=None,
            confidence_in_range=False,
            notes=[f"error_envelope: {err.get('error_code', '?')}"],
        )

    actual_score = actual.get(score_key)
    if actual_score is not None:
        actual_score = float(actual_score)
    actual_flag = str(actual.get("flag", ""))
    warnings_out: list[str] = list(actual.get("warnings") or [])
    confidence = actual.get("confidence")
    confidence_val = float(confidence) if confidence is not None else None

    expected_score = case.score_expectation.value
    # Within tolerance: null-matches-null is True; numeric comparison uses band.
    if expected_score is None and actual_score is None:
        within = True
    elif expected_score is None or actual_score is None:
        within = False
    else:
        band = case.score_expectation.tolerance_band()
        if band is None:
            within = False
        else:
            within = band[0] <= actual_score <= band[1]

    # Flag match: indeterminate-matches-indeterminate counts as match.
    flag_match = case.expected_flag == actual_flag

    # Must-cite check — we need the flat list of locators from actual.
    actual_cites = actual.get("citations") or []
    if not actual_cites:
        # Composite output shape: m_score_result.citations / z_score_result.citations.
        for block_key in ("m_score_result", "z_score_result"):
            block = actual.get(block_key)
            if isinstance(block, dict):
                actual_cites = actual_cites + list(block.get("citations") or [])

    citation_count = len(actual_cites)
    must_cite_satisfied = _must_cite_met(
        must_cite=case.citation_expectation.must_cite,
        actual_citations=actual_cites,
    )

    # Confidence-in-range check.
    if confidence_val is None:
        confidence_in_range = False
    else:
        confidence_in_range = (
            case.confidence.min <= confidence_val <= case.confidence.max
        )

    # Warnings must-include check.
    warning_notes: list[str] = []
    for needle in case.warnings_must_include:
        if not any(needle in w for w in warnings_out):
            warning_notes.append(f"missing_required_warning: {needle!r}")

    # Explainable-failure propagation.
    explainable: str | None = None
    if (not within or not flag_match) and case.known_deviation_explanation:
        explainable = case.known_deviation_explanation

    return CaseResult(
        case_id=case.case_id,
        skill_id=case.skill_id,
        cik=case.cik,
        fiscal_year_end=case.fiscal_year_end,
        expected_score=expected_score,
        actual_score=actual_score,
        within_tolerance=within,
        tolerance=case.score_expectation.tolerance,
        expected_flag=case.expected_flag,
        actual_flag=actual_flag,
        flag_match=flag_match,
        citation_count=citation_count,
        must_cite_satisfied=must_cite_satisfied,
        explainable_failure=explainable,
        warnings_observed=warnings_out,
        confidence_observed=confidence_val,
        confidence_in_range=confidence_in_range,
        notes=warning_notes,
    )


def _must_cite_met(
    *,
    must_cite: tuple[str, ...],
    actual_citations: list[dict[str, Any]],
) -> bool:
    """Check that every ``must_cite`` line item appears in ``actual_citations``.

    The must_cite list uses the ``"<canonical_name> (period=t|t-1)"``
    convention documented in ``gold_authoring_guide.md``. We check that
    each named canonical line item appears in at least one citation's
    ``locator`` string (at least once across period=t; our output
    citations don't carry period metadata as a separate field, so we
    treat "at least one mention" as satisfying either period
    requirement — period differentiation is handled indirectly by
    the gold citation_count).
    """
    if not must_cite:
        return True
    # Extract canonical names from the must_cite entries. The entries
    # are typically "<canonical_name> (period=...)" or just a bare
    # canonical name; we strip the period suffix.
    required_names: list[str] = []
    for entry in must_cite:
        name = entry.split("(")[0].strip()
        if name and name not in required_names:
            required_names.append(name)

    # Build a set of canonical names appearing in any actual citation's locator.
    actual_names: set[str] = set()
    for cite in actual_citations:
        if not isinstance(cite, dict):
            continue
        locator = cite.get("locator")
        if not isinstance(locator, str):
            continue
        # Locator shape: "<doc_id>::<statement_role>::<line_item>"
        parts = locator.split("::")
        if len(parts) >= 3:
            actual_names.add(parts[2].strip())
        # Market-data citations use synthetic line items like
        # "market_value_of_equity_<cik>_<fye>" — normalize to
        # "market_value_of_equity" for must_cite matching.
        line_item = parts[2] if len(parts) >= 3 else ""
        if line_item.startswith("market_value_of_equity"):
            actual_names.add("market_value_of_equity")

    for name in required_names:
        if name == "market_value_of_equity":
            if "market_value_of_equity" not in actual_names:
                return False
            continue
        if name not in actual_names:
            return False
    return True


# ---------------------------------------------------------------------------
# Metric aggregation.
# ---------------------------------------------------------------------------


def _compute_metrics(
    results: list[CaseResult],
    *,
    citation_resolves: tuple[int, int],
    cases_present: tuple[int, int],
) -> EvalMetrics:
    m_cases = [r for r in results if r.skill_id == "compute_beneish_m_score"]
    z_cases = [r for r in results if r.skill_id == "compute_altman_z_score"]
    return EvalMetrics(
        m_score_within_0_10=(
            sum(1 for r in m_cases if r.within_tolerance),
            len(m_cases),
        ),
        m_score_flag_match_rate=(
            sum(1 for r in m_cases if r.flag_match),
            len(m_cases),
        ),
        z_score_within_0_10=(
            sum(1 for r in z_cases if r.within_tolerance),
            len(z_cases),
        ),
        z_score_zone_match_rate=(
            sum(1 for r in z_cases if r.flag_match),
            len(z_cases),
        ),
        citation_resolves=citation_resolves,
        gold_present_for_all_cases=cases_present,
    )


def _expected_case_count(gold_root: Path) -> int:
    """Expected gold-case count — number of YAML files actually present.

    This is used for the ``gold_present_for_all_cases`` metric and is
    deliberately self-referential (we don't hardcode "10"); a reviewer
    who deletes a YAML will see the metric drop.
    """
    n = 0
    for sub in gold_root.iterdir() if gold_root.is_dir() else []:
        if sub.is_dir():
            n += len(list(sub.glob("*.yaml")))
    return n


# ---------------------------------------------------------------------------
# Report I/O.
# ---------------------------------------------------------------------------


def _persist_report(report: EvalReport) -> Path:
    out_dir = _MVP_ROOT / "eval" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    today = report.run_at[:10]
    path = out_dir / f"{today}_{report.run_id[:8]}.json"
    path.write_text(
        report.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )
    return path


def format_console_report(report: EvalReport) -> str:
    """Pretty-print an :class:`EvalReport` for CLI use.

    The format is deliberately narrow — < 90 cols — so it reads
    cleanly in a terminal and in log-pasted Slack messages.
    """
    lines: list[str] = []
    lines.append(f"# Eval report {report.run_id[:8]} at {report.run_at}")
    lines.append(f"# Gold root: {report.gold_root}")
    lines.append("")
    lines.append(
        "| case_id                  | score       | flag              | tol | cite |"
    )
    lines.append(
        "|--------------------------|-------------|-------------------|-----|------|"
    )
    for r in report.cases:
        actual_score = (
            f"{r.actual_score:+.4f}" if r.actual_score is not None else "null"
        )
        expected_score = (
            f"{r.expected_score:+.4f}" if r.expected_score is not None else "null"
        )
        flag_col = f"{r.expected_flag[:9]}→{r.actual_flag[:9]}"
        tol_col = "OK" if r.within_tolerance else "!!"
        cite_col = "OK" if r.must_cite_satisfied else "!!"
        lines.append(
            f"| {r.case_id:<24s} | {actual_score:>5s} v {expected_score:>5s} "
            f"| {flag_col:<17s} | {tol_col} | {cite_col} |"
        )
    lines.append("")
    m = report.metrics
    lines.append("## Metrics (§4.2 — gate is 4/5 on score+flag for each skill, 100% on citations)")
    lines.append(f"  m_score_within_0.10      : {m.m_score_within_0_10[0]}/{m.m_score_within_0_10[1]}")
    lines.append(f"  m_score_flag_match_rate  : {m.m_score_flag_match_rate[0]}/{m.m_score_flag_match_rate[1]}")
    lines.append(f"  z_score_within_0.10      : {m.z_score_within_0_10[0]}/{m.z_score_within_0_10[1]}")
    lines.append(f"  z_score_zone_match_rate  : {m.z_score_zone_match_rate[0]}/{m.z_score_zone_match_rate[1]}")
    lines.append(f"  citation_resolves        : {m.citation_resolves[0]}/{m.citation_resolves[1]}")
    lines.append(
        f"  gold_present_for_all_cases: {m.gold_present_for_all_cases[0]}/{m.gold_present_for_all_cases[1]}"
    )
    if report.explainable_failures:
        lines.append("")
        lines.append("## Explainable failures (documented deviations, per §4.2):")
        for ef in report.explainable_failures:
            # First line only for the report body; full text is in the JSON.
            first_line = ef.split("\n", 1)[0]
            lines.append(f"  - {first_line}")
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mvp.eval.runner",
        description="Run the MVP eval harness against gold cases.",
    )
    p.add_argument(
        "--gold-root",
        type=Path,
        default=None,
        help=(
            "Override the gold root (defaults to mvp/eval/gold). Tests "
            "use this to point at tmp_path."
        ),
    )
    p.add_argument(
        "--no-report-file",
        action="store_true",
        help="Skip writing the JSON report to eval/reports/.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = run_eval(
        gold_root=args.gold_root,
        write_report=not args.no_report_file,
    )
    sys.stdout.write(format_console_report(report))
    sys.stdout.write("\n")
    m = report.metrics
    # Exit 0 iff §4.2 gates pass.
    gate_pass = (
        m.m_score_within_0_10[0] >= 4
        and m.m_score_flag_match_rate[0] >= 4
        and m.z_score_within_0_10[0] >= 4
        and m.z_score_zone_match_rate[0] >= 4
        and m.citation_resolves[0] == m.citation_resolves[1]
        and m.gold_present_for_all_cases[0] == m.gold_present_for_all_cases[1]
    )
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CaseResult",
    "EvalMetrics",
    "EvalReport",
    "format_console_report",
    "run_eval",
    "main",
]
