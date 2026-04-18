"""Structured exception hierarchy for ``mvp.lib``.

Per Operating Principle P3 (``mvp_build_goal.md`` §0), every error must be a
typed object so the skill layer can catch it at its boundary and reformat
into the public error envelope
``{error_code, error_category, human_message, retry_safe, suggested_remediation}``.

All ``lib``-level exceptions derive from :class:`LibError`, which carries the
three attributes the skill boundary needs: ``error_code`` (stable,
machine-readable), ``error_category`` (one of the enum values below), and
``retry_safe`` (whether the caller may safely retry the same inputs).

Subclasses set class-level defaults; callers can override by passing keyword
arguments to the constructor when context demands it.
"""

from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    """Top-level error buckets surfaced by ``mvp.lib`` functions.

    The skill layer maps these to the public ``error_category`` field in the
    agent-facing error envelope. Keep the set small and stable — adding a
    category is a contract change.
    """

    INPUT_VALIDATION = "input_validation"
    IO = "io"
    NETWORK = "network"
    RATE_LIMIT = "rate_limit"
    UPSTREAM = "upstream"
    AUTH = "auth"
    PARSE = "parse"
    CACHE = "cache"
    INTERNAL = "internal"


class LibError(Exception):
    """Base class for all ``mvp.lib`` errors.

    Attributes
    ----------
    error_code:
        Stable, machine-readable identifier (snake_case). Agents pattern-match
        on this. Never change an existing code without a version bump.
    error_category:
        One of :class:`ErrorCategory`. Coarser than ``error_code``; safe for
        UI grouping.
    retry_safe:
        ``True`` if retrying the same inputs can plausibly succeed (e.g.
        transient network). ``False`` for deterministic failures (bad input,
        auth, parse).
    """

    error_code: str = "lib_error"
    error_category: ErrorCategory = ErrorCategory.INTERNAL
    retry_safe: bool = False

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        error_category: ErrorCategory | None = None,
        retry_safe: bool | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if error_code is not None:
            self.error_code = error_code
        if error_category is not None:
            self.error_category = error_category
        if retry_safe is not None:
            self.retry_safe = retry_safe

    def to_dict(self) -> dict[str, object]:
        """Serialise to a flat dict the skill boundary can embed."""
        return {
            "error_code": self.error_code,
            "error_category": self.error_category.value,
            "retry_safe": self.retry_safe,
            "message": self.message,
        }


class InputValidationError(LibError):
    """The caller supplied an argument this function cannot use."""

    error_code = "input_validation"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class PdfReadError(LibError):
    """Failure reading or parsing a PDF document via ``mvp.lib.pdf_io``."""

    error_code = "pdf_read_error"
    error_category = ErrorCategory.PARSE
    retry_safe = False

    def __init__(self, message: str, *, path: str, reason: str) -> None:
        super().__init__(message)
        self.path = path
        self.reason = reason


class EdgarHttpError(LibError):
    """Non-retryable HTTP error from the SEC EDGAR client."""

    error_code = "edgar_http_error"
    error_category = ErrorCategory.UPSTREAM
    retry_safe = False

    def __init__(self, message: str, *, status_code: int, url: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class RateLimitExceeded(LibError):
    """Caller exceeded the EDGAR ≤10 req/s budget inside a single second."""

    error_code = "rate_limit_exceeded"
    error_category = ErrorCategory.RATE_LIMIT
    retry_safe = True


class MissingApiKey(LibError):
    """LLM call was requested without an API key and no cache hit was found."""

    error_code = "missing_api_key"
    error_category = ErrorCategory.AUTH
    retry_safe = False


class LlmCallError(LibError):
    """Anthropic SDK call failed after the allowed retries."""

    error_code = "llm_call_error"
    error_category = ErrorCategory.UPSTREAM
    retry_safe = True


class StoreError(LibError):
    """Failure reading from the L1 doc/fact store.

    Raised when a requested filing isn't on disk, when its cached sha256
    no longer matches the meta-recorded hash (silent corruption, which we
    never auto-repair per P2), or when a manual-extraction YAML fixture is
    malformed. Callers of :mod:`mvp.store.doc_store` and
    :mod:`mvp.store.facts_store` should catch this at the skill boundary
    and reformat to the public error envelope.
    """

    error_code = "store_error"
    error_category = ErrorCategory.IO
    retry_safe = False

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        filing_id: str,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.filing_id = filing_id


class IngestionError(LibError):
    """Failure during L0 ingestion (filings or papers).

    Raised for cases where the ingested artifact cannot be persisted
    reliably: unknown CIK/accession pair, missing primary document in the
    EDGAR filing index, hash-on-disk mismatches against a recorded
    ``meta.json`` (indicating silent corruption), or paper-mirror HTTP
    failures. Network transport failures surface as the lower-level
    :class:`EdgarHttpError` / :class:`RateLimitExceeded` instead.
    """

    error_code = "ingestion_error"
    error_category = ErrorCategory.IO
    retry_safe = False

    def __init__(
        self,
        message: str,
        *,
        reason: str,
        target: str,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.target = target


class PersonaCallError(LibError):
    """Failure invoking a persona via :class:`mvp.agents.persona_runtime.PersonaRuntime`.

    Raised for: missing persona YAML, malformed persona schema, and — most
    commonly in phase 3 tests — a request to invoke the persona without an
    Anthropic API key and without a cache hit. The three variants are
    discriminated by ``error_code`` so the skill boundary can map them to
    the public error envelope without sniffing the message string.

    Attributes
    ----------
    persona_id:
        The ``id`` field of the persona being invoked, or the requested
        identifier if loading failed.
    reason:
        Short machine-readable token (``missing_api_key``, ``persona_not_found``,
        ``persona_schema_invalid``, ``llm_call_failed``) used to discriminate
        constructor-time variants.
    """

    error_code = "persona_call_error"
    error_category = ErrorCategory.INTERNAL
    retry_safe = False

    def __init__(
        self,
        message: str,
        *,
        persona_id: str,
        reason: str,
        error_code: str | None = None,
        error_category: ErrorCategory | None = None,
        retry_safe: bool | None = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            error_category=error_category,
            retry_safe=retry_safe,
        )
        self.persona_id = persona_id
        self.reason = reason
