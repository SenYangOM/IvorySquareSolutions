"""Unit tests for mvp.agents.persona_runtime.

Exercises the generic persona loader + dispatcher:
- loading a valid persona YAML from a fixture tree;
- rejecting missing-file and schema-invalid cases with typed errors;
- graceful no-API-key behavior (cache-hit succeeds, cache-miss raises);
- audit-log write on every call;
- integration against the real mvp/human_layer/personas/ files
  (the four MVP personas load cleanly).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mvp.agents.persona_runtime import (
    DEFAULT_HUMAN_LAYER_ROOT,
    Persona,
    PersonaRuntime,
    load_persona,
)
from mvp.lib.errors import PersonaCallError
from mvp.lib.llm import LlmClient


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


VALID_PERSONA_YAML = """\
id: test_persona
role_description: "Test persona for unit tests. Role is to produce canned responses."
model: claude-opus-4-7
system_prompt: "You are a test persona. Produce exactly the response the test harness expects. This prompt is longer than 200 characters to satisfy the schema validator which demands substantive system prompts on all personas including fixtures used by the persona-runtime test suite."
input_contract_description: "You receive a short string and echo a short string. Deterministic behavior is required for the test suite."
output_contract_description: "You produce a short deterministic string. The harness compares it byte-for-byte against the cached response."
replacement_note: "To replace this test persona with a real implementation, edit this YAML and update the downstream contract."
provenance:
  authored_by: "test suite"
  authored_at: 2026-04-17
  version: "0.1.0"
