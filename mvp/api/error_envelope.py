"""Structured error-envelope mapping for the L5 FastAPI surface.

Every error path — validation failures, unknown resources, registry
``KeyError``, typed :class:`mvp.lib.errors.LibError` subclasses, and
truly-unexpected exceptions — flows through :func:`build_envelope` and is
returned to the agent caller as the 5-field public envelope
``{error_code, error_category, human_message, retry_safe, suggested_remediation}``.

Per Operating Principle P3 (``mvp_build_goal.md`` §0), no error path may
leak a Python stack trace or internal filesystem path to the caller. The
FastAPI exception handler wired in :mod:`mvp.api.server` catches every
exception at a single seam and dispatches here.
"""

from __future__ import annotations

from typing import Any

from mvp.lib.errors import ErrorCategory, LibError


# Canonical 5-field envelope keys. Keep the set closed — adding a key is
# a contract change.
ENVELOPE_KEYS = (
    "error_code",
    "error_category",
    "human_message",
    "retry_safe",
    "suggested_remediation",
)


def build_envelope(
    *,
    error_code: str,
    error_category: str,
    human_message: str,
    retry_safe: bool,
    suggested_remediation: str,
) -> dict[str, Any]:
    """Construct the public error envelope, exactly 5 top-level fields.

    The envelope is wrapped under the ``error`` key by callers that need
    to distinguish an error response from a success response (the skill
    layer uses ``{"error": {...}}``). The API surface returns the
    envelope as the response body verbatim; the HTTP status code carries
    the success/error signal so clients don't need to sniff the body.
    """
    return {
        "error_code": error_code,
        "error_category": error_category,
        "human_message": human_message,
        "retry_safe": retry_safe,
        "suggested_remediation": suggested_remediation,
    }


def envelope_from_lib_error(exc: LibError) -> tuple[int, dict[str, Any]]:
    """Map a :class:`LibError` to ``(http_status, envelope)``.

    - Input-validation errors → 400.
    - Not-found / unknown-resource errors → 404.
    - Auth (missing API key) → 401.
    - Rate-limit → 429.
    - Upstream / parse / IO (transient or user-fixable) → 502 / 422 / 400.
    - Everything else → 500 with a generic ``internal_error`` payload
      (the original ``error_code`` is still surfaced — just the HTTP
      status is generic).
    """
    status = _status_for_category(exc.error_category, exc.error_code)
    envelope = build_envelope(
        error_code=exc.error_code,
        error_category=exc.error_category.value,
        human_message=exc.message,
        retry_safe=exc.retry_safe,
        suggested_remediation=_remediation_for(exc),
    )
    return status, envelope


def generic_internal_envelope(exc: BaseException) -> tuple[int, dict[str, Any]]:
    """Map an uncaught Python exception to ``(500, internal_error envelope)``.

    This is the global catch-all. The ``human_message`` carries the
    exception's type + message (for the agent caller to pattern-match on)
    but never a traceback or internal file path. The full traceback is
    expected to have been logged by the server's exception handler
    before this function is reached.
    """
    return 500, build_envelope(
        error_code="internal_error",
        error_category=ErrorCategory.INTERNAL.value,
        human_message=f"{type(exc).__name__}: {exc}",
        retry_safe=False,
        suggested_remediation=(
            "Unexpected internal error. If the failure persists with "
            "known-good inputs, file a bug against the API."
        ),
    )


def input_validation_envelope(human_message: str) -> tuple[int, dict[str, Any]]:
    """Produce a ``(400, input_validation envelope)`` for caller-side bad input."""
    return 400, build_envelope(
        error_code="input_validation",
        error_category=ErrorCategory.INPUT_VALIDATION.value,
        human_message=human_message,
        retry_safe=False,
        suggested_remediation=(
            "Adjust the request payload to match the skill's JSON Schema "
            "(see GET /v1/skills/{skill_id})."
        ),
    )


def not_found_envelope(
    *, what: str, key: str, suggested_remediation: str | None = None
) -> tuple[int, dict[str, Any]]:
    """Produce a ``(404, not_found envelope)`` for unknown resources."""
    return 404, build_envelope(
        error_code=f"{what}_not_found",
        error_category=ErrorCategory.INPUT_VALIDATION.value,
        human_message=f"no {what} found for {key!r}",
        retry_safe=False,
        suggested_remediation=(
            suggested_remediation
            or f"List known {what}s via the catalog endpoint, then retry with a valid key."
        ),
    )


