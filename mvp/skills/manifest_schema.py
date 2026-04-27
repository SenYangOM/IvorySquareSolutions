"""Skill manifest schema — Pydantic v2 models + MCP / OpenAI tool-spec projections.

Every skill under ``mvp/skills/{fundamental,interpretation,paper_derived,composite}``
ships with a ``manifest.yaml`` that loads into a :class:`SkillManifest`.
The manifest is the **single source of truth** for the skill's identity,
its provenance (for paper-derived skills), its I/O schema (JSON-Schema
with per-leaf LLM-readable descriptions), its citation contract, its
confidence model, and its evaluation metadata.

Per Operating Principle P3 (``mvp_build_goal.md`` §0), every manifest is
projectable to an MCP tool spec and to an OpenAI tool-use spec. The
projection helpers live on the :class:`SkillManifest` model itself so the
registry can emit both catalogs without duplicating logic.

Schema structure mirrors ``mvp_build_goal.md`` §6 verbatim. Fields that
§6 marks as "populated later by eval harness" (``current_pass_rate``,
``last_eval_run``) accept ``None`` at manifest-write time; every other
field must be populated on-disk. The JSON-Schema-style ``inputs`` and
``outputs`` blocks are validated to ensure every non-object leaf has a
``description`` field that reads well to an LLM caller — that rule is
enforced by :func:`_validate_leaf_descriptions`.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


SkillLayer = Literal[
    "fundamental",
    "interpretation",
    "paper_derived",
    "composite",
    "foundational",
]
SkillStatus = Literal["alpha", "beta", "ga", "deprecated"]
MaterializationReason = Literal[
    "llm_fails",
    "closed_form_determinism",
    "conceptual_high_value",
]
MaintainerPersona = Literal[
    "accounting_expert",
    "quant_finance_methodologist",
    "evaluation_agent",
    "citation_auditor",
]
CalibrationStatus = Literal["uncalibrated_at_mvp", "calibrated"]


# ---------------------------------------------------------------------------
# Sub-models for the various manifest blocks.
# ---------------------------------------------------------------------------


class SourcePaper(BaseModel):
    """A single source paper referenced by a paper-derived skill's provenance block."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    citation: str = Field(min_length=20)
    doi_or_url: str = Field(min_length=5)
    local_pdf: str = Field(min_length=5)
    pdf_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class StudyScope(BaseModel):
    """Study-scope subset of the provenance block — the scope of the original paper."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    asset_class: str = Field(min_length=3)
    time_period_in_paper: str = Field(min_length=3)
    sample_size_in_paper: str = Field(min_length=3)


class ProblemStatement(BaseModel):
    """Hypothesis-test-style problem block of a paper-derived skill's provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    one_line: str = Field(min_length=20)
    long_form: str = Field(min_length=40)


class Methodology(BaseModel):
    """Methodology block — how the paper answers the problem it poses."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str = Field(min_length=30)
    formulas_extracted_from_paper: dict[str, str] = Field(default_factory=dict)
    threshold: str = Field(min_length=5)


class ExpectedResults(BaseModel):
    """What the skill is expected to output, described semantically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metric_kind: str = Field(min_length=5)
    interpretation_guide: str = Field(min_length=20)


class Provenance(BaseModel):
    """Hypothesis-test-style provenance block per ``mvp_build_goal.md`` §6."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_papers: list[SourcePaper] = Field(default_factory=list)
    study_scope: StudyScope | None = None
    problem: ProblemStatement | None = None
    methodology: Methodology | None = None
    expected_results: ExpectedResults | None = None
    takeaways: list[str] = Field(default_factory=list)
    use_cases: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_sub_blocks_when_source_papers_present(self) -> "Provenance":
        # Paper-derived skills must populate the full provenance chain.
        # Fundamental / composite skills may legitimately have empty
        # source_papers and thus an empty provenance block — the skill's
        # maintainer_persona signals which it is.
        if self.source_papers:
            missing: list[str] = []
            if self.study_scope is None:
                missing.append("study_scope")
            if self.problem is None:
                missing.append("problem")
            if self.methodology is None:
                missing.append("methodology")
            if self.expected_results is None:
                missing.append("expected_results")
            if not self.takeaways:
                missing.append("takeaways")
            if not self.use_cases:
                missing.append("use_cases")
            if missing:
                raise ValueError(
                    "provenance.source_papers is non-empty, but these sub-blocks "
                    f"are missing or empty: {', '.join(missing)}"
                )
        return self


class ImplementationDecision(BaseModel):
    """A single implementation decision — the record an auditor reviews."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision: str = Field(min_length=10)
    rationale: str = Field(min_length=10)
    reviewer_persona: MaintainerPersona


