"""L5 FastAPI stub — the localhost-only API surface for the MVP.

Spec: ``mvp_build_goal.md`` §12 Phase 6, ``success_criteria.md`` §2, §7
(L5 row), §12 (agent-accessibility gate).

All routes share the single skill registry that :mod:`mvp.cli.main` uses
(``mvp.skills.registry.default_registry``). Every error path — whether a
typed :class:`mvp.lib.errors.LibError`, an input-validation failure, or
an uncaught exception — flows through one of the exception handlers
registered below and returns the 5-field public envelope from
:mod:`mvp.api.error_envelope`. No raw stack traces or internal paths ever
reach the client.

Production hardening (auth, rate limiting, TLS, CORS) is out of scope
per ``success_criteria.md`` §9 "API security beyond a localhost stub —
Stage 2 production is post-MVP." The app binds localhost when served via
``uvicorn mvp.api:app`` with default args.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills.registry import default_registry

from . import routes
from .error_envelope import (
    build_envelope,
    envelope_from_lib_error,
    generic_internal_envelope,
    input_validation_envelope,
)


logger = logging.getLogger("mvp.api")


# ---------------------------------------------------------------------------
# App factory.
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Construct the FastAPI application and register routes + handlers.

    Kept as a factory so tests can mount a fresh app if they need to
    inject a distinct registry; by default every app instance uses the
    module-level :func:`default_registry` singleton so CLI and API
    traverse the identical code path.
    """
    app = FastAPI(
        title="MVP skills API",
        version="0.6.0",
        description=(
            "Localhost stub exposing the MVP skill registry. "
            "The CLI (`mvp run ...`) and this API call the same registry "
            "and produce byte-identical outputs modulo timestamp fields."
        ),
    )

    # ------------------------------------------------------------------
    # Catalog routes.
    # ------------------------------------------------------------------

    @app.get("/v1/skills")
    def _list_skills() -> list[dict[str, Any]]:
        return routes.list_skills_response(default_registry())

    @app.get("/v1/skills/{skill_id}")
    def _get_skill(skill_id: str) -> Any:
        return routes.skill_manifest_response(default_registry(), skill_id)

    @app.get("/mcp/tools")
    def _mcp_catalog() -> dict[str, Any]:
        return routes.mcp_catalog_response(default_registry())

    @app.get("/openai/tools")
    def _openai_catalog() -> dict[str, Any]:
        return routes.openai_catalog_response(default_registry())

    # ------------------------------------------------------------------
    # Skill dispatch.
    # ------------------------------------------------------------------

    @app.post("/v1/skills/{skill_id}")
    async def _run_skill(skill_id: str, request: Request) -> Any:
        try:
            payload = await request.json()
        except Exception as exc:  # body is not JSON-decodable
            status, envelope = input_validation_envelope(
                f"request body is not valid JSON: {exc}"
            )
            return JSONResponse(status_code=status, content=envelope)
        return routes.run_skill_response(default_registry(), skill_id, payload)

    # ------------------------------------------------------------------
    # Citation resolution.
    # ------------------------------------------------------------------

    @app.post("/v1/resolve_citation")
    async def _resolve_citation(request: Request) -> Any:
        try:
            payload = await request.json()
        except Exception as exc:
            status, envelope = input_validation_envelope(
                f"request body is not valid JSON: {exc}"
            )
            return JSONResponse(status_code=status, content=envelope)
        return routes.resolve_citation_response(payload)

    # ------------------------------------------------------------------
    # Eval endpoints. POST /v1/eval/run is idempotent but POST signals
    # "may take non-trivial time + spawn background work" to the caller;
    # GET would suggest cacheability which doesn't match.
    # ------------------------------------------------------------------

    @app.get("/v1/eval/latest")
    def _eval_latest() -> Any:
        return routes.eval_latest_response()

    @app.post("/v1/eval/run")
    def _eval_run() -> Any:
        # POST is correct even though this is read-only w.r.t. domain
        # state: re-running evaluation is non-idempotent in timing and
        # produces a new run_id per call.
        return routes.eval_run_response()

    # ------------------------------------------------------------------
    # Health.
    # ------------------------------------------------------------------

    @app.get("/healthz")
    def _healthz() -> dict[str, Any]:
        return routes.health_response()

    # ------------------------------------------------------------------
    # Exception handlers.
    # ------------------------------------------------------------------

    @app.exception_handler(LibError)
    async def _lib_error_handler(_request: Request, exc: LibError) -> JSONResponse:
        status, envelope = envelope_from_lib_error(exc)
        return JSONResponse(status_code=status, content=envelope)

    @app.exception_handler(KeyError)
    async def _key_error_handler(_request: Request, exc: KeyError) -> JSONResponse:
        # KeyError from registry.get() means "no skill registered" — map to 404.
        # We include the exception's str in the message so agents can pattern match.
        msg = str(exc).strip("'\"")
        envelope = build_envelope(
            error_code="skill_not_found",
            error_category=ErrorCategory.INPUT_VALIDATION.value,
            human_message=f"resource not found: {msg}",
            retry_safe=False,
            suggested_remediation=(
                "Use GET /v1/skills for the catalogue, then retry with a valid id."
            ),
        )
        return JSONResponse(status_code=404, content=envelope)

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errs = exc.errors()
        # RequestValidationError.errors() returns a list of dicts; we
        # extract the first one for the human_message for compactness.
        detail = "; ".join(
            f"{'.'.join(str(p) for p in e.get('loc', []))}: {e.get('msg', '')}"
            for e in errs[:5]
        ) or "request validation failed"
        status, envelope = input_validation_envelope(detail)
        return JSONResponse(status_code=status, content=envelope)

    @app.exception_handler(Exception)
    async def _catch_all_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Log with full traceback server-side; return a sanitised envelope.
        logger.exception("unhandled exception in API route: %s", exc)
        status, envelope = generic_internal_envelope(exc)
        return JSONResponse(status_code=status, content=envelope)

    return app


# Module-level singleton for `uvicorn mvp.api:app`.
app = create_app()


__all__ = ["app", "create_app"]
