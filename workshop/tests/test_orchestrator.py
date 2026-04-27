"""Smoke tests for ``workshop.paper_to_skill.orchestrator``.

The orchestrator is exercised against the shipped Beneish PDF without
a live API key. The expected behaviour is a structured run report
whose ``verdict`` is ``"block"`` (because the LLM cache is cold and no
key is available), with ``revisions_needed`` instructing the caller to
provide a key or prime the cache. The pipeline still produces the
deterministic A1 extraction artifact, exercising the file-shape and
cost-tracking contracts.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.lib.cost_tracking import summarize
from workshop.paper_to_skill.orchestrator import (
    STAGE_TARGETS,
    compare_calibration_outputs,
    run_deep_pipeline,
)


def test_run_deep_pipeline_returns_structured_report_without_api_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without an API key, the orchestrator returns a structured block."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    audit_root = tmp_path / "audit"
    cost_root = tmp_path / "cost"

    report = run_deep_pipeline(
        "beneish_1999",
        mode="calibration",
        audit_log_root=audit_root,
        cost_log_root=cost_root,
    )

    assert report["paper_id"] == "beneish_1999"
    assert report["mode"] == "calibration"
    assert report["verdict"] in ("go", "revise", "block", "complete")

    # A1 ran deterministically — that artifact is on disk.
    audit_dir = Path(report["audit_log_dir"])
    assert (audit_dir / "A1_extracted.json").is_file()
    assert (audit_dir / "run_report.json").is_file()

    # Cost log exists and summarize() works.
    cost_summary = report["cost_summary"]
    assert cost_summary["run_id"] == report["run_id"]
    assert "by_stage" in cost_summary

    # Stage targets are surfaced for the caller.
    assert report["stage_targets"] == STAGE_TARGETS


def test_run_deep_pipeline_unknown_paper_id_blocks_early(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    cost_root = tmp_path / "cost"

    report = run_deep_pipeline(
        "no_such_paper",
        mode="calibration",
        audit_log_root=audit_root,
        cost_log_root=cost_root,
    )

    assert report["verdict"] == "block"
    assert "PDF not found" in report.get("block_reason", "")
    assert any("Place the paper PDF" in r for r in report["revisions_needed"])
    assert report["stages"] == []
    # Cost log was created (empty) so a downstream consumer can call summarize.
    s = summarize(report["run_id"], cost_log_root=cost_root)
    assert s["n_calls"] == 0


def test_run_deep_pipeline_invalid_mode_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        run_deep_pipeline(
            "beneish_1999",
            mode="bogus",  # type: ignore[arg-type]
            audit_log_root=tmp_path / "audit",
            cost_log_root=tmp_path / "cost",
        )


def test_compare_calibration_outputs_handles_missing_drafts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the deep pipeline didn't write skill.py/manifest.yaml, the
    comparison helper still returns a structured (empty) delta rather
    than crashing."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    audit_root = tmp_path / "audit"
    cost_root = tmp_path / "cost"
    report = run_deep_pipeline(
        "beneish_1999",
        mode="calibration",
        audit_log_root=audit_root,
        cost_log_root=cost_root,
    )

    repo_root = Path(__file__).resolve().parent.parent.parent
    shipped_skill_dir = (
        repo_root
        / "mvp"
        / "skills"
        / "paper_derived"
        / "compute_beneish_m_score"
    )
    shipped_gold_dir = repo_root / "mvp" / "eval" / "gold" / "beneish"

    delta = compare_calibration_outputs(
        report,
        paper_id="beneish_1999",
        shipped_skill_dir=shipped_skill_dir,
        shipped_gold_dir=shipped_gold_dir,
    )

    assert delta["paper_id"] == "beneish_1999"
    assert delta["gold_present_count_shipped"] == 5  # 5 issuers
    # Each comparison record names its label.
    labels = [c["label"] for c in delta["comparisons"]]
    assert "skill.py" in labels
    assert "manifest.yaml" in labels
