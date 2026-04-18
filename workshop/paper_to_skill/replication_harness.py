"""workshop.paper_to_skill.replication_harness — run a skill's
manifest ``examples[]`` through the shipped skill and produce a
±tolerance pass/fail report.

First-draft version written during Paper 4 onboarding (de Kok 2024
GLLM non-answer filter). Papers 1-3 each hand-wrote per-skill
paper-replication tests; by Paper 4, five L3 skills were shipped,
each with an ``examples[]`` block in the manifest that enumerated
the MVP-sample expected inputs. The harness lets those declarative
blocks drive a uniform live-run report without re-authoring per-skill
imperative pytest code each iteration.

What this script does
---------------------
1. Loads a shipped skill's ``manifest.yaml`` via
   ``SkillManifest.load_from_yaml``.
2. For each ``example`` in ``manifest.examples``:

   - Runs the skill through the registry
     (``default_registry().get(skill_id).run(example.input)``).
   - Compares the returned value/flag against optional tolerance
     blocks on the example (``expected_flag``,
     ``expected_score_range``, ``expected_score_tolerance``).
   - Records pass/fail + diagnostic trace.

3. Prints a per-skill report line (PASS / FAIL / count) and exits
   non-zero if any example fails.

What this script does NOT do
----------------------------
- Replace per-skill paper-replication tests. Those still exist under
  ``mvp/tests/integration/`` — they exercise arithmetic boundaries,
  degenerate inputs, and regression-specific pins (e.g. the Altman X5
  coefficient = 0.999). The harness is for the live-run sample-firm
  sanity check, not the full replication gate.
- Fetch/ingest/download anything. The MVP corpus must already be on
  disk (``data/filings/`` populated) — the harness runs the shipped
  skill exactly as the CLI / API would.
- Interpret the ``example.notes`` free-text field. Those are for human
  readers; the harness's pass/fail logic is driven by the typed
  expectation fields only.

The harness's expectation shape is a conservative superset of what the
current Papers 1-4 manifests ship. Each ``example`` may optionally set:

- ``expected_flag`` — exact string match on the skill's ``flag`` output.
- ``expected_score_range`` — 2-item [min, max], inclusive, matched
  against the skill's primary score output (resolved via the same
  ``_SCORE_KEYS`` table as ``mvp/eval/gold_loader.py``).
- ``expected_score_tolerance`` — alternate to range: {"value": X,
  "tolerance": Y} matches when skill_score is within ±Y of X.

If an example sets NEITHER ``expected_flag`` nor a score expectation,
the harness only checks that the skill returned a non-error envelope
(loose liveness check). This is useful for new skills whose expected
values aren't yet calibrated.

Papers 1-3 manifests predate this harness and don't include typed
expectations in their ``examples[]`` blocks — they're string-only
``notes`` fields. Running the harness against them produces a loose
PASS (liveness-only) for each example. That is the designed behaviour:
a back-fill to add typed expectations to Papers 1-3's manifests is
filed as a follow-up in ``workshop/maintenance/README.md``.

Usage
-----
As a library::

    from workshop.paper_to_skill.replication_harness import run_harness
    from pathlib import Path

    report = run_harness(
        manifest_path=Path("mvp/skills/paper_derived/compute_nonanswer_hedging_density/manifest.yaml"),
    )
    print(report.summary_line())

As a CLI::

    python -m workshop.paper_to_skill.replication_harness \\
        --manifest mvp/skills/paper_derived/compute_nonanswer_hedging_density/manifest.yaml
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# Score key table — mirrors mvp/eval/gold_loader.py's _SCORE_KEYS.
# If this drifts, the harness will still work (falls back to "score");
# the alignment is just for a clean log line.
_SCORE_KEYS: dict[str, str] = {
    "compute_beneish_m_score": "m_score",
    "compute_altman_z_score": "z_score",
    "compute_mdna_upfrontedness": "upfrontedness_score",
    "compute_context_importance_signals": "context_importance_score",
    "compute_business_complexity_signals": "business_complexity_score",
    "compute_nonanswer_hedging_density": "hedging_density",
    "predict_filing_complexity_from_determinants": "predicted_complexity_level",
}


@dataclass(frozen=True)
class ExampleResult:
    """Result of running one manifest ``example`` through the skill."""

    example_name: str
    passed: bool
    reason: str
    actual_score: float | None = None
    actual_flag: str | None = None
    expected_flag: str | None = None
    expected_score: str | None = None  # pretty-printed band or value


@dataclass(frozen=True)
class HarnessReport:
    """Report of running a skill's full examples[] block."""

    skill_id: str
    total: int
    passed: int
    failed: int
    results: tuple[ExampleResult, ...] = field(default_factory=tuple)

    @property
    def all_passed(self) -> bool:
        return self.failed == 0 and self.total > 0

    def summary_line(self) -> str:
        """One-line PASS/FAIL summary suitable for a CLI."""
        gate = "PASS" if self.all_passed else "FAIL"
        return (
            f"[{gate}] {self.skill_id}: {self.passed}/{self.total} examples "
            f"passed"
        )

    def per_example_lines(self) -> list[str]:
        """Per-example lines for a detailed log."""
        lines: list[str] = []
        for r in self.results:
            marker = "ok" if r.passed else "FAIL"
            line = f"  [{marker}] {r.example_name}: {r.reason}"
            lines.append(line)
        return lines


