"""Abstract :class:`Skill` base class — shared contract for all L4 skill endpoints.

Every concrete skill under ``mvp/skills/{fundamental,interpretation,
paper_derived,composite}/<skill_id>/skill.py`` subclasses :class:`Skill`
and exposes a module-level ``SKILL`` constant pointing at the subclass —
the registry discovers skills by walking those directories and importing
``skill`` modules (see :mod:`mvp.skills.registry`).

Contract (P3 "the user is an AI agent")
---------------------------------------
- :meth:`Skill.run` validates inputs against the manifest's ``inputs``
  JSON Schema, invokes :meth:`_execute` (which subclasses implement),
  and validates the returned dict against the manifest's ``outputs``
  schema before surfacing it to the caller.
- Any error raised inside :meth:`_execute` is caught at this boundary
  and reformatted into the public error envelope
  ``{error_code, error_category, human_message, retry_safe, suggested_remediation}``.
  A typed :class:`LibError` is the expected internal representation; a
  raw exception is reformatted as ``internal_error`` with ``retry_safe=False``.
- Skills are deterministic: given the same inputs, :meth:`_execute` must
  return byte-identical outputs modulo the provenance timestamps that
  :meth:`run` adds post-hoc (``run_at``, ``run_id``).

``run`` does NOT mutate the manifest; instances are safe to share across
invocations. A concrete skill that needs long-lived state (e.g. a cache
handle) may store it on the instance — but it must treat state as an
optimization, never a correctness input.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, ClassVar

from mvp.lib.errors import ErrorCategory, LibError

from .manifest_schema import SkillManifest

# jsonschema is lazy-imported inside _validate_against_schema so the
# manifest module remains import-time cheap for tools that only need the
# Pydantic schema (e.g. the registry's list_skills operation).


class Skill(ABC):
    """Abstract base for every callable skill.

    Subclasses set the class variable :pyattr:`id` (must match the
    ``skill_id`` in the manifest) and either:

    - provide a ``MANIFEST_PATH: Path`` class variable pointing at the
      sibling ``manifest.yaml`` file, OR
    - override :meth:`_load_manifest` to return a :class:`SkillManifest`
      built programmatically (rare — tests use this).

    They implement :meth:`_execute`, which receives a validated input dict
    and returns a dict that will be validated against the manifest's
    ``outputs`` schema.

    Concrete subclasses SHOULD NOT override :meth:`run`; the input/output
    validation + provenance stamping + error reformatting that live there
    are load-bearing and uniform across skills.
    """

    id: ClassVar[str]
    MANIFEST_PATH: ClassVar[Path | None] = None

    def __init__(self, *, config: dict[str, Any] | None = None) -> None:
        self._config: dict[str, Any] = dict(config) if config else {}
        self._manifest: SkillManifest = self._load_manifest()
        if self._manifest.skill_id != self.id:
            raise ValueError(
                f"manifest skill_id {self._manifest.skill_id!r} does not match "
                f"class id {self.id!r}"
            )

    @property
    def manifest(self) -> SkillManifest:
        """The loaded :class:`SkillManifest`. Frozen, safe to share."""
        return self._manifest

    @property
    def config(self) -> dict[str, Any]:
        """Optional config dict passed at construction time."""
        return self._config

    # ------------------------------------------------------------------
    # Manifest loading — subclasses usually just set MANIFEST_PATH.
    # ------------------------------------------------------------------

    def _load_manifest(self) -> SkillManifest:
        if self.MANIFEST_PATH is None:
            raise NotImplementedError(
                f"{type(self).__name__} must set MANIFEST_PATH or override _load_manifest"
            )
        return SkillManifest.load_from_yaml(self.MANIFEST_PATH)

    # ------------------------------------------------------------------
    # Public run — validates I/O, wraps errors, stamps provenance.
    # ------------------------------------------------------------------

    def run(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Invoke the skill.

        Parameters
        ----------
        inputs:
            A mapping whose shape must match the manifest's ``inputs``
            JSON Schema. Extra fields and type mismatches are rejected
            at this boundary.

        Returns
        -------
        dict
            Either the skill's output (validated against the manifest's
            ``outputs`` schema) OR a structured error envelope of the
            shape
            ``{"error": {error_code, error_category, human_message,
            retry_safe, suggested_remediation, skill_id, version}}``.
            The envelope is returned as a regular dict — no exception
            leaks past :meth:`run`.
        """
        run_id = str(uuid.uuid4())
        run_at = datetime.now(timezone.utc).isoformat()
        try:
            self._validate_inputs(inputs)
        except _InputSchemaError as exc:
            return self._error_envelope(
                error_code="input_validation",
                error_category=ErrorCategory.INPUT_VALIDATION.value,
                human_message=str(exc),
                retry_safe=False,
                suggested_remediation=(
                    "Adjust the inputs to match this skill's JSON Schema "
                    "(see manifest.inputs)."
                ),
            )

        try:
            out = self._execute(inputs)
        except LibError as exc:
            return self._error_envelope(
                error_code=exc.error_code,
                error_category=exc.error_category.value,
                human_message=exc.message,
                retry_safe=exc.retry_safe,
                suggested_remediation=self._remediation_for(exc),
            )
        except Exception as exc:
            # Truly unexpected — we do not swallow these quietly, but we do
            # not leak a raw stack trace to an agent either. The message
            # carries the exception type + message; logs hold the traceback.
            return self._error_envelope(
                error_code="internal_error",
                error_category=ErrorCategory.INTERNAL.value,
                human_message=f"{type(exc).__name__}: {exc}",
                retry_safe=False,
                suggested_remediation=(
                    "Unexpected internal error. Re-check inputs; if the failure "
                    "repeats with known-good inputs, file a bug against the skill."
                ),
            )

        if not isinstance(out, dict):
            return self._error_envelope(
                error_code="internal_error",
                error_category=ErrorCategory.INTERNAL.value,
                human_message=(
                    f"skill {self.id!r} returned {type(out).__name__}; expected dict"
                ),
                retry_safe=False,
                suggested_remediation="File a bug against the skill.",
            )

        # Stamp per-call provenance onto the output. ``provenance`` is an
        # object we always populate; ``outputs`` schemas that want it
        # typed should include a ``provenance`` property.
        prov = dict(out.get("provenance") or {})
        prov.setdefault("skill_id", self.id)
        prov.setdefault("skill_version", self._manifest.version)
        prov["run_id"] = run_id
        prov["run_at"] = run_at
        out = {**out, "provenance": prov}

        try:
            self._validate_outputs(out)
        except _InputSchemaError as exc:
            return self._error_envelope(
                error_code="output_schema_violation",
                error_category=ErrorCategory.INTERNAL.value,
                human_message=str(exc),
                retry_safe=False,
                suggested_remediation=(
                    "The skill produced an output that violates its own schema. "
                    "This is an engineering bug; file against the skill."
                ),
            )
        return out

    # ------------------------------------------------------------------
    # Subclass contract.
    # ------------------------------------------------------------------

    @abstractmethod
    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Skill-specific logic. Must return a dict that matches the manifest's
        ``outputs`` schema (apart from ``provenance``, which :meth:`run` adds)."""

    # ------------------------------------------------------------------
    # Helpers used by :meth:`run`.
    # ------------------------------------------------------------------

    def _validate_inputs(self, inputs: dict[str, Any]) -> None:
        _validate_against_schema(inputs, self._manifest.inputs, what="input")

    def _validate_outputs(self, outputs: dict[str, Any]) -> None:
        _validate_against_schema(outputs, self._manifest.outputs, what="output")

    def _error_envelope(
        self,
        *,
        error_code: str,
        error_category: str,
        human_message: str,
        retry_safe: bool,
        suggested_remediation: str,
    ) -> dict[str, Any]:
        return {
            "error": {
                "error_code": error_code,
                "error_category": error_category,
                "human_message": human_message,
                "retry_safe": retry_safe,
                "suggested_remediation": suggested_remediation,
                "skill_id": self.id,
                "skill_version": self._manifest.version,
            }
        }

    def _remediation_for(self, exc: LibError) -> str:
        """Map a :class:`LibError` to a short remediation string.

        Subclasses with domain-specific remediations can override this.
        """
        remediations = {
            "missing_api_key": (
                "Set ANTHROPIC_API_KEY in the environment, or prime the LLM "
                "cache for the exact input."
            ),
            "rate_limit_exceeded": (
                "Slow down or batch calls; EDGAR fair-access budget is 10 req/s."
            ),
            "hash_mismatch": (
                "A stored artifact's hash no longer matches the recorded value — "
                "re-ingest the upstream doc; do NOT proceed with the mismatched copy."
            ),
        }
        return remediations.get(
            exc.error_code,
            "Inspect the error_code and human_message, then consult the skill manifest.",
        )


# ---------------------------------------------------------------------------
# JSON-Schema validation — lazy jsonschema import.
# ---------------------------------------------------------------------------


class _InputSchemaError(Exception):
    """Raised when an input or output dict fails JSON-Schema validation.

    Kept internal: :meth:`Skill.run` catches and reformats into the public
    error envelope.
    """


def _validate_against_schema(
    payload: dict[str, Any], schema: dict[str, Any], *, what: str
) -> None:
    """Validate ``payload`` against ``schema`` using ``jsonschema``.

    We import jsonschema lazily so the ``mvp.skills`` package stays
    import-cheap for callers who only want the manifest schema (e.g.
    tools generating the MCP catalog).

    Raises
    ------
    _InputSchemaError
        With a compact human-readable summary of the first failure.
    """
    try:
        import jsonschema  # type: ignore[import-untyped]
    except ModuleNotFoundError as exc:
        # jsonschema is an OPTIONAL, indirect dependency of pydantic's
        # legacy JSON Schema backend. If it isn't installed, fall back
        # to a minimal shape check — we still want the skill boundary
        # to reject the most common errors (wrong types, missing
        # required fields).
        _minimal_shape_check(payload, schema, what=what)
        return
    try:
        jsonschema.validate(instance=payload, schema=schema)
    except jsonschema.ValidationError as exc:
        raise _InputSchemaError(
            f"{what} schema violation at {'.'.join(str(p) for p in exc.absolute_path) or '$'}: "
            f"{exc.message}"
        ) from exc


def _minimal_shape_check(
    payload: dict[str, Any], schema: dict[str, Any], *, what: str
) -> None:
    """Fallback validator when jsonschema isn't installed.

    Checks: top-level type==object + required keys present + top-level
    properties match a narrow type ('string' / 'number' / 'integer' /
    'boolean'). Nested properties are NOT recursed — this path exists only
    so skills don't fail cold on test infra that lacks jsonschema.
    """
    if schema.get("type") not in (None, "object"):
        return
    required = schema.get("required", [])
    if not isinstance(required, list):
        required = []
    for key in required:
        if key not in payload:
            raise _InputSchemaError(
                f"{what} missing required field {key!r}"
            )
    props = schema.get("properties", {})
    if isinstance(props, dict):
        for key, sub in props.items():
            if key not in payload:
                continue
            expected = sub.get("type") if isinstance(sub, dict) else None
            val = payload[key]
            if expected == "string" and not isinstance(val, str):
                raise _InputSchemaError(f"{what} field {key!r} must be a string")
            if expected == "integer" and not isinstance(val, int):
                raise _InputSchemaError(f"{what} field {key!r} must be an integer")
            if expected == "number" and not isinstance(val, (int, float)):
                raise _InputSchemaError(f"{what} field {key!r} must be a number")
            if expected == "boolean" and not isinstance(val, bool):
                raise _InputSchemaError(f"{what} field {key!r} must be a boolean")


__all__ = ["Skill"]