def from_skill_envelope(
    err_block: dict[str, Any],
) -> tuple[int, dict[str, Any]]:
    """Convert a skill-returned ``{"error": {...}}`` block into HTTP envelope.

    The skill base class (``mvp.skills._base.Skill.run``) already emits a
    canonical envelope; this function maps the skill's ``error_code`` /
    ``error_category`` to the right HTTP status and projects down to the
    5-field public envelope (the skill's envelope additionally carries
    ``skill_id`` + ``skill_version`` which are dropped here — they're
    already visible in the URL path).
    """
    code = str(err_block.get("error_code", "internal_error"))
    category = str(err_block.get("error_category", ErrorCategory.INTERNAL.value))
    status = _status_for_category_str(category, code)
    envelope = build_envelope(
        error_code=code,
        error_category=category,
        human_message=str(err_block.get("human_message", "")),
        retry_safe=bool(err_block.get("retry_safe", False)),
        suggested_remediation=str(err_block.get("suggested_remediation", "")),
    )
    return status, envelope


# ---------------------------------------------------------------------------
# Status-code mapping.
# ---------------------------------------------------------------------------


_CATEGORY_STATUS: dict[ErrorCategory, int] = {
    ErrorCategory.INPUT_VALIDATION: 400,
    ErrorCategory.PARSE: 422,
    ErrorCategory.AUTH: 401,
    ErrorCategory.RATE_LIMIT: 429,
    ErrorCategory.UPSTREAM: 502,
    ErrorCategory.NETWORK: 502,
    ErrorCategory.IO: 500,
    ErrorCategory.CACHE: 500,
    ErrorCategory.INTERNAL: 500,
}


def _status_for_category(category: ErrorCategory, error_code: str) -> int:
    # A handful of codes override their category's default.
    if error_code in {
        "unknown_filing",
        "unknown_paper",
        "skill_not_found",
        "eval_report_not_found",
    }:
        return 404
    return _CATEGORY_STATUS.get(category, 500)


def _status_for_category_str(category_value: str, error_code: str) -> int:
    try:
        category = ErrorCategory(category_value)
    except ValueError:
        return 500
    return _status_for_category(category, error_code)


# ---------------------------------------------------------------------------
# Remediation strings — identical set as ``mvp.skills._base.Skill._remediation_for``.
# Keeping these co-located so the CLI path and the API path produce the
# same remediation text for the same typed error.
# ---------------------------------------------------------------------------


_REMEDIATIONS: dict[str, str] = {
    "missing_api_key": (
        "Set ANTHROPIC_API_KEY in the environment, or prime the LLM cache "
        "for the exact input."
    ),
    "rate_limit_exceeded": (
        "Slow down or batch calls; EDGAR fair-access budget is 10 req/s."
    ),
    "hash_mismatch": (
        "A stored artifact's hash no longer matches the recorded value — "
        "re-ingest the upstream doc; do NOT proceed with the mismatched copy."
    ),
    "unknown_filing": (
        "The MVP ships a fixed 10-filing sample. Use GET /v1/skills (or the "
        "CLI 'mvp skills list') to see the supported CIK/year pairs."
    ),
    "unknown_paper": (
        "The MVP ships two sample papers ('beneish_1999', 'altman_1968'). "
        "Pass one of those ids to the ingest endpoint."
    ),
    "store_error": (
        "Check that the requested filing is in the MVP sample set and that "
        "the filing has been ingested (mvp ingest filings)."
    ),
    "ingestion_error": (
        "Inspect the error target (CIK/accession or paper_id) and retry "
        "ingestion; if a hash_mismatch is reported, do NOT silently repair."
    ),
}


def _remediation_for(exc: LibError) -> str:
    return _REMEDIATIONS.get(
        exc.error_code,
        "Inspect the error_code and human_message, then consult the skill manifest.",
    )


__all__ = [
    "ENVELOPE_KEYS",
    "build_envelope",
    "envelope_from_lib_error",
    "from_skill_envelope",
    "generic_internal_envelope",
    "input_validation_envelope",
    "not_found_envelope",
]