class CitationContract(BaseModel):
    """Per-field citation requirements for a skill's outputs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required_per_field: dict[str, str] = Field(default_factory=dict)
    hash_algorithm: Literal["sha256"] = "sha256"
    locator_format: str = Field(min_length=5)


class ConfidenceSpec(BaseModel):
    """How the skill computes its confidence score + its calibration status."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    computed_from: list[str] = Field(default_factory=list, min_length=1)
    calibration_status: CalibrationStatus


class SkillDependency(BaseModel):
    """A dependency on another skill (by id + min_version)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skill_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    min_version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class Dependencies(BaseModel):
    """Dependency declarations: other skills, lib modules, rule templates."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    skills: list[SkillDependency] = Field(default_factory=list)
    lib: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list)


class EvalMetric(BaseModel):
    """A single eval metric the skill is graded on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3)
    target: str = Field(min_length=2)


class Evaluation(BaseModel):
    """Evaluation-harness metadata — populated at skill-write time; live
    ``current_pass_rate`` / ``last_eval_run`` come from Phase 5 runs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gold_standard_path: str = Field(min_length=3)
    current_pass_rate: float | None = None
    last_eval_run: datetime | None = None
    eval_metrics: list[EvalMetric] = Field(default_factory=list, min_length=1)


class Example(BaseModel):
    """A worked input/output example.

    Optional typed expectation fields drive ``workshop/paper_to_skill/
    replication_harness.py`` when present. The harness compares the
    expectations against the shipped skill's live output and emits a
    pass/fail per example. When no typed expectations are present the
    harness performs a liveness-only check (skill returns a non-error
    envelope).

    - ``expected_flag`` (str) — exact string match on the skill's
      ``flag`` output.
    - ``expected_m_score_range`` / ``expected_z_score_range`` — legacy
      score-range fields retained for Beneish M / Altman Z manifests.
      Both encode a 2-item ``[low, high]`` inclusive band.
    - ``expected_score_range`` — generic 2-item ``[low, high]``
      inclusive band matched against the skill's primary score field
      (resolved via the harness's ``_SCORE_KEYS`` table). Added in
      paper-5 onboarding when the prior legacy-only fields blocked
      the replication harness from driving
      ``predict_filing_complexity_from_determinants`` (whose primary
      score is ``predicted_complexity_level``) end-to-end.
    - ``expected_score_tolerance`` — alternative to range:
      ``{"value": X, "tolerance": Y}`` matches when the score is
      within ±Y of X. Added alongside ``expected_score_range`` for
      paper-replication examples where a target value + symmetric
      tolerance is more natural than a band.

    All new fields default to ``None`` so Papers 1-4 manifests
    (written before the extension) continue to validate unchanged.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=3)
    input: dict[str, Any]
    expected_flag: str | None = None
    expected_m_score_range: list[float] | None = None
    expected_z_score_range: list[float] | None = None
    expected_score_range: list[float] | None = None
    expected_score_tolerance: dict[str, float] | None = None
    notes: str = Field(min_length=5)


class CostEstimate(BaseModel):
    """Per-call cost envelope — tokens, external calls, expected latency."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    llm_tokens_per_call: int = Field(ge=0)
    external_api_calls: int = Field(ge=0)
    typical_latency_ms: int = Field(ge=0)


# ---------------------------------------------------------------------------
# Top-level SkillManifest.
# ---------------------------------------------------------------------------


