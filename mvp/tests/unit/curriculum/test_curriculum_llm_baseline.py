"""Unit tests for ``mvp.curriculum.llm_baseline``."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from mvp.curriculum.llm_baseline import (
    decide_materialization,
    load_question_bank,
    run_baseline,
    write_baseline_snapshot,
)


def _bank_yaml(tmp_path: Path, questions: list[dict]) -> Path:
    p = tmp_path / "qb.yaml"
    p.write_text(yaml.safe_dump({"questions": questions}), encoding="utf-8")
    return p


def test_load_question_bank_rejects_missing_keys(tmp_path: Path) -> None:
    p = _bank_yaml(tmp_path, [{"id": "q1", "prompt": "x"}])
    with pytest.raises(ValueError):
        load_question_bank(p)


def test_load_question_bank_normal(tmp_path: Path) -> None:
    p = _bank_yaml(
        tmp_path,
        [
            {"id": "q1", "prompt": "p1", "expected": "answer", "kind": "conceptual"},
            {"id": "q2", "prompt": "p2", "expected": 1.5, "kind": "computational",
             "answer_match": "numeric"},
        ],
    )
    bank = load_question_bank(p)
    assert len(bank) == 2
    assert bank[1]["answer_match"] == "numeric"


def test_synthetic_run_classifies_computational_below_markdown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    bank = [
        {
            "id": f"q{i}",
            "prompt": f"compute thing {i}",
            "expected": float(i),
            "kind": "computational",
            "answer_match": "numeric",
            "tags": ["computational"],
        }
        for i in range(1, 4)
    ]
    run = run_baseline(
        node_id="foundational/or/dummy/ch01__01__demo",
        question_bank=bank,
        n_trials=10,
        cache_dir=tmp_path / ".cache",
    )
    assert run.mode == "synthetic"
    # Synthetic policy for 'computational': pass rate ~0.7
    assert 0.55 <= run.pass_rate <= 0.85
    decision = decide_materialization(run, is_closed_form=False)
    assert decision.decision == "keep_code_backed"
    assert decision.materialization_reason == "llm_fails"


def test_decide_drops_when_pass_rate_above_drop_threshold() -> None:
    from mvp.curriculum.llm_baseline import BaselineRun

    run = BaselineRun(
        node_id="x",
        n_trials_per_question=10,
        n_questions=5,
        pass_rate=0.97,
        failure_mode_tags={
            "qualitative_correct": 1,
            "computational_off_by_arithmetic": 0,
            "structural_misunderstanding": 0,
            "unit_or_dimension_error": 0,
            "partial_correct": 0,
        },
        trials=[],
    )
    decision = decide_materialization(run, is_closed_form=False)
    assert decision.decision == "drop"
    assert decision.materialization_reason is None


def test_decide_keeps_markdown_only_in_intermediate_band() -> None:
    from mvp.curriculum.llm_baseline import BaselineRun

    run = BaselineRun(
        node_id="x",
        n_trials_per_question=10,
        n_questions=5,
        pass_rate=0.90,
        failure_mode_tags={
            "qualitative_correct": 5,
            "computational_off_by_arithmetic": 0,
            "structural_misunderstanding": 0,
            "unit_or_dimension_error": 0,
            "partial_correct": 0,
        },
        trials=[],
    )
    decision = decide_materialization(run, is_closed_form=False, is_conceptual=True)
    assert decision.decision == "keep_markdown_only"
    assert decision.materialization_reason == "conceptual_high_value"


def test_decide_closed_form_overrides_pass_rate() -> None:
    from mvp.curriculum.llm_baseline import BaselineRun

    run = BaselineRun(
        node_id="x",
        n_trials_per_question=10,
        n_questions=5,
        pass_rate=0.99,
        failure_mode_tags={tag: 0 for tag in (
            "qualitative_correct",
            "computational_off_by_arithmetic",
            "structural_misunderstanding",
            "unit_or_dimension_error",
            "partial_correct",
        )},
        trials=[],
    )
    decision = decide_materialization(run, is_closed_form=True)
    assert decision.decision == "keep_code_backed"
    assert decision.materialization_reason == "closed_form_determinism"


def test_write_baseline_snapshot_writes_json(tmp_path: Path) -> None:
    from mvp.curriculum.llm_baseline import BaselineRun

    run = BaselineRun(
        node_id="x",
        n_trials_per_question=2,
        n_questions=1,
        pass_rate=0.5,
        failure_mode_tags={
            "qualitative_correct": 0,
            "computational_off_by_arithmetic": 1,
            "structural_misunderstanding": 0,
            "unit_or_dimension_error": 0,
            "partial_correct": 0,
        },
        trials=[],
    )
    out = tmp_path / "llm_baseline.json"
    write_baseline_snapshot(run, path=out)
    assert out.is_file()
    data = out.read_text(encoding="utf-8")
    assert "pass_rate" in data