"""


@pytest.fixture
def persona_dir(tmp_path: Path) -> Path:
    """Build a minimal human_layer tree under tmp_path and return its root."""
    root = tmp_path / "human_layer"
    (root / "personas").mkdir(parents=True)
    (root / "personas" / "test_persona.yaml").write_text(VALID_PERSONA_YAML, encoding="utf-8")
    return root


# ---------------------------------------------------------------------------
# load_persona
# ---------------------------------------------------------------------------


def test_load_persona_ok(persona_dir: Path) -> None:
    p = load_persona("test_persona", human_layer_root=persona_dir)
    assert isinstance(p, Persona)
    assert p.id == "test_persona"
    assert p.model == "claude-opus-4-7"
    assert p.provenance.version == "0.1.0"


def test_load_persona_missing_file_raises(tmp_path: Path) -> None:
    empty_root = tmp_path / "empty"
    (empty_root / "personas").mkdir(parents=True)
    with pytest.raises(PersonaCallError) as exc_info:
        load_persona("does_not_exist", human_layer_root=empty_root)
    assert exc_info.value.error_code == "persona_not_found"
    assert exc_info.value.reason == "persona_not_found"
    assert exc_info.value.persona_id == "does_not_exist"
    assert exc_info.value.retry_safe is False


def test_load_persona_malformed_yaml_raises(tmp_path: Path) -> None:
    root = tmp_path / "human_layer"
    (root / "personas").mkdir(parents=True)
    (root / "personas" / "broken.yaml").write_text("not: [valid: yaml: at all", encoding="utf-8")
    with pytest.raises(PersonaCallError) as exc_info:
        load_persona("broken", human_layer_root=root)
    assert exc_info.value.error_code == "persona_schema_invalid"


def test_load_persona_schema_invalid_raises(tmp_path: Path) -> None:
    root = tmp_path / "human_layer"
    (root / "personas").mkdir(parents=True)
    # missing required fields
    (root / "personas" / "bad.yaml").write_text(
        "id: bad\nrole_description: short\nmodel: x\n", encoding="utf-8"
    )
    with pytest.raises(PersonaCallError) as exc_info:
        load_persona("bad", human_layer_root=root)
    assert exc_info.value.error_code == "persona_schema_invalid"


def test_load_persona_id_filename_mismatch_raises(tmp_path: Path) -> None:
    root = tmp_path / "human_layer"
    (root / "personas").mkdir(parents=True)
    # the YAML claims id=other_name but the filename is wrong_name
    yaml_body = VALID_PERSONA_YAML.replace("id: test_persona", "id: other_name")
    (root / "personas" / "wrong_name.yaml").write_text(yaml_body, encoding="utf-8")
    with pytest.raises(PersonaCallError) as exc_info:
        load_persona("wrong_name", human_layer_root=root)
    assert exc_info.value.error_code == "persona_schema_invalid"


# ---------------------------------------------------------------------------
# PersonaRuntime — instantiation and call paths
# ---------------------------------------------------------------------------


def test_runtime_instantiates_without_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runtime = PersonaRuntime()
    assert runtime is not None


def test_runtime_call_cache_hit_returns_response(
    persona_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    audit_root = tmp_path / "audit_log"
    cache_dir = tmp_path / "llm_cache"

    runtime = PersonaRuntime(
        human_layer_root=persona_dir,
        audit_log_root=audit_root,
        llm_cache_dir=cache_dir,
    )

    # Prime the cache by hand: the client under the hood derives a key
    # from (model, system, messages, temperature, max_tokens).
    persona = load_persona("test_persona", human_layer_root=persona_dir)
    client = LlmClient(model=persona.model, cache_dir=cache_dir)
    # NOTE: the runtime's default max_tokens is 12000 (raised from 4000
    # to give thinking-enabled personas headroom for long generations);
    # keep the cache-key derivation in sync so the cache hit lands.
    key = client._derive_key(
        persona.system_prompt,
        [{"role": "user", "content": "hello"}],
        0.0,
        12000,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"text": "cached-reply", "input_tokens": 42, "output_tokens": 23}),
        encoding="utf-8",
    )

    resp = runtime.call("test_persona", "hello")
    assert resp.text == "cached-reply"
    assert resp.persona_id == "test_persona"
    assert resp.model == "claude-opus-4-7"
    assert resp.cache_hit is True
    assert resp.input_tokens == 42
    assert resp.output_tokens == 23
    assert resp.audit_log_path.exists()

    # Audit record has the expected shape.
    record = json.loads(resp.audit_log_path.read_text(encoding="utf-8"))
    assert record["persona_id"] == "test_persona"
    assert record["user_message"] == "hello"
    assert record["response_text"] == "cached-reply"
    assert record["cache_hit"] is True
    assert record["persona_version"] == "0.1.0"
    assert "persona_config_hash" in record and len(record["persona_config_hash"]) == 64


def test_runtime_call_cache_miss_no_api_key_raises(
    persona_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runtime = PersonaRuntime(
        human_layer_root=persona_dir,
        audit_log_root=tmp_path / "audit_log",
        llm_cache_dir=tmp_path / "llm_cache",
    )
    with pytest.raises(PersonaCallError) as exc_info:
        runtime.call("test_persona", "unprimed question")
    assert exc_info.value.error_code == "missing_api_key"
    assert exc_info.value.retry_safe is False
    assert exc_info.value.persona_id == "test_persona"


def test_runtime_remediation_string_surfaced(persona_dir: Path, tmp_path: Path) -> None:
    runtime = PersonaRuntime(
        human_layer_root=persona_dir,
        audit_log_root=tmp_path / "audit_log",
        llm_cache_dir=tmp_path / "llm_cache",
    )
    # The runtime publishes a human-readable remediation the skill
    # boundary can embed in the public error envelope.
    assert "ANTHROPIC_API_KEY" in runtime.suggested_remediation_for_missing_key
    assert "cache" in runtime.suggested_remediation_for_missing_key.lower()


def test_runtime_audit_log_idempotent_for_same_inputs(
    persona_dir: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two calls with identical inputs write to the same filename (deterministic)."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    audit_root = tmp_path / "audit_log"
    cache_dir = tmp_path / "llm_cache"
    runtime = PersonaRuntime(
        human_layer_root=persona_dir,
        audit_log_root=audit_root,
        llm_cache_dir=cache_dir,
    )
    persona = load_persona("test_persona", human_layer_root=persona_dir)
    client = LlmClient(model=persona.model, cache_dir=cache_dir)
    key = client._derive_key(
        persona.system_prompt,
        [{"role": "user", "content": "x"}],
        0.0,
        12000,
    )
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps({"text": "r", "input_tokens": 1, "output_tokens": 1}),
        encoding="utf-8",
    )

    r1 = runtime.call("test_persona", "x")
    r2 = runtime.call("test_persona", "x")
    # Same filename — the short-hash is deterministic over persona + message.
    assert r1.audit_log_path == r2.audit_log_path


# ---------------------------------------------------------------------------
# Integration against the real mvp/human_layer/personas/ files
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "persona_id,expected_model",
    [
        ("accounting_expert", "claude-sonnet-4-6"),
        ("quant_finance_methodologist", "claude-sonnet-4-6"),
        ("evaluation_agent", "claude-sonnet-4-6"),
        ("citation_auditor", "claude-sonnet-4-6"),
    ],
)
def test_real_mvp_personas_load(persona_id: str, expected_model: str) -> None:
    p = load_persona(persona_id)
    assert p.id == persona_id
    assert p.model == expected_model
    # Substantive prompt per P2: every persona has a real system prompt.
    assert len(p.system_prompt) >= 500
    # Every persona has a replacement_note — the seam for human takeover.
    assert len(p.replacement_note) >= 50


def test_real_mvp_personas_are_in_default_tree() -> None:
    """Sanity check: the default human_layer root points at the real personas."""
    root = DEFAULT_HUMAN_LAYER_ROOT
    for persona_id in (
        "accounting_expert",
        "quant_finance_methodologist",
        "evaluation_agent",
        "citation_auditor",
    ):
        assert (root / "personas" / f"{persona_id}.yaml").is_file()


def test_wrapper_modules_import_cleanly() -> None:
    """The four thin wrappers must be importable without an API key."""
    from mvp.agents import accounting_expert, citation_auditor, evaluation_agent
    from mvp.agents import quant_finance_methodologist

    assert accounting_expert.PERSONA_ID == "accounting_expert"
    assert quant_finance_methodologist.PERSONA_ID == "quant_finance_methodologist"
    assert evaluation_agent.PERSONA_ID == "evaluation_agent"
    assert citation_auditor.PERSONA_ID == "citation_auditor"
