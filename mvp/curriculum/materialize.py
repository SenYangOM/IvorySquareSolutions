"""Foundational-skill materialization — turn a node + draft files into skill files.

Given a curriculum node and a draft directory containing
``concept.md``, ``question_bank.yaml`` and ``decision.json``, write the
final skill file set:

::

    mvp/skills/foundational/<branch>/<book_id>/<chapter>__<section>__<subsection>/
    ├── concept.md            # paraphrased summary + intuition + ASCII examples
    ├── prereqs.yaml          # explicit list of prerequisite skill_ids
    ├── eval/
    │   ├── question_bank.yaml
    │   └── llm_baseline.json
    ├── code/                 # OPTIONAL — required for closed_form_determinism
    │   ├── __init__.py
    │   └── <impl>.py
    ├── manifest.yaml
    └── README.md

The draft directory layout mirrors the final layout, so materialization
is mostly file copying + manifest synthesis. The manifest is generated
from the curriculum node's metadata + the filter decision; it is NOT
expected to ship pre-authored.
"""

from __future__ import annotations

import json
import re
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

import yaml

from mvp.curriculum.graph import CurriculumGraph, load_default


_MVP_ROOT = Path(__file__).resolve().parent.parent


def materialize_node(
    node_id: str,
    *,
    graph: CurriculumGraph | None = None,
    draft_root: Path | None = None,
    target_root: Path | None = None,
) -> dict[str, Any]:
    """Materialize a node from its draft directory into the foundational skill tree.

    Parameters
    ----------
    node_id:
        Curriculum node id, e.g.
        ``foundational/or/bertsimas_lp/ch01__01__lp_canonical_form``.
    graph:
        Curriculum graph instance. Defaults to the singleton.
    draft_root:
        Override the location to read the draft files from. Defaults to
        ``mvp/curriculum/drafts/<node_id_path>/``.
    target_root:
        Override the directory under which the materialized skill files
        are written. Defaults to ``mvp/skills/foundational/<...>/``.
        Tests use this to avoid polluting the real skill tree.
    """
    g = graph if graph is not None else load_default()
    if node_id not in g.nodes:
        raise ValueError(f"node {node_id!r} is not in the curriculum graph")
    node = g.nodes[node_id]

    draft_dir = _draft_dir(node_id, override=draft_root)
    if not draft_dir.is_dir():
        raise FileNotFoundError(
            f"draft directory not found at {draft_dir}; "
            "author concept.md, question_bank.yaml, and decision.json there"
        )

    decision_path = draft_dir / "decision.json"
    if not decision_path.is_file():
        raise FileNotFoundError(
            f"decision.json missing under {draft_dir}; run 'mvp curriculum filter' first"
        )
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    materialization_reason = _required_str(
        decision, ("decision", "materialization_reason")
    ) or _required_str(decision, ("materialization_reason",))
    if materialization_reason is None:
        raise ValueError(
            f"decision.json at {decision_path} does not name a materialization_reason"
        )
    if materialization_reason not in (
        "llm_fails",
        "closed_form_determinism",
        "conceptual_high_value",
    ):
        raise ValueError(
            f"decision.json materialization_reason {materialization_reason!r} is "
            "not one of llm_fails | closed_form_determinism | conceptual_high_value"
        )

    target_dir = _target_dir(node_id, override=target_root)
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "eval").mkdir(parents=True, exist_ok=True)

    # 1. concept.md (required)
    concept_src = draft_dir / "concept.md"
    if not concept_src.is_file():
        raise FileNotFoundError(f"concept.md missing under {draft_dir}")
    shutil.copyfile(concept_src, target_dir / "concept.md")

    # 2. eval/question_bank.yaml (required)
    qb_src = draft_dir / "question_bank.yaml"
    if not qb_src.is_file():
        raise FileNotFoundError(f"question_bank.yaml missing under {draft_dir}")
    shutil.copyfile(qb_src, target_dir / "eval" / "question_bank.yaml")

    # 3. eval/llm_baseline.json (lifted from decision.baseline)
    baseline = decision.get("baseline")
    if not isinstance(baseline, dict):
        raise ValueError(
            f"decision.json at {decision_path} does not contain a baseline payload"
        )
    (target_dir / "eval" / "llm_baseline.json").write_text(
        json.dumps(baseline, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    # 4. prereqs.yaml (from graph + draft override)
    prereq_ids = _resolve_prereqs(node_id, draft_dir, g)
    (target_dir / "prereqs.yaml").write_text(
        yaml.safe_dump(
            {"node_id": node_id, "prereqs": prereq_ids},
            sort_keys=False,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )

    # 5. code/ directory (required for closed_form_determinism)
    code_artifacts: list[str] = []
    code_src_dir = draft_dir / "code"
    if materialization_reason == "closed_form_determinism":
        if not code_src_dir.is_dir():
            raise FileNotFoundError(
                f"closed_form_determinism node requires draft code/ "
                f"directory under {draft_dir}"
            )
        target_code = target_dir / "code"
        target_code.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(code_src_dir.iterdir()):
            if src_file.name.startswith("."):
                continue
            shutil.copyfile(src_file, target_code / src_file.name)
            code_artifacts.append(src_file.name)
        # Always ensure __init__.py present.
        if not (target_code / "__init__.py").is_file():
            (target_code / "__init__.py").write_text(
                f'"""Reference code for foundational skill {_skill_id(node_id)!r}."""\n',
                encoding="utf-8",
            )
            if "__init__.py" not in code_artifacts:
                code_artifacts.append("__init__.py")
    elif code_src_dir.is_dir():
        # Optional code for non-closed-form skills is allowed but not required.
        target_code = target_dir / "code"
        target_code.mkdir(parents=True, exist_ok=True)
        for src_file in sorted(code_src_dir.iterdir()):
            if src_file.name.startswith("."):
                continue
            shutil.copyfile(src_file, target_code / src_file.name)
            code_artifacts.append(src_file.name)

    # 6. manifest.yaml + foundational_meta.yaml sidecar
    manifest_payload = _synthesize_manifest(
        node=node,
        decision=decision,
        materialization_reason=materialization_reason,
        prereqs=prereq_ids,
        code_artifacts=code_artifacts,
    )
    manifest_text = yaml.safe_dump(
        manifest_payload, sort_keys=False, allow_unicode=True
    )
    (target_dir / "manifest.yaml").write_text(manifest_text, encoding="utf-8")
    foundational_meta = _synthesize_foundational_meta(
        node=node,
        decision=decision,
        prereqs=prereq_ids,
        code_artifacts=code_artifacts,
    )
    (target_dir / "foundational_meta.yaml").write_text(
        yaml.safe_dump(foundational_meta, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    # 7. README.md (1-paragraph public-facing summary). Allow draft to ship one.
    readme_src = draft_dir / "README.md"
    if readme_src.is_file():
        shutil.copyfile(readme_src, target_dir / "README.md")
    else:
        (target_dir / "README.md").write_text(
            _default_readme(node, materialization_reason),
            encoding="utf-8",
        )

    # Update the graph: mark materialized.
    g.update_materialization(
        node_id,
        reason=materialization_reason,
        status="materialized",
    )
    g.save()

    return {
        "node_id": node_id,
        "skill_id": _skill_id(node_id),
        "materialization_reason": materialization_reason,
        "skill_dir": str(target_dir),
        "files_written": _list_files_under(target_dir),
    }


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _draft_dir(node_id: str, *, override: Path | None = None) -> Path:
    if override is not None:
        return Path(override)
    rel = node_id.split("foundational/", 1)[1]
    return _MVP_ROOT / "curriculum" / "drafts" / rel


def _target_dir(node_id: str, *, override: Path | None = None) -> Path:
    rel = node_id.split("foundational/", 1)[1]
    if override is not None:
        return Path(override) / rel
    return _MVP_ROOT / "skills" / "foundational" / rel


def _skill_id(node_id: str) -> str:
    """Compute the foundational skill_id from a curriculum node id.

    Mapping is deterministic and reversible: keep slashes-as-delimiters
    becomes underscores. The skill_id pattern in
    :class:`mvp.skills.manifest_schema.SkillManifest` is
    ``^[a-z][a-z0-9_]*$`` with max length 64 — the curriculum naming
    convention guarantees that.
    """
    rel = node_id.split("foundational/", 1)[1]
    skill = "fnd_" + re.sub(r"[^a-z0-9]+", "_", rel.lower()).strip("_")
    return skill[:64]


def _resolve_prereqs(
    node_id: str, draft_dir: Path, graph: CurriculumGraph
) -> list[str]:
    """Combine graph-derived and draft-authored prereq lists."""
    graph_prereqs = graph.prereqs_of(node_id)
    draft_path = draft_dir / "prereqs.yaml"
    if not draft_path.is_file():
        # Map node ids to skill ids for prereqs.yaml output.
        return sorted({_skill_id(p) for p in graph_prereqs})
    raw = yaml.safe_load(draft_path.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("prereqs"), list):
        extra = [str(p) for p in raw["prereqs"]]
    elif isinstance(raw, list):
        extra = [str(p) for p in raw]
    else:
        extra = []
    return sorted({*[_skill_id(p) for p in graph_prereqs], *extra})


def _synthesize_manifest(
    *,
    node: Any,
    decision: dict[str, Any],
    materialization_reason: str,
    prereqs: list[str],
    code_artifacts: list[str],
) -> dict[str, Any]:
    """Produce a manifest dict ready for ``yaml.safe_dump`` AND for SkillManifest."""
    skill_id = _skill_id(node.id)
    title = node.title.strip()
    description = (
        f"Foundational concept skill for {node.book_id} chapter "
        f"{node.chapter} section {node.section}: {title}. "
        f"Materialized because {materialization_reason}. "
        f"Inputs: a textbook-style query about this subsection. "
        f"Outputs: a concise concept answer plus a citation to the "
        f"concept.md surface and (when present) a code reference."
    )
    pass_rate = float(decision.get("pass_rate", 0.0))
    failure_modes = decision.get("failure_mode_tags") or {}

    inputs_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": False,
        "required": ["query"],
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    f"A textbook-style question about the subsection "
                    f"\"{title}\" — for example, a definition request, "
                    "a worked-example computation, or a conceptual check."
                ),
            },
            "context": {
                "type": "string",
                "description": (
                    "Optional surrounding context (e.g., a paper section "
                    "the foundational concept supports). Free-form."
                ),
            },
        },
    }

    outputs_schema: dict[str, Any] = {
        "type": "object",
        "additionalProperties": True,
        "required": ["answer", "concept_path"],
        "properties": {
            "answer": {
                "type": "string",
                "description": (
                    "Concise concept answer derived from concept.md or, "
                    "for closed-form-determinism skills, computed by the "
                    "code/ reference implementation."
                ),
            },
            "concept_path": {
                "type": "string",
                "description": (
                    "Repository-relative path to concept.md for this "
                    "subsection — the citation surface for the answer."
                ),
            },
            "code_artifacts": {
                "type": "array",
                "description": (
                    "List of files under code/ that implement the "
                    "deterministic reference. Empty when the skill is "
                    "markdown-only."
                ),
                "items": {
                    "type": "string",
                    "description": "One filename under the code/ directory.",
                },
            },
            "warnings": {
                "type": "array",
                "description": (
                    "Zero or more warnings — e.g., when the query falls "
                    "outside the concept's scope or a unit is ambiguous."
                ),
                "items": {
                    "type": "string",
                    "description": "One warning string.",
                },
            },
        },
    }

    citation_contract: dict[str, Any] = {
        "required_per_field": {
            "answer": (
                "answer must cite concept_path; closed-form-determinism "
                "skills additionally cite the code/ implementation."
            )
        },
        "hash_algorithm": "sha256",
        "locator_format": (
            "foundational::<branch>/<book_id>/<ch>__<sec>__<subsection>::concept.md"
        ),
    }

    confidence = {
        "computed_from": [
            f"bare_llm_pass_rate ({pass_rate:.2f}; foundational filter snapshot)",
            "deterministic_code_reference (when materialization_reason="
            "closed_form_determinism)",
        ],
        "calibration_status": "uncalibrated_at_mvp",
    }

    evaluation = {
        "gold_standard_path": (
            f"mvp/skills/foundational/{node.branch}/{node.book_id}/"
            f"ch{node.chapter:02d}__{node.section:02d}__{node.subsection}/"
            "eval/question_bank.yaml"
        ),
        "eval_metrics": [
            {
                "name": "concept_md_resolves",
                "target": "= 1.00",
            },
            {
                "name": "bare_llm_pass_rate_recorded",
                "target": "= 1.00",
            },
        ],
    }

    examples = [
        {
            "name": f"{node.book_id} {node.chapter}.{node.section} — definition probe",
            "input": {
                "query": f"State the definition or core idea of: {title}.",
            },
            "notes": (
                f"Synthesized example for the {skill_id} foundational skill. "
                f"Used by the curriculum eval to confirm the concept.md surface "
                f"is reachable; tighter expectation comes from question_bank.yaml."
            ),
        }
    ]

    cost_estimate = {
        "llm_tokens_per_call": 0,
        "external_api_calls": 0,
        "typical_latency_ms": 30,
    }

    payload: dict[str, Any] = {
        "skill_id": skill_id,
        "version": "0.1.0",
        "layer": "foundational",
        "status": "alpha",
        "maintainer_persona": _persona_for(node.branch),
        "description_for_llm": description,
        "materialization_reason": materialization_reason,
        "inputs": inputs_schema,
        "outputs": outputs_schema,
        "citation_contract": citation_contract,
        "confidence": confidence,
        "dependencies": {
            "skills": [],  # Foundational prereq edges live in prereqs.yaml.
            "lib": [],
            "rules": [],
        },
        "evaluation": evaluation,
        "limitations": [
            (
                f"Bare-LLM pass rate snapshot recorded {pass_rate:.2f} on "
                f"{decision.get('n_questions', 0) if isinstance(decision, dict) else 'unknown'} "
                f"questions; thresholds 0.85 / 0.95 are starting points, not "
                f"calibrated values."
            ),
            (
                "Foundational concept content is paraphrased and "
                "IvorySquare-authored; verbatim textbook content is "
                "deliberately excluded."
            ),
        ],
        "examples": examples,
        "cost_estimate": cost_estimate,
    }
    return payload


def _synthesize_foundational_meta(
    *,
    node: Any,
    decision: dict[str, Any],
    prereqs: list[str],
    code_artifacts: list[str],
) -> dict[str, Any]:
    """Build the ``foundational_meta.yaml`` sidecar payload.

    Stored as a sibling file rather than a manifest extension because the
    :class:`SkillManifest` schema is strict (``extra="forbid"``). The
    sidecar holds curriculum-graph-specific metadata that the registry
    does not need at skill-call time but the curriculum tooling does.
    """
    return {
        "branch": node.branch,
        "book_id": node.book_id,
        "chapter": node.chapter,
        "section": node.section,
        "subsection": node.subsection,
        "title": node.title.strip(),
        "prereqs": prereqs,
        "code_artifacts": code_artifacts,
        "filter_failure_modes": dict(decision.get("failure_mode_tags") or {}),
        "filter_mode": decision.get("mode", "live"),
        "filter_pass_rate": float(decision.get("pass_rate", 0.0)),
    }


def _persona_for(branch: str) -> str:
    if branch.lower() in ("finance", "accounting", "fin", "fa"):
        return "accounting_expert"
    return "quant_finance_methodologist"


def _default_readme(node: Any, materialization_reason: str) -> str:
    return (
        f"# {node.book_id} ch{node.chapter}.{node.section} — {node.title}\n\n"
        f"Foundational concept skill on the {node.branch} branch of the "
        f"IvorySquare curriculum. Materialization reason: "
        f"`{materialization_reason}`. The concept content lives in "
        f"`concept.md`; bare-LLM filter signal lives in "
        f"`eval/llm_baseline.json`; the question bank used to drive that "
        f"signal lives in `eval/question_bank.yaml`. Closed-form "
        f"reference code, when present, lives under `code/`.\n"
    )


def _required_str(d: dict[str, Any], path: tuple[str, ...]) -> str | None:
    cur: Any = d
    for k in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    if isinstance(cur, str):
        return cur
    return None


def _list_files_under(path: Path) -> list[str]:
    out: list[str] = []
    for p in sorted(path.rglob("*")):
        if p.is_file():
            out.append(str(p.relative_to(path)))
    return out


def validate_generated_manifest(manifest_path: Path) -> None:
    """Validate a generated foundational manifest passes :class:`SkillManifest`."""
    from mvp.skills.manifest_schema import SkillManifest

    SkillManifest.load_from_yaml(manifest_path)


__all__ = ["materialize_node", "validate_generated_manifest"]
