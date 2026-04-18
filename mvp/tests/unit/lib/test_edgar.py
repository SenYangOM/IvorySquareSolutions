"""Unit tests for mvp.lib.edgar (no live network — httpx.MockTransport only)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
import pytest

from mvp.lib.edgar import (
    DEFAULT_USER_AGENT,
    MAX_RPS,
    EdgarClient,
    _TokenBucket,
    normalize_cik,
)
from mvp.lib.errors import EdgarHttpError, InputValidationError, RateLimitExceeded


# --- normalize_cik --------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("320193", "0000320193"),
        ("0000320193", "0000320193"),
        (320193, "0000320193"),
        ("CIK0000320193", "0000320193"),
        ("CIK320193", "0000320193"),
    ],
)
def test_normalize_cik_accepts(raw: Any, expected: str) -> None:
    assert normalize_cik(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "abc", "12345678901", -5, 0, None, 1.5])
def test_normalize_cik_rejects(raw: Any) -> None:
    with pytest.raises(InputValidationError):
        normalize_cik(raw)


# --- _TokenBucket ---------------------------------------------------------


def test_token_bucket_allows_under_limit() -> None:
    b = _TokenBucket(rps=10)
    now = 1000.0
    for i in range(10):
        b.record(now=now + i * 0.05)  # 10 requests over 0.5s — fine


def test_token_bucket_raises_over_limit() -> None:
    b = _TokenBucket(rps=10)
    now = 1000.0
    for i in range(10):
        b.record(now=now + i * 0.01)  # 10 requests in 0.1s — at limit
    with pytest.raises(RateLimitExceeded):
        b.record(now=now + 0.1)  # 11th within the window


def test_token_bucket_window_rolls_off() -> None:
    b = _TokenBucket(rps=10)
    for i in range(10):
        b.record(now=1000.0 + i * 0.01)
    # 1.1s later, all old stamps are outside the window.
    b.record(now=1001.2)


# --- EdgarClient via MockTransport ---------------------------------------


def _mk_client(handler: Any, **kw: Any) -> EdgarClient:
    transport = httpx.MockTransport(handler)
    return EdgarClient(transport=transport, **kw)


def test_fetch_submissions_sets_user_agent() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"cik": "320193", "filings": {"recent": {}}})

    with _mk_client(handler) as client:
        payload = client.fetch_submissions("320193")

    assert captured["user_agent"] == DEFAULT_USER_AGENT
    assert payload["cik"] == "320193"


def test_user_agent_override_for_tests() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["user_agent"] = request.headers.get("user-agent", "")
        return httpx.Response(200, json={"ok": True})

    with _mk_client(handler, user_agent="test/1.0") as client:
        client.fetch_submissions("320193")

    assert captured["user_agent"] == "test/1.0"


def test_empty_user_agent_rejected() -> None:
    with pytest.raises(InputValidationError):
        EdgarClient(user_agent="")


def test_fetch_filing_index_url_shape() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json={"directory": {"item": []}})

    with _mk_client(handler) as client:
        client.fetch_filing_index("320193", "0000320193-23-000106")

    assert (
        captured[0]
        == "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/index.json"
    )


def test_fetch_filing_index_accepts_nodash() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"directory": {"item": []}})

    with _mk_client(handler) as client:
        client.fetch_filing_index("320193", "000032019323000106")


@pytest.mark.parametrize("accession", ["bad", "1234567890-12-3456", "", "    "])
def test_fetch_filing_index_rejects_bad_accession(accession: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    with _mk_client(handler) as client:
        with pytest.raises(InputValidationError):
            client.fetch_filing_index("320193", accession)


def test_fetch_document_rejects_non_sec_host() -> None:
    def handler(request: httpx.Request) -> httpx.Response:  # pragma: no cover
        return httpx.Response(200, content=b"x")

    with _mk_client(handler) as client:
        with pytest.raises(InputValidationError):
            client.fetch_document("https://example.com/x")


def test_fetch_document_accepts_sec() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html>x</html>")

    with _mk_client(handler) as client:
        body = client.fetch_document(
            "https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm"
        )
    assert body == b"<html>x</html>"


def test_retry_on_429_then_succeed(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, json={"error": "slow down"})
        return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with _mk_client(handler) as client:
        payload = client.fetch_submissions("320193")
    assert payload == {"ok": True}
    assert len(calls) == 2


def test_retry_exhausted_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with _mk_client(handler) as client:
        with pytest.raises(EdgarHttpError) as exc:
            client.fetch_submissions("320193")
    assert exc.value.status_code == 503


def test_non_retryable_4xx_raises_immediately(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(404, json={"error": "not found"})

    monkeypatch.setattr(time, "sleep", lambda _s: None)
    with _mk_client(handler) as client:
        with pytest.raises(EdgarHttpError) as exc:
            client.fetch_submissions("320193")
    assert exc.value.status_code == 404
    assert len(calls) == 1  # no retry on 404


def test_rate_limit_propagates() -> None:
    # Fire 11 sub-second requests and verify the bucket raises.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    with _mk_client(handler) as client:
        for _ in range(MAX_RPS):
            client.fetch_submissions("320193")
        # The 11th in-window call must raise RateLimitExceeded.
        with pytest.raises(RateLimitExceeded):
            client.fetch_submissions("320193")


def test_non_json_response_raises_edgarhttperror() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"<html/>", headers={"Content-Type": "text/html"})

    with _mk_client(handler) as client:
        with pytest.raises(EdgarHttpError):
            client.fetch_submissions("320193")


def test_json_root_not_object_raises() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"[1,2,3]", headers={"Content-Type": "application/json"})

    with _mk_client(handler) as client:
        with pytest.raises(EdgarHttpError):
            client.fetch_submissions("320193")


def test_fetch_company_tickers() -> None:
    captured: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(str(request.url))
        return httpx.Response(200, json={"0": {"cik_str": 320193, "ticker": "AAPL"}})

    with _mk_client(handler) as client:
        payload = client.fetch_company_tickers()

    assert captured[0] == "https://www.sec.gov/files/company_tickers.json"
    assert payload["0"]["ticker"] == "AAPL"
