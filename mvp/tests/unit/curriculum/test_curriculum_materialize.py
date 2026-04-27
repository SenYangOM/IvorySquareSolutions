"""Unit tests for ``mvp.curriculum.materialize``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from mvp.curriculum.graph import CurriculumGraph, CurriculumNode
from mvp.curriculum.materialize import materialize_node, validate_generated_manifest


def _sample_decision(reason: str) -> dict:
    return {
        "decision": {
            "decision": "keep_code_backed" if reason == "closed_form_determinism" else "keep_markdown_only",
            "materialization_reason": reason,
            "pass_rate": 0.78,
            "rationale": "test fixture",
        },
        "baseline": {
            "node_id": "foundational/test/demo/ch01__01__widget",
            "n_trials_per_question": 10,
            "n_questions": 1,
            "pass_rate": 0.78,
            "failure_mode_tags": {
                "qualitative_correct": 0,
                "computational_off_by_arithmetic": 1,
                "structural_misunderstanding": 0,
                "unit_or_dimension_error": 0,
                "partial_correct": 0,
            },
            "mode": "synthetic",
            "trials": [],
        },
        "pass_rate": 0.78,
        "failure_mode_tags": {
            "qualitative_correct": 0,
            "computational_off_by_arithmetic": 1,
            "structural_misunderstanding": 0,
            "unit_or_dimension_error": 0,
            "partial_correct": 0,
        },
        "n_questions": 1,
        "mode": "synthetic",
        "materialization_reason": reason,
    }


def _make_node(node_id: str) -> CurriculumNode:
    return CurriculumNode(
        id=node_id,
        branch="test",
        book_id="demo",
        chapter=1,
        section=1,
        subsection="widget",
        title="Widget concept",
    )


def test_materialize_closed_form_writes_full_file_set(tmp_path) -> None:
    node_id = "foundational/test/demo/ch01__01__widget"
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node(node_id))
    g.save()

    draft = tmp_path / "draft"
    draft.mkdir(parents=True)
    (draft / "concept.md").write_text("# Widget\n\nDemo content.\n", encoding="utf-8")
    (draft / "question_bank.yaml").write_text(
        yaml.safe_dump(
            {
                "questions": [
                    {
                        "id": "q1",
                        "prompt": "What is a widget?",
                        "expected": "demo",
                        "kind": "computational",
                        "answer_match": "substring",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    code_dir = draft / "code"
    code_dir.mkdir()
    (code_dir / "widget.py").write_text(
        '"""Widget reference."""\n\ndef widget(x):\n    return x + 1\n',
        encoding="utf-8",
    )
    (draft / "decision.json").write_text(
        json.dumps(_sample_decision("closed_form_determinism")),
        encoding="utf-8",
    )

    target_root = tmp_path / "target"
    out = materialize_node(
        node_id, graph=g, draft_root=draft, target_root=target_root
    )
    skill_dir = Path(out["skill_dir"])
    files = set(out["files_written"])
    assert "concept.md" in files
    assert "manifest.yaml" in files
    assert "prereqs.yaml" in files
    assert "eval/llm_baseline.json" in files
    assert "eval/question_bank.yaml" in files
    assert "code/widget.py" in files
    assert "foundational_meta.yaml" in files
    # Manifest must validate.
    validate_generated_manifest(skill_dir / "manifest.yaml")
    # Confirm the test wrote under the override, not the real tree.
    assert str(skill_dir).startswith(str(target_root))


def test_materialize_requires_decision_json(tmp_path) -> None:
    node_id = "foundational/test/demo/ch01__01__missing_decision"
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(
        CurriculumNode(
            id=node_id, branch="test", book_id="demo", chapter=1, section=1,
            subsection="missing_decision", title="x",
        )
    )
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "concept.md").write_text("# x", encoding="utf-8")
    (draft / "question_bank.yaml").write_text(
        yaml.safe_dump({"questions": [{"id": "q1", "prompt": "q", "expected": "a", "kind": "conceptual"}]}),
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        materialize_node(node_id, graph=g, draft_root=draft)


def test_materialize_rejects_invalid_reason(tmp_path) -> None:
    node_id = "foundational/test/demo/ch01__01__bad_reason"
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(
        CurriculumNode(
            id=node_id, branch="test", book_id="demo", chapter=1, section=1,
            subsection="bad_reason", title="x",
        )
    )
    draft = tmp_path / "draft"
    draft.mkdir()
    (draft / "concept.md").write_text("# x", encoding="utf-8")
    (draft / "question_bank.yaml").write_text(
        yaml.safe_dump({"questions": [{"id": "q1", "prompt": "q", "expected": "a", "kind": "conceptual"}]}),
        encoding="utf-8",
    )
    bad = _sample_decision("not_a_real_reason")
    bad["materialization_reason"] = "not_a_real_reason"
    bad["decision"]["materialization_reason"] = "not_a_real_reason"
    (draft / "decision.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        materialize_node(node_id, graph=g, draft_root=draft)
