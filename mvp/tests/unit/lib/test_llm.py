"""Unit tests for mvp.lib.llm.

All tests exercise the wrapper WITHOUT a live API key by hitting the cache
path. Cache entries are written directly under ``tmp_path`` and read back
via :meth:`LlmClient.call`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mvp.lib.errors import MissingApiKey
from mvp.lib.llm import LlmClient, LlmResponse


def _populate_cache(client: LlmClient, system: str, messages: list[dict], payload: dict) -> str:
    """Write ``payload`` into the wrapper's on-disk cache and return the key."""
    key = client._derive_key(system, messages, 0.0, 4000)
    cache_dir = client._cache_dir
    assert cache_dir is not None
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(json.dumps(payload), encoding="utf-8")
    return key


def test_cache_hit_returns_cached_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    _populate_cache(
        client,
        "sys",
        [{"role": "user", "content": "hi"}],
        {"text": "cached-hello", "input_tokens": 7, "output_tokens": 11},
    )

    resp = client.call("sys", [{"role": "user", "content": "hi"}])
    assert isinstance(resp, LlmResponse)
    assert resp.text == "cached-hello"
    assert resp.input_tokens == 7
    assert resp.output_tokens == 11
    assert resp.cache_hit is True


def test_cache_miss_without_api_key_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    with pytest.raises(MissingApiKey):
        client.call("sys", [{"role": "user", "content": "hi"}])


def test_cache_miss_without_cache_dir_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient()
    with pytest.raises(MissingApiKey):
        client.call("sys", [{"role": "user", "content": "hi"}])


def test_cache_key_sensitive_to_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    _populate_cache(
        client,
        "sys-A",
        [{"role": "user", "content": "hi"}],
        {"text": "A", "input_tokens": 1, "output_tokens": 1},
    )

    # Same messages, different system → cache miss.
    with pytest.raises(MissingApiKey):
        client.call("sys-B", [{"role": "user", "content": "hi"}])


def test_cache_key_sensitive_to_temperature(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    _populate_cache(
        client,
        "sys",
        [{"role": "user", "content": "hi"}],
        {"text": "A", "input_tokens": 1, "output_tokens": 1},
    )
    with pytest.raises(MissingApiKey):
        client.call("sys", [{"role": "user", "content": "hi"}], temperature=0.7)


def test_explicit_cache_key_used(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    (tmp_path / "custom-key.json").write_text(
        json.dumps({"text": "via-key", "input_tokens": 3, "output_tokens": 4}),
        encoding="utf-8",
    )
    resp = client.call(
        "sys",
        [{"role": "user", "content": "hi"}],
        cache_key="custom-key",
    )
    assert resp.text == "via-key"
    assert resp.cache_hit is True


def test_corrupt_cache_entry_treated_as_miss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    client = LlmClient(cache_dir=tmp_path)
    key = client._derive_key("sys", [{"role": "user", "content": "hi"}], 0.0, 4000)
    (tmp_path / f"{key}.json").write_text("{not valid json", encoding="utf-8")
    with pytest.raises(MissingApiKey):
        client.call("sys", [{"role": "user", "content": "hi"}])


def test_env_var_api_key_picked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-env")
    client = LlmClient()
    assert client._api_key == "sk-test-env"


def test_explicit_api_key_overrides_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-env")
    client = LlmClient(api_key="sk-explicit")
    assert client._api_key == "sk-explicit"
