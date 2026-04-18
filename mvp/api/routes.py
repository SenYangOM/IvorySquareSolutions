"""Thin route handlers for the FastAPI stub.

Every handler follows the same pattern:

1. Look up the requested resource via the shared skill/ingestion modules.
2. Validate the payload via the manifest's JSON Schema (done by the
   skill's :meth:`run` boundary — we do not duplicate validation here).
3. Dispatch to the registry / eval runner / ingestion module.
4. Format the output. Errors never escape: the skill boundary either
   returns a typed error envelope, or the exception handler in
   :mod:`mvp.api.server` catches a raw exception and routes through
   :mod:`mvp.api.error_envelope`.

Per Operating Principle P3 the CLI and API call the same registry
singleton with the same input shape; the parity test in
``tests/integration/test_cli_api_parity.py`` asserts byte-identical
outputs modulo the three timestamp/id fields
(``provenance.run_at``, ``provenance.run_id``, ``provenance.build_id``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from fastapi.responses import JSONResponse

from mvp.lib.citation import Citation
from mvp.skills.manifest_schema import SkillManifest
from mvp.skills.registry import Registry, default_registry

from .error_envelope import (
    build_envelope,
    from_skill_envelope,
    input_validation_envelope,
    not_found_envelope,
)


_MVP_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Catalog endpoints.
# ---------------------------------------------------------------------------


def list_skills_response(registry: Registry) -> list[dict[str, Any]]:
    """Return the skill catalogue as a list — same content as ``mvp skills list``."""
    out: list[dict[str, Any]] = []
    for manifest in registry.list_skills():
        out.append(_skill_summary(manifest))
    return out


def skill_manifest_response(
    registry: Registry, skill_id: str
) -> dict[str, Any] | JSONResponse:
    """Return the full manifest for ``skill_id`` as a JSON-serialisable dict."""
    try:
        skill = registry.get(skill_id)
    except KeyError:
        status, envelope = not_found_envelope(
            what="skill",
            key=skill_id,
            suggested_remediation=(
                "Use GET /v1/skills for the catalogue, then retry with a valid skill_id."
            ),
        )
        return JSONResponse(status_code=status, content=envelope)
    return skill.manifest.model_dump(mode="json")


def mcp_catalog_response(registry: Registry) -> dict[str, Any]:
    """Return a spec-compliant MCP tool catalog.

    The MCP public spec (2024/2025) calls for a ``{"tools": [...]}``
    envelope — each entry is the manifest's ``as_mcp_tool()`` projection
    (``{name, description, inputSchema}``). We include the tool count as
    a convenience for agents inspecting the catalogue.
    """
    tools = registry.mcp_catalog()
    return {"tools": tools, "count": len(tools)}


def openai_catalog_response(registry: Registry) -> dict[str, Any]:
    """Return the OpenAI tool-use catalog wrapped as ``{"tools": [...]}``."""
    tools = registry.openai_catalog()
    return {"tools": tools, "count": len(tools)}


# ---------------------------------------------------------------------------
# Skill invocation.
# ---------------------------------------------------------------------------


def run_skill_response(
    registry: Registry, skill_id: str, payload: dict[str, Any]
) -> dict[str, Any] | JSONResponse:
    """Dispatch ``skill_id`` with ``payload`` and return output or an envelope.

    The skill's :meth:`run` method handles input-schema validation, its
    own error handling, and provenance stamping. If the skill returns
    an ``{"error": {...}}`` block we translate to the public 5-field
    envelope with the appropriate HTTP status.
    """
    if not isinstance(payload, dict):
        status, envelope = input_validation_envelope(
            f"request body must be a JSON object, got {type(payload).__name__}"
        )
        return JSONResponse(status_code=status, content=envelope)

    try:
        skill = registry.get(skill_id)
    except KeyError:
        status, envelope = not_found_envelope(
            what="skill",
            key=skill_id,
            suggested_remediation=(
                "Use GET /v1/skills for the catalogue, then retry with a valid skill_id."
            ),
        )
        return JSONResponse(status_code=status, content=envelope)

    result = skill.run(payload)
    err_block = result.get("error") if isinstance(result, dict) else None
    if err_block is not None and isinstance(err_block, dict):
        status, envelope = from_skill_envelope(err_block)
        return JSONResponse(status_code=status, content=envelope)
    return result


# ---------------------------------------------------------------------------
# Citation resolution.
# ---------------------------------------------------------------------------


def resolve_citation_response(
    payload: dict[str, Any],
) -> dict[str, Any] | JSONResponse:
    """Resolve a ``(doc_id, locator)`` via the engine's citation validator."""
    # Avoid top-level import: citation_validator eagerly walks a few
    # filesystem paths, which is fine at server-warm but we keep things
    # lazy for fast cold-start on the catalogue-only routes.
    from mvp.engine.citation_validator import resolve_citation

    if not isinstance(payload, dict):
        status, envelope = input_validation_envelope(
            f"request body must be a JSON object, got {type(payload).__name__}"
        )
        return JSONResponse(status_code=status, content=envelope)
    doc_id = payload.get("doc_id")
    locator = payload.get("locator")
    excerpt_hash = payload.get("excerpt_hash")
    if not isinstance(doc_id, str) or not isinstance(locator, str):
        status, envelope = input_validation_envelope(
            "body must carry string 'doc_id' and string 'locator' fields"
        )
        return JSONResponse(status_code=status, content=envelope)
    from datetime import datetime, timezone

    try:
        citation = Citation(
            doc_id=doc_id,
            locator=locator,
            excerpt_hash=excerpt_hash
            if isinstance(excerpt_hash, str) and excerpt_hash
            else "0" * 64,
            retrieved_at=datetime.now(timezone.utc),
        )
    except Exception as exc:  # pydantic ValidationError
        status, envelope = input_validation_envelope(
            f"citation shape invalid: {exc}"
        )
        return JSONResponse(status_code=status, content=envelope)
    return resolve_citation(citation)


