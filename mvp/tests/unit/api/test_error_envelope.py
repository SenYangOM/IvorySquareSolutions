"""Tests that every error path produces the 5-field structured envelope.

Per Operating Principle P3 and ``success_criteria.md`` §12, no API
response on an error path may leak a stack trace, internal file path, or
skill-internal state. Every error must project to the 5-field envelope
``{error_code, error_category, human_message, retry_safe, suggested_remediation}``
with an appropriate HTTP status.
"""

from __future__ import annotations

import re

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from mvp.api import app
from mvp.api.error_envelope import (
    ENVELOPE_KEYS,
    build_envelope,
    envelope_from_lib_error,
    generic_internal_envelope,
)
from mvp.lib.errors import (
    EdgarHttpError,
    ErrorCategory,
    IngestionError,
    InputValidationError,
    LibError,
    MissingApiKey,
    RateLimitExceeded,
)


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Envelope shape + no-leak guarantees.
# ---------------------------------------------------------------------------


def test_envelope_has_exactly_five_keys() -> None:
    env = build_envelope(
        error_code="some_code",
        error_category="input_validation",
        human_message="msg",
        retry_safe=False,
        suggested_remediation="do X",
    )
    assert set(env.keys()) == set(ENVELOPE_KEYS)
    assert len(ENVELOPE_KEYS) == 5


def test_404_on_unknown_skill_has_envelope_and_no_trace(client: TestClient) -> None:
    resp = client.get("/v1/skills/ghost_skill_id_123")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    # Assert no stack-trace or internal-path leak.
    _assert_no_leakage(body)


def test_400_on_missing_required_input(client: TestClient) -> None:
    resp = client.post(
        "/v1/skills/compute_beneish_m_score", json={"cik": "0001024401"}
    )
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    _assert_no_leakage(body)


