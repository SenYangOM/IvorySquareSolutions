"""Schema tests for SkillManifest + MCP / OpenAI projections.

Enforces:
- Every shipped manifest under mvp/skills/<layer>/<skill_id>/manifest.yaml
  round-trips through SkillManifest.load_from_yaml without raising.
- as_mcp_tool() projects to the MCP shape {name, description, inputSchema}.
- as_openai_tool() projects to the OpenAI shape {type: function, function: {...}}.
- Leaf description enforcement catches a manifest that omits a description.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.skills.manifest_schema import SkillManifest


_MVP_ROOT = Path(__file__).resolve().parents[3]
_SKILL_ROOT = _MVP_ROOT / "skills"


def _all_manifest_paths() -> list[Path]:
    return sorted(_SKILL_ROOT.glob("*/*/manifest.yaml"))


@pytest.mark.parametrize("path", _all_manifest_paths(), ids=lambda p: p.parent.name)
def test_manifest_loads(path: Path) -> None:
    manifest = SkillManifest.load_from_yaml(path)
    # Basic shape assertions that must hold for every manifest.
    assert manifest.skill_id
    assert manifest.version.count(".") == 2
    assert manifest.description_for_llm
    assert manifest.inputs.get("type") == "object"
    assert manifest.outputs.get("type") == "object"
    assert manifest.examples, "every manifest must carry at least one example"
    assert manifest.evaluation.gold_standard_path
    assert manifest.evaluation.eval_metrics


@pytest.mark.parametrize("path", _all_manifest_paths(), ids=lambda p: p.parent.name)
def test_mcp_projection(path: Path) -> None:
    manifest = SkillManifest.load_from_yaml(path)
    spec = manifest.as_mcp_tool()
    assert set(spec.keys()) == {"name", "description", "inputSchema"}
    assert spec["name"] == manifest.skill_id
    assert spec["description"] == manifest.description_for_llm
    assert spec["inputSchema"].get("type") == "object"


@pytest.mark.parametrize("path", _all_manifest_paths(), ids=lambda p: p.parent.name)
def test_openai_projection(path: Path) -> None:
    manifest = SkillManifest.load_from_yaml(path)
    spec = manifest.as_openai_tool()
    assert spec.get("type") == "function"
    fn = spec["function"]
    assert fn["name"] == manifest.skill_id
    assert fn["description"] == manifest.description_for_llm
    assert fn["parameters"].get("type") == "object"


def test_leaf_descriptions_enforced() -> None:
    """A manifest with a leaf missing 'description' must fail validation."""
    bad = {
        "skill_id": "bad_leaf_test",
        "version": "0.1.0",
        "layer": "fundamental",
        "status": "alpha",
        "maintainer_persona": "accounting_expert",
        "description_for_llm": "A test manifest that should fail leaf-description validation." * 2,
        "inputs": {
            "type": "object",
            "required": ["cik"],
            "properties": {
                "cik": {"type": "string"},  # missing description on purpose
            },
        },
        "outputs": {
            "type": "object",
            "required": ["ok"],
            "properties": {
                "ok": {"type": "boolean", "description": "ok bit"},
            },
        },
        "citation_contract": {
            "required_per_field": {},
            "hash_algorithm": "sha256",
            "locator_format": "a::b::c",
        },
        "confidence": {
            "computed_from": ["nothing"],
            "calibration_status": "uncalibrated_at_mvp",
        },
        "evaluation": {
            "gold_standard_path": "eval/gold/none/",
            "eval_metrics": [{"name": "x", "target": ">= 0"}],
        },
        "limitations": ["test-only"],
        "examples": [{"name": "x", "input": {}, "notes": "test"}],
        "cost_estimate": {
            "llm_tokens_per_call": 0,
            "external_api_calls": 0,
            "typical_latency_ms": 0,
        },
    }
    with pytest.raises(Exception):
        SkillManifest(**bad)


def test_paper_derived_requires_provenance() -> None:
    """A paper_derived skill without source_papers must fail validation."""
    base: dict = {
        "skill_id": "fake_paper_skill",
        "version": "0.1.0",
        "layer": "paper_derived",
        "status": "alpha",
        "maintainer_persona": "quant_finance_methodologist",
        "description_for_llm": "Fake paper-derived skill for tests — must be at least 80 characters long.",
        "inputs": {
            "type": "object",
            "required": ["cik"],
            "properties": {
                "cik": {"type": "string", "description": "cik"},
            },
        },
        "outputs": {
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean", "description": "ok bit"}},
        },
        "citation_contract": {
            "required_per_field": {},
            "hash_algorithm": "sha256",
            "locator_format": "a::b::c",
        },
        "confidence": {
            "computed_from": ["nothing"],
            "calibration_status": "uncalibrated_at_mvp",
        },
        "evaluation": {
            "gold_standard_path": "eval/gold/none/",
            "eval_metrics": [{"name": "x", "target": ">= 0"}],
        },
        "limitations": ["test-only"],
        "examples": [{"name": "x", "input": {}, "notes": "test"}],
        "cost_estimate": {
            "llm_tokens_per_call": 0,
            "external_api_calls": 0,
            "typical_latency_ms": 0,
        },
    }
    with pytest.raises(Exception):
        SkillManifest(**base)


def test_composite_requires_dependencies() -> None:
    """A composite skill without sub-skill dependencies must fail validation."""
    base: dict = {
        "skill_id": "fake_composite",
        "version": "0.1.0",
        "layer": "composite",
        "status": "alpha",
        "maintainer_persona": "accounting_expert",
        "description_for_llm": "Fake composite for tests — must be at least 80 characters long.",
        "inputs": {
            "type": "object",
            "required": ["cik"],
            "properties": {"cik": {"type": "string", "description": "cik"}},
        },
        "outputs": {
            "type": "object",
            "required": ["ok"],
            "properties": {"ok": {"type": "boolean", "description": "ok bit"}},
        },
        "citation_contract": {
            "required_per_field": {},
            "hash_algorithm": "sha256",
            "locator_format": "a::b::c",
        },
        "confidence": {
            "computed_from": ["nothing"],
            "calibration_status": "uncalibrated_at_mvp",
        },
        "evaluation": {
            "gold_standard_path": "eval/gold/none/",
            "eval_metrics": [{"name": "x", "target": ">= 0"}],
        },
        "limitations": ["test-only"],
        "examples": [{"name": "x", "input": {}, "notes": "test"}],
        "cost_estimate": {
            "llm_tokens_per_call": 0,
            "external_api_calls": 0,
            "typical_latency_ms": 0,
        },
    }
    with pytest.raises(Exception):
        SkillManifest(**base)