class SkillManifest(BaseModel):
    """One skill's full manifest.

    See ``mvp_build_goal.md`` §6 for the field-by-field spec. The schema is
    strict (``extra="forbid"``); any unknown key fails validation at load
    time so manifest drift cannot silently accumulate.

    The ``inputs`` and ``outputs`` blocks are stored as JSON-Schema-style
    dicts rather than further Pydantic sub-models — each skill's I/O shape
    differs and the JSON-Schema dict projects directly to MCP / OpenAI /
    FastAPI documentation. Post-load validation ensures every non-object
    leaf carries a ``description`` field (see :func:`_validate_leaf_descriptions`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    skill_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=3, max_length=64)
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")
    layer: SkillLayer
    status: SkillStatus
    maintainer_persona: MaintainerPersona
    description_for_llm: str = Field(min_length=80, max_length=2000)
    # Optional: foundational-layer-only — surfaces *why* the bare-LLM filter
    # decided this subsection earned a materialized skill. One of
    # llm_fails | closed_form_determinism | conceptual_high_value. Other
    # layers must leave this null.
    materialization_reason: MaterializationReason | None = None

    provenance: Provenance = Field(default_factory=lambda: Provenance())
    implementation_decisions: list[ImplementationDecision] = Field(default_factory=list)

    inputs: dict[str, Any]
    outputs: dict[str, Any]

    citation_contract: CitationContract
    confidence: ConfidenceSpec
    dependencies: Dependencies = Field(default_factory=lambda: Dependencies())
    evaluation: Evaluation

    limitations: list[str] = Field(min_length=1)
    examples: list[Example] = Field(min_length=1)
    cost_estimate: CostEstimate

    # ----------------- validators ------------------------------------------

    @field_validator("description_for_llm")
    @classmethod
    def _no_trivial_description(cls, v: str) -> str:
        stripped = v.strip()
        if len(stripped) < 80:
            raise ValueError(
                "description_for_llm must be at least 80 characters — it is how an "
                "LLM caller decides whether to invoke this skill."
            )
        return stripped

    @field_validator("inputs", "outputs")
    @classmethod
    def _leaf_descriptions(cls, schema: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(schema, dict):
            raise ValueError("inputs/outputs must be a JSON-Schema-style dict")
        missing = _validate_leaf_descriptions(schema, path="$")
        if missing:
            raise ValueError(
                "inputs/outputs leaf schemas missing LLM-readable descriptions: "
                + "; ".join(missing[:5])
                + (f"; (+{len(missing) - 5} more)" if len(missing) > 5 else "")
            )
        return schema

    @model_validator(mode="after")
    def _cross_field_checks(self) -> "SkillManifest":
        # A paper_derived skill must have at least one source_paper and at
        # least one implementation decision.
        if self.layer == "paper_derived":
            if not self.provenance.source_papers:
                raise ValueError(
                    f"paper_derived skill {self.skill_id!r} must have at least one "
                    "provenance.source_papers entry"
                )
            if not self.implementation_decisions:
                raise ValueError(
                    f"paper_derived skill {self.skill_id!r} must have at least one "
                    "implementation_decisions entry"
                )
        # A composite skill must declare at least one sub-skill dependency.
        if self.layer == "composite" and not self.dependencies.skills:
            raise ValueError(
                f"composite skill {self.skill_id!r} must declare its sub-skill "
                "dependencies in dependencies.skills"
            )
        # Status guard: 'ga' requires calibrated confidence.
        if self.status == "ga" and self.confidence.calibration_status != "calibrated":
            raise ValueError(
                f"skill {self.skill_id!r} has status=ga but confidence is not calibrated"
            )
        # Foundational layer must declare a materialization_reason; all other
        # layers must leave it null so the field's meaning is preserved.
        if self.layer == "foundational" and self.materialization_reason is None:
            raise ValueError(
                f"foundational skill {self.skill_id!r} must set "
                "materialization_reason (llm_fails | closed_form_determinism "
                "| conceptual_high_value)"
            )
        if self.layer != "foundational" and self.materialization_reason is not None:
            raise ValueError(
                f"skill {self.skill_id!r} has layer={self.layer!r} but sets "
                "materialization_reason; that field is foundational-only"
            )
        return self

    # ----------------- projections -----------------------------------------

    def as_mcp_tool(self) -> dict[str, Any]:
        """Project the manifest to a Model Context Protocol tool spec.

        MCP shape: ``{"name": <id>, "description": <desc>, "inputSchema": <schema>}``
        where ``inputSchema`` is a JSON Schema dict with an outer
        ``{"type": "object"}`` wrapper — MCP requires object-typed inputs.
        """
        return {
            "name": self.skill_id,
            "description": self.description_for_llm,
            "inputSchema": _wrap_as_object_schema(self.inputs),
        }

    def as_openai_tool(self) -> dict[str, Any]:
        """Project the manifest to an OpenAI tool-use spec.

        OpenAI shape: ``{"type": "function", "function": {...}}`` where
        ``function.parameters`` is a JSON Schema dict (same content as
        MCP ``inputSchema``).
        """
        return {
            "type": "function",
            "function": {
                "name": self.skill_id,
                "description": self.description_for_llm,
                "parameters": _wrap_as_object_schema(self.inputs),
            },
        }

    def to_openapi_operation(self) -> dict[str, Any]:
        """Project to a FastAPI-friendly OpenAPI operation dict.

        Consumed by Phase 6's ``mvp.api.server`` to auto-generate API
        docs from the same manifest. Returns an operation object keyed
        by the conventional ``summary`` / ``description`` / ``requestBody``
        / ``responses`` shape.
        """
        return {
            "operationId": self.skill_id,
            "summary": f"{self.skill_id} (v{self.version})",
            "description": self.description_for_llm,
            "requestBody": {
                "required": True,
                "content": {
                    "application/json": {"schema": _wrap_as_object_schema(self.inputs)}
                },
            },
            "responses": {
                "200": {
                    "description": "Skill output envelope.",
                    "content": {
                        "application/json": {
                            "schema": _wrap_as_object_schema(self.outputs)
                        }
                    },
                }
            },
        }

    # ----------------- loader ----------------------------------------------

    @classmethod
    def load_from_yaml(cls, path: Path | str) -> "SkillManifest":
        """Load and strictly validate a manifest YAML from disk.

        Raises
        ------
        FileNotFoundError
            If ``path`` does not exist.
        ValueError
            If the YAML is not a mapping or the root-level schema
            validation fails. ``pydantic.ValidationError`` is re-raised as
            ``ValueError`` with the full validation trace preserved.
        """
        p = Path(path)
        if not p.is_file():
            raise FileNotFoundError(f"manifest YAML not found at {p}")
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(
                f"manifest YAML at {p} must be a mapping, got {type(raw).__name__}"
            )
        try:
            return cls.model_validate(raw)
        except Exception as exc:  # pydantic.ValidationError broadened
            raise ValueError(f"manifest YAML at {p} failed schema validation: {exc}") from exc


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


_JSON_SCHEMA_LEAF_TYPES = frozenset({"string", "number", "integer", "boolean", "array", "null"})
"""Types whose leaves require a ``description`` field per P3."""


def _validate_leaf_descriptions(schema: dict[str, Any], *, path: str) -> list[str]:
    """Return a list of JSON-Schema paths whose leaves are missing ``description``.

    An "object" node is recursed into via its ``properties``. An "array"
    node has its ``items`` recursed into. All other concrete leaf types
    (``string``, ``number``, ``integer``, ``boolean``, ``null``) must
    carry a ``description`` field — that field is what an LLM uses to
    populate the input correctly.

    The top-level object schema itself does not require a description
    (its description comes from the manifest's ``description_for_llm``),
    so we only check nested leaves.
    """
    missing: list[str] = []
    node_type = schema.get("type")
    # References (e.g., {"$ref": "#/..."}) are passed through unchecked —
    # the referenced definition should itself be validated; MVP manifests
    # don't use $ref in I/O schemas.
    if "$ref" in schema:
        return missing
    if node_type == "object" or ("properties" in schema and node_type is None):
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            return missing
        for name, sub in props.items():
            if not isinstance(sub, dict):
                continue
            missing.extend(_validate_leaf_descriptions(sub, path=f"{path}.{name}"))
        return missing
    if node_type == "array":
        items = schema.get("items")
        if isinstance(items, dict):
            # Array leaves need a description themselves OR their items need one.
            if "description" not in schema and not _has_leaf_description(items):
                missing.append(path)
            if isinstance(items, dict):
                missing.extend(_validate_leaf_descriptions(items, path=f"{path}[]"))
        else:
            if "description" not in schema:
                missing.append(path)
        return missing
    if isinstance(node_type, str) and node_type in _JSON_SCHEMA_LEAF_TYPES:
        if "description" not in schema or not schema["description"]:
            missing.append(path)
        return missing
    # Unknown/untyped node (e.g. anyOf, oneOf): descend best-effort.
    for key in ("anyOf", "oneOf", "allOf"):
        sub_list = schema.get(key)
        if isinstance(sub_list, list):
            for i, sub in enumerate(sub_list):
                if isinstance(sub, dict):
                    missing.extend(
                        _validate_leaf_descriptions(sub, path=f"{path}[{key}:{i}]")
                    )
    return missing


def _has_leaf_description(schema: dict[str, Any]) -> bool:
    """Whether ``schema`` or its immediate descendants carry a description."""
    if isinstance(schema.get("description"), str) and schema["description"].strip():
        return True
    return False


def _wrap_as_object_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure the returned schema has ``{"type": "object"}`` at the root.

    Manifest ``inputs`` / ``outputs`` blocks are authored as object
    schemas (``type: object`` + ``properties``) so this is usually a
    pass-through. We deep-copy to avoid leaking the manifest's frozen
    dict into caller-mutable spec structures.
    """
    import copy

    copied = copy.deepcopy(schema)
    if copied.get("type") != "object":
        copied.setdefault("type", "object")
    return copied


__all__ = [
    "CalibrationStatus",
    "CitationContract",
    "ConfidenceSpec",
    "CostEstimate",
    "Dependencies",
    "Evaluation",
    "EvalMetric",
    "Example",
    "ExpectedResults",
    "ImplementationDecision",
    "MaintainerPersona",
    "Methodology",
    "ProblemStatement",
    "Provenance",
    "SkillDependency",
    "SkillLayer",
    "SkillManifest",
    "SkillStatus",
    "SourcePaper",
    "StudyScope",
]