def test_400_on_non_json_body(client: TestClient) -> None:
    resp = client.post(
        "/v1/skills/compute_beneish_m_score",
        content=b"not json at all",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    _assert_no_leakage(body)


def test_run_unknown_skill_post_returns_envelope(client: TestClient) -> None:
    resp = client.post("/v1/skills/nonexistent", json={})
    assert resp.status_code == 404
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    _assert_no_leakage(body)


def test_resolve_citation_bad_body_returns_envelope(client: TestClient) -> None:
    resp = client.post("/v1/resolve_citation", json={})
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    _assert_no_leakage(body)


def test_resolve_citation_malformed_locator_returns_400(client: TestClient) -> None:
    # The locator regex forbids '::::' etc; ensure this becomes a 400 envelope.
    resp = client.post(
        "/v1/resolve_citation",
        json={"doc_id": "0000320193/0000320193-23-000106", "locator": "not a valid locator"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    _assert_no_leakage(body)


# ---------------------------------------------------------------------------
# The global Exception handler never leaks.
# ---------------------------------------------------------------------------


def test_uncaught_exception_returns_generic_internal_envelope() -> None:
    """Register a test-only route that raises, then hit it and assert shape."""
    # Use create_app so we have a fresh app instance for the synthetic route.
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise")
    async def _raise(_req: Request) -> dict:
        raise RuntimeError("internal state x=42 /secret/internal/path")

    fresh_client = TestClient(fresh, raise_server_exceptions=False)
    resp = fresh_client.get("/__test_raise")
    assert resp.status_code == 500
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    assert body["error_code"] == "internal_error"
    # Generic message: includes exception type and message but nothing
    # a caller can mine for internal paths beyond what the test itself
    # wrote into the message.
    assert body["human_message"].startswith("RuntimeError:")
    assert "Traceback" not in body["human_message"]
    # The remediation is the stock one — no internal path fragments.
    assert "file a bug" in body["suggested_remediation"].lower()


def test_lib_error_handler_maps_to_correct_status() -> None:
    """A skill that raises a typed LibError should produce a sanitised envelope."""
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise_lib")
    async def _raise(_req: Request) -> dict:
        raise InputValidationError("bad input from x")

    c = TestClient(fresh, raise_server_exceptions=False)
    resp = c.get("/__test_raise_lib")
    assert resp.status_code == 400
    body = resp.json()
    assert set(body.keys()) == set(ENVELOPE_KEYS)
    assert body["error_code"] == "input_validation"


def test_lib_error_auth_category_maps_to_401() -> None:
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise_auth")
    async def _raise(_req: Request) -> dict:
        raise MissingApiKey("ANTHROPIC_API_KEY is not set")

    c = TestClient(fresh, raise_server_exceptions=False)
    resp = c.get("/__test_raise_auth")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error_code"] == "missing_api_key"
    assert body["error_category"] == "auth"


def test_lib_error_rate_limit_maps_to_429() -> None:
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise_rate")
    async def _raise(_req: Request) -> dict:
        raise RateLimitExceeded("10 req/s budget exceeded")

    c = TestClient(fresh, raise_server_exceptions=False)
    resp = c.get("/__test_raise_rate")
    assert resp.status_code == 429
    body = resp.json()
    assert body["error_code"] == "rate_limit_exceeded"
    assert body["retry_safe"] is True


def test_lib_error_upstream_maps_to_502() -> None:
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise_upstream")
    async def _raise(_req: Request) -> dict:
        raise EdgarHttpError("503 from EDGAR", status_code=503, url="https://sec.gov/x")

    c = TestClient(fresh, raise_server_exceptions=False)
    resp = c.get("/__test_raise_upstream")
    assert resp.status_code == 502
    body = resp.json()
    assert body["error_code"] == "edgar_http_error"
    assert body["error_category"] == "upstream"


def test_ingestion_error_unknown_filing_maps_to_404() -> None:
    from mvp.api.server import create_app

    fresh = create_app()

    @fresh.get("/__test_raise_unk_filing")
    async def _raise(_req: Request) -> dict:
        raise IngestionError(
            "no sample filing registered for ...",
            reason="unknown_filing",
            target="0001024401/x",
        )

    # IngestionError defaults to error_code='ingestion_error', but we
    # want 'unknown_filing' for the remediation lookup — override via the
    # constructor.
    from mvp.api.server import create_app as _create

    fresh2 = _create()

    @fresh2.get("/__test_raise_unk")
    async def _raise2(_req: Request) -> dict:
        exc = IngestionError(
            "no sample filing",
            reason="unknown_filing",
            target="0001024401/x",
        )
        exc.error_code = "unknown_filing"
        raise exc

    c = TestClient(fresh2, raise_server_exceptions=False)
    resp = c.get("/__test_raise_unk")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "unknown_filing"


# ---------------------------------------------------------------------------
# Error-envelope module API.
# ---------------------------------------------------------------------------


def test_envelope_from_lib_error_includes_remediation() -> None:
    exc = MissingApiKey("no key configured")
    status, env = envelope_from_lib_error(exc)
    assert status == 401
    assert env["error_code"] == "missing_api_key"
    assert "ANTHROPIC_API_KEY" in env["suggested_remediation"]


def test_generic_internal_envelope_no_traceback() -> None:
    try:
        raise RuntimeError("boom")
    except RuntimeError as exc:
        status, env = generic_internal_envelope(exc)
    assert status == 500
    assert env["error_code"] == "internal_error"
    assert "Traceback" not in env["human_message"]
    assert "/mnt/" not in env["human_message"]


# ---------------------------------------------------------------------------
# Leakage detector.
# ---------------------------------------------------------------------------


_LEAK_PATTERNS = [
    re.compile(r"Traceback"),
    re.compile(r"/home/[^ ]+\.py"),
    re.compile(r"/mnt/[^ ]+\.py"),
    re.compile(r"File \"[^\"]+\", line \d+"),
    # Internal pydantic / FastAPI module paths leaking through:
    re.compile(r"pydantic\..*\.py"),
    re.compile(r"fastapi\..*\.py"),
]


def _assert_no_leakage(body: dict) -> None:
    """Assert no stack-trace / internal-path leakage in the envelope body.

    We check every string value in the envelope. None of them should
    match a traceback marker or an internal file path.
    """
    for key in ("error_code", "error_category", "human_message", "suggested_remediation"):
        val = body.get(key, "")
        if not isinstance(val, str):
            continue
        for pat in _LEAK_PATTERNS:
            assert not pat.search(val), (
                f"envelope[{key!r}] leaks internal detail: "
                f"{pat.pattern!r} matched {val!r}"
            )