# ---------------------------------------------------------------------------
# Eval endpoints.
# ---------------------------------------------------------------------------


def eval_latest_response() -> dict[str, Any] | JSONResponse:
    """Return the most recent JSON report under ``mvp/eval/reports/`` or 404."""
    reports_dir = _MVP_ROOT / "eval" / "reports"
    if not reports_dir.is_dir():
        status, envelope = not_found_envelope(
            what="eval_report",
            key="latest",
            suggested_remediation=(
                "Run POST /v1/eval/run or 'mvp eval' to generate a report "
                "before querying the latest one."
            ),
        )
        return JSONResponse(status_code=status, content=envelope)

    candidates = sorted(reports_dir.glob("*.json"))
    if not candidates:
        status, envelope = not_found_envelope(
            what="eval_report",
            key="latest",
            suggested_remediation=(
                "Run POST /v1/eval/run or 'mvp eval' to generate a report "
                "before querying the latest one."
            ),
        )
        return JSONResponse(status_code=status, content=envelope)

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    import json

    try:
        return json.loads(latest.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        status, envelope = input_validation_envelope(
            f"stored eval report at {latest.name} is not valid JSON: {exc}"
        )
        return JSONResponse(status_code=status, content=envelope)


def eval_run_response() -> dict[str, Any]:
    """Run the eval harness and return the ``EvalReport`` as JSON."""
    from mvp.eval.runner import run_eval

    report = run_eval()
    return report.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Health.
# ---------------------------------------------------------------------------


def health_response() -> dict[str, Any]:
    """Return a small readiness payload. Never raises — falls back to defaults."""
    import contextlib
    import json

    build_id = "unknown"
    phase: int | str = "unknown"
    state_path = _MVP_ROOT / "BUILD_STATE.json"
    if state_path.is_file():
        # A corrupted or unreadable BUILD_STATE.json degrades the healthz
        # payload to "unknown" rather than 500ing — the readiness contract
        # says this endpoint never raises. contextlib.suppress is the
        # documented no-op for that degrade path.
        with contextlib.suppress(OSError, json.JSONDecodeError):
            state = json.loads(state_path.read_text(encoding="utf-8"))
            build_id = f"{state.get('started_at', 'unknown')}/phase-{state.get('current_phase', '?')}"
            phase = state.get("current_phase", "unknown")
    return {"status": "ok", "build_id": build_id, "phase": phase}


# ---------------------------------------------------------------------------
# Internal helpers.
# ---------------------------------------------------------------------------


def _skill_summary(manifest: SkillManifest) -> dict[str, Any]:
    """One-entry skill summary — matches ``mvp skills list`` content."""
    return {
        "skill_id": manifest.skill_id,
        "version": manifest.version,
        "layer": manifest.layer,
        "status": manifest.status,
        "maintainer_persona": manifest.maintainer_persona,
        "description_for_llm": manifest.description_for_llm,
    }


__all__ = [
    "eval_latest_response",
    "eval_run_response",
    "health_response",
    "list_skills_response",
    "mcp_catalog_response",
    "openai_catalog_response",
    "resolve_citation_response",
    "run_skill_response",
    "skill_manifest_response",
]
