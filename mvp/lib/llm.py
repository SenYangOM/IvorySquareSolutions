"""Anthropic SDK wrapper.

Wraps the ``anthropic`` SDK with three concerns layered on top:

* **Caching.** If a ``cache_dir`` is configured, every call is keyed by a
  SHA-256 over ``(model, system, messages, temperature, max_tokens)``;
  cache hits bypass the SDK entirely. This lets tests exercise the wrapper
  without an API key, and lets the MVP's determinism contract
  (``success_criteria.md`` §4.4) hold for LLM-involved skills.
* **Retries.** One retry on transient ``anthropic.APIError`` subclasses.
  Auth errors re-raise immediately as :class:`MissingApiKey`.
* **API-key resolution.** Explicit ``api_key`` > env ``ANTHROPIC_API_KEY``.
  If both are absent the wrapper still works for cache-hit paths; a miss
  with no key raises :class:`MissingApiKey`.

The class deliberately does **not** know about tool use, streaming, or
vision — the MVP's persona runtime (``mvp.agents``) will compose those on
top when it arrives in Phase 4.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic

from .errors import LlmCallError, MissingApiKey
from .hashing import sha256_text


@dataclass(frozen=True)
class LlmResponse:
    """Structured return value of :meth:`LlmClient.call`.

    Attributes
    ----------
    text:
        Joined assistant text across all returned content blocks.
    input_tokens:
        Prompt tokens consumed (0 on cache hit).
    output_tokens:
        Completion tokens produced (0 on cache hit).
    cache_hit:
        ``True`` if the response was served from the on-disk cache.
    """

    text: str
    input_tokens: int
    output_tokens: int
    cache_hit: bool


class LlmClient:
    """Anthropic SDK wrapper with on-disk caching and single-retry resilience.

    Parameters
    ----------
    model:
        The Anthropic model id. Defaults to the persona-runtime default
        (``claude-opus-4-7``); callers should pass ``claude-sonnet-4-6``
        for cost-managed personas per ``mvp_build_goal.md`` §13 decision 1.
    api_key:
        Explicit API key. If ``None``, the wrapper reads
        ``ANTHROPIC_API_KEY`` from the environment. Missing keys are OK
        for cache-only usage; they raise :class:`MissingApiKey` only on
        cache miss.
    cache_dir:
        Directory holding cached responses. Created on first write.
        If ``None``, caching is disabled.
    """

    def __init__(
        self,
        model: str = "claude-opus-4-7",
        *,
        api_key: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._model = model
        self._api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY")
        self._cache_dir = Path(cache_dir) if cache_dir is not None else None
        # Lazy SDK client so cache-only usage works without a key.
        self._sdk: anthropic.Anthropic | None = None

    def call(
        self,
        system: str,
        messages: list[dict[str, Any]],
        *,
        temperature: float = 0.0,
        max_tokens: int = 4000,
        cache_key: str | None = None,
    ) -> LlmResponse:
        """Invoke the model (or serve from cache) and return a response.

        Parameters
        ----------
        system:
            System prompt (may be empty).
        messages:
            Anthropic-format message list, e.g.
            ``[{"role": "user", "content": "..."}]``.
        temperature:
            Sampling temperature. Defaults to 0 for reproducibility.
        max_tokens:
            Output-token ceiling.
        cache_key:
            Optional explicit cache key. If ``None``, a key is derived from
            the canonical call payload.

        Raises
        ------
        MissingApiKey
            On cache miss with no API key available.
        LlmCallError
            After the SDK's own retry plus this wrapper's one extra retry
            have both failed.
        """
        key = cache_key or self._derive_key(system, messages, temperature, max_tokens)

        cached = self._cache_read(key)
        if cached is not None:
            return LlmResponse(
                text=cached["text"],
                input_tokens=int(cached.get("input_tokens", 0)),
                output_tokens=int(cached.get("output_tokens", 0)),
                cache_hit=True,
            )

        if not self._api_key:
            raise MissingApiKey(
                "ANTHROPIC_API_KEY is not set and no cached response was found "
                f"(cache_key={key[:12]}…)"
            )

        sdk = self._get_sdk()

        attempts = 0
        last_exc: Exception | None = None
        while attempts < 2:
            attempts += 1
            try:
                resp = sdk.messages.create(
                    model=self._model,
                    system=system,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except anthropic.AuthenticationError as exc:
                # Never retry an auth error — re-raise as MissingApiKey so
                # the skill boundary maps it to error_category=auth.
                raise MissingApiKey(f"Anthropic auth failed: {exc}") from exc
            except anthropic.APIError as exc:
                last_exc = exc
                if attempts >= 2:
                    raise LlmCallError(
                        f"Anthropic call failed after {attempts} attempts: {exc}"
                    ) from exc
                continue
            break
        else:  # pragma: no cover - loop always returns or raises
            raise LlmCallError(f"Anthropic call failed: {last_exc}")

        text = _join_text_blocks(resp)
        input_tokens = int(getattr(getattr(resp, "usage", None), "input_tokens", 0) or 0)
        output_tokens = int(getattr(getattr(resp, "usage", None), "output_tokens", 0) or 0)

        self._cache_write(
            key,
            {"text": text, "input_tokens": input_tokens, "output_tokens": output_tokens},
        )
        return LlmResponse(
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_hit=False,
        )

    # --- Internals ------------------------------------------------------

    def _get_sdk(self) -> anthropic.Anthropic:
        if self._sdk is None:
            self._sdk = anthropic.Anthropic(api_key=self._api_key)
        return self._sdk

    def _derive_key(
        self,
        system: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
    ) -> str:
        payload = json.dumps(
            {
                "model": self._model,
                "system": system,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        return sha256_text(payload, normalize_newlines=False)

    def _cache_path(self, key: str) -> Path | None:
        if self._cache_dir is None:
            return None
        return self._cache_dir / f"{key}.json"

    def _cache_read(self, key: str) -> dict[str, Any] | None:
        path = self._cache_path(key)
        if path is None or not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            # Corrupt cache entry: treat as miss. Don't crash the caller.
            return None
        if not isinstance(data, dict) or "text" not in data:
            return None
        return data

    def _cache_write(self, key: str, data: dict[str, Any]) -> None:
        path = self._cache_path(key)
        if path is None:
            return
        self._cache_dir.mkdir(parents=True, exist_ok=True)  # type: ignore[union-attr]
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, sort_keys=True)
        tmp.replace(path)


def _join_text_blocks(resp: Any) -> str:
    """Concatenate text across all ``TextBlock`` entries in an Anthropic response."""
    parts: list[str] = []
    for block in getattr(resp, "content", []) or []:
        # The SDK returns typed blocks; ``type == "text"`` carries a ``.text``.
        if getattr(block, "type", None) == "text":
            parts.append(getattr(block, "text", ""))
    return "".join(parts)
