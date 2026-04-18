"""Phase 5 acceptance demo.

Runs the eval harness against every gold case + the citation-integrity
check, and prints the composite gate-line for the Phase 5 handoff.
Exits 0 iff all §4.2 gates pass; non-zero otherwise.

Usage
-----
    ./.venv/bin/python -m mvp.scripts.phase5_demo
"""

from __future__ import annotations

import sys

from mvp.eval.citation_check import (
    check_citations,
    format_console_report as format_citation_report,
)
from mvp.eval.runner import format_console_report as format_eval_report, run_eval


def main() -> int:
    report = run_eval(write_report=True)
    sys.stdout.write(format_eval_report(report))
    sys.stdout.write("\n")

    citation_report = check_citations(case_results=report.cases)
    sys.stdout.write(format_citation_report(citation_report))
    sys.stdout.write("\n")

    m = report.metrics
    gate_line = (
        f"PHASE 5 ACCEPTANCE: "
        f"M within_0.10 = {m.m_score_within_0_10[0]}/{m.m_score_within_0_10[1]} | "
        f"M flag_match = {m.m_score_flag_match_rate[0]}/{m.m_score_flag_match_rate[1]} | "
        f"Z within_0.10 = {m.z_score_within_0_10[0]}/{m.z_score_within_0_10[1]} | "
        f"Z zone_match = {m.z_score_zone_match_rate[0]}/{m.z_score_zone_match_rate[1]} | "
        f"citations_resolved = {citation_report.resolved}/{citation_report.total_citations}"
    )
    sys.stdout.write(gate_line + "\n")

    gate_pass = (
        m.m_score_within_0_10[0] >= 4
        and m.m_score_flag_match_rate[0] >= 4
        and m.z_score_within_0_10[0] >= 4
        and m.z_score_zone_match_rate[0] >= 4
        and citation_report.resolution_rate == 1.0
        and m.gold_present_for_all_cases[0] == m.gold_present_for_all_cases[1]
    )
    return 0 if gate_pass else 1


if __name__ == "__main__":
    sys.exit(main())
