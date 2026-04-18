"""SEC EDGAR HTTP client.

Two non-negotiables (``mvp_build_goal.md`` §13 decision 2):

1. Every outbound request carries the hardcoded User-Agent
   ``"Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"`` — SEC fair-access
   rules require a declared identifier. Tests can override via a keyword
   argument but production code must not.
2. The client enforces ≤10 requests per second via a monotonic-clock sliding
   window. Under-the-limit requests are never blocked (no artificial
   sleeping); a request that would take us above 10/s in a given second
   raises :class:`RateLimitExceeded` so the caller can decide whether to
   back off. Silent sleeping past the limit would hide systemic bugs.

Retries on 429/5xx use exponential backoff (1s, 2s, 4s) for at most 3
attempts. Any other HTTP failure surfaces as an :class:`EdgarHttpError`
carrying the status code and URL.
"""

from __future__ import annotations

import time
from collections import deque
from typing import Any

import httpx

from .errors import EdgarHttpError, InputValidationError, RateLimitExceeded

DEFAULT_USER_AGENT = "Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"
MAX_RPS = 10
_BACKOFFS_S = (1.0, 2.0, 4.0)
_RETRYABLE = frozenset({429, 500, 502, 503, 504})

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
_COMPANY_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FILING_INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/index.json"


def normalize_cik(cik: str | int) -> str:
    """Return ``cik`` as a 10-digit zero-padded string.

    Accepts bare ints, numeric strings, and already-padded ``"0000320193"``.
    Raises :class:`InputValidationError` on garbage.
    """
    if isinstance(cik, int):
        if cik <= 0:
            raise InputValidationError(f"cik must be positive, got {cik}")
        s = str(cik)
    elif isinstance(cik, str):
        s = cik.strip()
        if not s:
            raise InputValidationError("cik must be non-empty")
        if s.startswith("CIK"):
            s = s[3:]
        if not s.isdigit():
            raise InputValidationError(f"cik must be digits, got {cik!r}")
    else:
        raise InputValidationError(f"cik must be str or int, got {type(cik).__name__}")
    if len(s) > 10:
        raise InputValidationError(f"cik {cik!r} exceeds 10 digits")
    return s.zfill(10)


class _TokenBucket:
    """Monotonic-clock sliding-window rate limiter, max ``rps`` per rolling 1 second.

    Not thread-safe; the MVP is single-threaded. If we ever go async or
    multi-thread, wrap ``record()`` in a lock.
    """

    def __init__(self, rps: int) -> None:
        self._rps = rps
        self._stamps: deque[float] = deque()

    def record(self, now: float | None = None) -> None:
        """Record a request attempt. Raises ``RateLimitExceeded`` if over budget."""
        t = now if now is not None else time.monotonic()
        cutoff = t - 1.0
        while self._stamps and self._stamps[0] <= cutoff:
            self._stamps.popleft()
        if len(self._stamps) >= self._rps:
            raise RateLimitExceeded(
                f"EDGAR rate limit: {self._rps} req/s exceeded"
            )
        self._stamps.append(t)


class EdgarClient:
    """Minimal, rate-limited, UA-declared SEC EDGAR client.

    Construct once and reuse — the underlying ``httpx.Client`` pools
    connections. Call :meth:`close` (or use as a context manager) to release
    the socket.
    """

    def __init__(
        self,
        *,
        user_agent: str | None = None,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        ua = user_agent if user_agent is not None else DEFAULT_USER_AGENT
        if not ua or not ua.strip():
            raise InputValidationError("user_agent must be a non-empty string")
        self._ua = ua
        self._client = httpx.Client(
            timeout=timeout,
            headers={"User-Agent": ua, "Accept-Encoding": "gzip, deflate"},
            transport=transport,
        )
        self._bucket = _TokenBucket(MAX_RPS)

    def __enter__(self) -> "EdgarClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # --- Public API -----------------------------------------------------

    def fetch_company_tickers(self) -> dict[str, Any]:
        """Return the ``company_tickers.json`` manifest from sec.gov."""
        return self._get_json(_COMPANY_TICKERS_URL)

    def fetch_submissions(self, cik: str | int) -> dict[str, Any]:
        """Return the submissions index for ``cik`` (any CIK form accepted)."""
        url = _SUBMISSIONS_URL.format(cik10=normalize_cik(cik))
        return self._get_json(url)

    def fetch_filing_index(self, cik: str | int, accession: str) -> dict[str, Any]:
        """Return the filing's index.json (lists documents in an accession).

        ``accession`` may be either the 18-character dashed form
        (``"0000320193-23-000106"``) or the 18-digit no-dash form.
        """
        if not isinstance(accession, str) or not accession.strip():
            raise InputValidationError("accession must be a non-empty string")
        nodash = accession.replace("-", "")
        if not nodash.isdigit() or len(nodash) != 18:
            raise InputValidationError(
                f"accession {accession!r} must be 18 digits (dashes optional)"
            )
        cik_int = int(normalize_cik(cik))
        url = _FILING_INDEX_URL.format(cik_int=cik_int, accession_nodash=nodash)
        return self._get_json(url)

    def fetch_document(self, url: str) -> bytes:
        """Fetch an absolute URL on ``sec.gov`` and return raw bytes.

        Restricts to ``sec.gov`` / ``data.sec.gov`` to keep this client's
        auth and rate-limit contract narrow.
        """
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            raise InputValidationError(f"url must be an absolute http(s) URL, got {url!r}")
        host = httpx.URL(url).host or ""
        if not (host == "sec.gov" or host.endswith(".sec.gov")):
            raise InputValidationError(
                f"fetch_document only supports sec.gov hosts, got {host!r}"
            )
        resp = self._request("GET", url)
        return resp.content

    # --- Internals ------------------------------------------------------

    def _get_json(self, url: str) -> dict[str, Any]:
        resp = self._request("GET", url)
        try:
            payload = resp.json()
        except ValueError as exc:
            raise EdgarHttpError(
                f"EDGAR response was not JSON: {exc}",
                status_code=resp.status_code,
                url=url,
            ) from exc
        if not isinstance(payload, dict):
            raise EdgarHttpError(
                f"EDGAR response root was not a JSON object (got {type(payload).__name__})",
                status_code=resp.status_code,
                url=url,
            )
        return payload

    def _request(self, method: str, url: str) -> httpx.Response:
        last_exc: Exception | None = None
        for attempt in range(len(_BACKOFFS_S) + 1):
            # Rate-limit check is *per-attempt*: retries consume budget too.
            self._bucket.record()
            try:
                resp = self._client.request(method, url)
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < len(_BACKOFFS_S):
                    time.sleep(_BACKOFFS_S[attempt])
                    continue
                raise EdgarHttpError(
                    f"network error after {attempt + 1} attempts: {exc}",
                    status_code=0,
                    url=url,
                ) from exc
            if resp.status_code < 400:
                return resp
            if resp.status_code in _RETRYABLE and attempt < len(_BACKOFFS_S):
                time.sleep(_BACKOFFS_S[attempt])
                continue
            raise EdgarHttpError(
                f"EDGAR HTTP {resp.status_code} for {url}",
                status_code=resp.status_code,
                url=url,
            )
        # Unreachable: the loop either returns or raises. Keep for type-checkers.
        raise EdgarHttpError(  # pragma: no cover
            f"retry loop exhausted without raising ({last_exc})",
            status_code=0,
            url=url,
        )