def run_harness(manifest_path: Path) -> HarnessReport:
    """Run every example in a skill's manifest through the shipped
    skill and produce a HarnessReport.

    Imports the skill schema + registry lazily so the module is safe to
    import without the ``mvp`` package present (e.g. in a pure-workshop
    environment). When ``mvp`` IS on the path, the harness runs the
    shipped skill via the registry.
    """
    # Late-imported to keep this module import-safe.
    from mvp.skills.manifest_schema import SkillManifest
    from mvp.skills.registry import default_registry

    manifest = SkillManifest.load_from_yaml(manifest_path)
    skill_id = manifest.skill_id
    score_key = _SCORE_KEYS.get(skill_id, "score")

    skill = default_registry().get(skill_id)

    results: list[ExampleResult] = []
    for ex in manifest.examples:
        inputs = ex.input
        expected_flag = ex.expected_flag

        # Pull tolerance blocks if present. The schema doesn't require
        # them; manifests predating the harness won't have them.
        raw = getattr(ex, "__dict__", {})
        expected_score_range = raw.get("expected_score_range")
        expected_score_tolerance = raw.get("expected_score_tolerance")

        try:
            output = skill.run(inputs)
        except Exception as exc:  # noqa: BLE001 - we WANT the catch-all
            results.append(
                ExampleResult(
                    example_name=ex.name,
                    passed=False,
                    reason=f"skill raised: {type(exc).__name__}: {exc}",
                    expected_flag=expected_flag,
                )
            )
            continue

        if "error" in output:
            err = output["error"]
            results.append(
                ExampleResult(
                    example_name=ex.name,
                    passed=False,
                    reason=(
                        f"skill returned error envelope: "
                        f"{err.get('error_code')}: "
                        f"{err.get('human_message', '')[:120]}"
                    ),
                    expected_flag=expected_flag,
                )
            )
            continue

        actual_score = output.get(score_key)
        actual_flag = output.get("flag")

        passed, reason = _check_expectations(
            actual_score=actual_score,
            actual_flag=actual_flag,
            expected_flag=expected_flag,
            expected_score_range=expected_score_range,
            expected_score_tolerance=expected_score_tolerance,
        )

        expected_score_pretty = _format_expected_score(
            expected_score_range, expected_score_tolerance
        )
        results.append(
            ExampleResult(
                example_name=ex.name,
                passed=passed,
                reason=reason,
                actual_score=(
                    float(actual_score) if actual_score is not None else None
                ),
                actual_flag=actual_flag,
                expected_flag=expected_flag,
                expected_score=expected_score_pretty,
            )
        )

    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count
    return HarnessReport(
        skill_id=skill_id,
        total=len(results),
        passed=passed_count,
        failed=failed_count,
        results=tuple(results),
    )


def _check_expectations(
    *,
    actual_score: float | None,
    actual_flag: str | None,
    expected_flag: str | None,
    expected_score_range: list[float] | None,
    expected_score_tolerance: dict[str, float] | None,
) -> tuple[bool, str]:
    """Return (passed, reason) for one example's expectations."""
    failures: list[str] = []

    if expected_flag is not None:
        if actual_flag != expected_flag:
            failures.append(
                f"flag {actual_flag!r} != expected {expected_flag!r}"
            )

    if expected_score_range is not None:
        lo, hi = float(expected_score_range[0]), float(expected_score_range[1])
        if actual_score is None:
            failures.append(
                f"score is null but expected [{lo}, {hi}]"
            )
        elif not (lo <= actual_score <= hi):
            failures.append(
                f"score {actual_score} outside [{lo}, {hi}]"
            )

    if expected_score_tolerance is not None:
        want = float(expected_score_tolerance["value"])
        tol = float(expected_score_tolerance["tolerance"])
        if actual_score is None:
            failures.append(
                f"score is null but expected {want} ± {tol}"
            )
        elif abs(actual_score - want) > tol:
            failures.append(
                f"score {actual_score} outside {want} ± {tol}"
            )

    if failures:
        return False, "; ".join(failures)

    # No expectation fields → loose liveness pass.
    if (
        expected_flag is None
        and expected_score_range is None
        and expected_score_tolerance is None
    ):
        return True, (
            f"liveness (no typed expectations on this example; "
            f"actual flag={actual_flag}, score={actual_score})"
        )
    return True, (
        f"all expectations met (flag={actual_flag}, score={actual_score})"
    )


def _format_expected_score(
    range_: list[float] | None,
    tol: dict[str, float] | None,
) -> str | None:
    """Pretty-print an expected-score expectation for a log line."""
    if range_ is not None:
        return f"[{range_[0]}, {range_[1]}]"
    if tol is not None:
        return f"{tol.get('value')} ± {tol.get('tolerance')}"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="workshop.paper_to_skill.replication_harness",
        description=(
            "Run a shipped skill's manifest examples[] block through the "
            "registry and report pass/fail per example."
        ),
    )
    parser.add_argument(
        "--manifest",
        required=True,
        type=Path,
        help="Path to the skill's manifest.yaml.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-example lines in addition to the summary.",
    )
    args = parser.parse_args(argv)

    report = run_harness(args.manifest)
    print(report.summary_line())
    if args.verbose or not report.all_passed:
        for line in report.per_example_lines():
            print(line)

    return 0 if report.all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
