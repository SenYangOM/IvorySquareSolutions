"""Persona runtime — generic YAML-driven LLM persona dispatcher.

Engineering layer only. **No domain knowledge lives in this file.** All
accounting / finance / evaluation / audit voice lives in the YAML configs
under ``mvp/human_layer/personas/`` that this module loads.

Design — Operating Principle P1 (``mvp_build_goal.md`` §0)
---------------------------------------------------------
A change in the human layer must not require recompilation, code review,
or engineering involvement. The mechanism:

* Each persona's prompt, model assignment, and contract description lives
  in ``mvp/human_layer/personas/<persona_id>.yaml``.
* The four thin wrappers under ``mvp/agents/{accounting_expert,
  quant_finance_methodologist, evaluation_agent, citation_auditor}.py``
  each carry only a ``PERSONA_ID`` constant and a one-line ``call()``.
* Replacing a subagent with a real expert means (a) amending the YAML's
  ``system_prompt`` to that expert's own style guide, or (b) bypassing
  the runtime entirely and having the human author the downstream
  declarative artifacts (rule templates, gold sets, audit comments)
  directly. Either path requires no Python change.

Design — Operating Principle P3 (``mvp_build_goal.md`` §0)
---------------------------------------------------------
Every error from this module is a typed ``PersonaCallError`` carrying
``error_code``, ``error_category``, ``retry_safe``, and
``suggested_remediation``. Nothing raw leaks to the caller.

Audit logging
-------------
Every ``PersonaRuntime.call()`` invocation writes one JSON record to
``agents/audit_log/<YYYY-MM-DD>_<persona_id>_<short_hash>.json``. The
record captures the persona config hash, the user-message hash, the
exact system prompt and user message, the response text, token counts,
cache-hit status, and timestamps. Reviewers sample these per
``mvp/human_layer/audit_review_guide.md``; they are never hand-edited.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from mvp.lib.errors import ErrorCategory, MissingApiKey, PersonaCallError
from mvp.lib.llm import LlmClient


PersonaRole = Literal[
    "accounting_expert",
    "quant_finance_methodologist",
    "evaluation_agent",
    "citation_auditor",
]


DEFAULT_HUMAN_LAYER_ROOT = Path(__file__).resolve().parent.parent / "human_layer"
DEFAULT_AUDIT_LOG_ROOT = Path(__file__).resolve().parent / "audit_log"


class PersonaProvenance(BaseModel):
    """Authoring metadata for a persona YAML.

    ``authored_by`` names the human (or the name of the Claude subagent
    instance) who wrote this version of the persona. ``version`` is a
    semver string; bumping it is how the human layer signals that the
    persona's contract has changed.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    authored_by: str = Field(min_length=1)
    authored_at: date
    version: str = Field(pattern=r"^\d+\.\d+\.\d+$")


class Persona(BaseModel):
    """A declarative persona configuration.

    See ``mvp/human_layer/personas/*.yaml`` for the four MVP instances.
    Loading this model via :func:`load_persona` validates every field;
    unknown keys are rejected so accidental drift is loud.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]*$", min_length=3, max_length=64)
    role_description: str = Field(min_length=20)
    model: str = Field(min_length=3)
    system_prompt: str = Field(min_length=200)
    input_contract_description: str = Field(min_length=50)
    output_contract_description: str = Field(min_length=50)
    replacement_note: str = Field(min_length=50)
    provenance: PersonaProvenance


@dataclass(frozen=True)
class PersonaResponse:
    """Structured return value of :meth:`PersonaRuntime.call`.

    Attributes
    ----------
    text:
        The assistant's response text.
    persona_id:
        The persona that produced ``text``.
    model:
        The model id recorded on the persona YAML.
    input_tokens, output_tokens:
        Token counts from the underlying LLM call (``0`` on cache hit).
    audit_log_path:
        Absolute path of the JSON audit record just written.
    cache_hit:
        Whether the underlying :class:`LlmClient` served from the cache.
    """

    text: str
    persona_id: str
    model: str
    input_tokens: int
    output_tokens: int
    audit_log_path: Path
    cache_hit: bool


def load_persona(
    persona_id: str,
    *,
    human_layer_root: Path | None = None,
) -> Persona:
    """Load and validate a persona YAML from the human layer.

    Parameters
    ----------
    persona_id:
        File-stem of the YAML (e.g. ``"accounting_expert"``).
    human_layer_root:
        Override the default location (``mvp/human_layer``). Tests pass a
        fixture directory here.

    Raises
    ------
    PersonaCallError
        If the YAML file is missing, cannot be parsed, or fails schema
        validation. The ``reason`` discriminator is ``persona_not_found``
        or ``persona_schema_invalid``.
    """
    root = Path(human_layer_root) if human_layer_root is not None else DEFAULT_HUMAN_LAYER_ROOT
    path = root / "personas" / f"{persona_id}.yaml"
    if not path.is_file():
        raise PersonaCallError(
            f"Persona YAML not found at {path}",
            persona_id=persona_id,
            reason="persona_not_found",
            error_code="persona_not_found",
            error_category=ErrorCategory.INPUT_VALIDATION,
            retry_safe=False,
        )
    try:
        with path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise PersonaCallError(
            f"Persona YAML at {path} is not valid YAML: {exc}",
            persona_id=persona_id,
            reason="persona_schema_invalid",
            error_code="persona_schema_invalid",
            error_category=ErrorCategory.PARSE,
            retry_safe=False,
        ) from exc
    if not isinstance(raw, dict):
        raise PersonaCallError(
            f"Persona YAML at {path} must be a mapping, got {type(raw).__name__}",
            persona_id=persona_id,
            reason="persona_schema_invalid",
            error_code="persona_schema_invalid",
            error_category=ErrorCategory.PARSE,
            retry_safe=False,
        )
    try:
        persona = Persona.model_validate(raw)
    except Exception as exc:  # pydantic.ValidationError — broaden for forward compat
        raise PersonaCallError(
            f"Persona YAML at {path} failed schema validation: {exc}",
            persona_id=persona_id,
            reason="persona_schema_invalid",
            error_code="persona_schema_invalid",
            error_category=ErrorCategory.INPUT_VALIDATION,
            retry_safe=False,
        ) from exc
    if persona.id != persona_id:
        raise PersonaCallError(
            f"Persona YAML id {persona.id!r} does not match filename {persona_id!r}",
            persona_id=persona_id,
            reason="persona_schema_invalid",
            error_code="persona_schema_invalid",
            error_category=ErrorCategory.INPUT_VALIDATION,
            retry_safe=False,
        )
    return persona


class PersonaRuntime:
    """Generic dispatcher for persona calls.

    One instance can serve any number of personas; it is cheap to
    construct and threadsafe for read-only use. Tests instantiate it
    with a ``human_layer_root`` pointing at a fixture directory.

    Parameters
    ----------
    human_layer_root:
        Where to look for ``personas/<id>.yaml`` files. Defaults to the
        sibling ``mvp/human_layer`` directory.
    audit_log_root:
        Where to write per-call audit JSON. Defaults to
        ``mvp/agents/audit_log`` and is created on first write.
    llm_cache_dir:
        Forwarded to :class:`LlmClient`. Enables determinism and lets
        cached calls succeed without an API key. Defaults to
        ``mvp/agents/audit_log/_llm_cache``.
    """

    def __init__(
        self,
        *,
        human_layer_root: Path | None = None,
        audit_log_root: Path | None = None,
        llm_cache_dir: Path | None = None,
    ) -> None:
        self._human_layer_root = (
            Path(human_layer_root) if human_layer_root is not None else DEFAULT_HUMAN_LAYER_ROOT
        )
        self._audit_log_root = (
            Path(audit_log_root) if audit_log_root is not None else DEFAULT_AUDIT_LOG_ROOT
        )
        self._llm_cache_dir = (
            Path(llm_cache_dir)
            if llm_cache_dir is not None
            else self._audit_log_root / "_llm_cache"
        )
        # Cache loaded personas so repeated calls don't re-parse YAML.
        self._persona_cache: dict[str, Persona] = {}

    def call(
        self,
        persona_id: str,
        user_message: str,
        *,
        cache_dir: Path | None = None,
        temperature: float = 0.0,
        max_tokens: int = 4000,
    ) -> PersonaResponse:
        """Invoke the named persona with ``user_message``.

        Parameters
        ----------
        persona_id:
            File-stem of the persona YAML.
        user_message:
            The prompt to send as a single user turn. Tool use is not
            supported at the runtime level — compose at the skill layer.
        cache_dir:
            Overrides the default LLM cache directory (for tests).
        temperature, max_tokens:
            Forwarded to :class:`LlmClient`.

        Raises
        ------
        PersonaCallError
            With ``error_code="missing_api_key"`` when the LLM call misses
            the cache and no ``ANTHROPIC_API_KEY`` is set. With
            ``error_code="persona_not_found"`` / ``persona_schema_invalid``
            for YAML-layer failures. With ``error_code="llm_call_error"``
            for underlying SDK errors after retries.
        """
        persona = self._load(persona_id)

        effective_cache_dir = Path(cache_dir) if cache_dir is not None else self._llm_cache_dir
        client = LlmClient(model=persona.model, cache_dir=effective_cache_dir)

        messages = [{"role": "user", "content": user_message}]
        try:
            resp = client.call(
                system=persona.system_prompt,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except MissingApiKey as exc:
            raise PersonaCallError(
                (
                    f"Persona {persona_id!r} was invoked without ANTHROPIC_API_KEY "
                    f"and no cached response was available."
                ),
                persona_id=persona_id,
                reason="missing_api_key",
                error_code="missing_api_key",
                error_category=ErrorCategory.AUTH,
                retry_safe=False,
            ) from exc
        except Exception as exc:
            raise PersonaCallError(
                f"Underlying LLM call failed for persona {persona_id!r}: {exc}",
                persona_id=persona_id,
                reason="llm_call_failed",
                error_code="llm_call_error",
                error_category=ErrorCategory.UPSTREAM,
                retry_safe=True,
            ) from exc

        audit_path = self._write_audit_log(
            persona=persona,
            user_message=user_message,
            response_text=resp.text,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            cache_hit=resp.cache_hit,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return PersonaResponse(
            text=resp.text,
            persona_id=persona.id,
            model=persona.model,
            input_tokens=resp.input_tokens,
            output_tokens=resp.output_tokens,
            audit_log_path=audit_path,
            cache_hit=resp.cache_hit,
        )

    def _load(self, persona_id: str) -> Persona:
        if persona_id not in self._persona_cache:
            self._persona_cache[persona_id] = load_persona(
                persona_id, human_layer_root=self._human_layer_root
            )
        return self._persona_cache[persona_id]

    @property
    def suggested_remediation_for_missing_key(self) -> str:
        """Human-readable remediation the skill boundary can surface to an agent."""
        return (
            "Set ANTHROPIC_API_KEY in the environment, or prime the LLM cache "
            "by recording a previous call with the same inputs."
        )

    def _write_audit_log(
        self,
        *,
        persona: Persona,
        user_message: str,
        response_text: str,
        input_tokens: int,
        output_tokens: int,
        cache_hit: bool,
        temperature: float,
        max_tokens: int,
    ) -> Path:
        self._audit_log_root.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        day = now.strftime("%Y-%m-%d")

        persona_config_hash = _persona_config_hash(persona)
        user_message_hash = hashlib.sha256(user_message.encode("utf-8")).hexdigest()
        short = hashlib.sha256(
            (persona_config_hash + user_message_hash).encode("utf-8")
        ).hexdigest()[:10]

        filename = f"{day}_{persona.id}_{short}.json"
        path = self._audit_log_root / filename
        record = {
            "persona_id": persona.id,
            "persona_version": persona.provenance.version,
            "persona_config_hash": persona_config_hash,
            "model": persona.model,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "system_prompt": persona.system_prompt,
            "user_message": user_message,
            "user_message_hash": user_message_hash,
            "response_text": response_text,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_hit": cache_hit,
            "called_at": now.isoformat(),
        }
        tmp = path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, sort_keys=True, indent=2)
        tmp.replace(path)
        return path


def _persona_config_hash(persona: Persona) -> str:
    """Stable hash over the persona's authoring-relevant fields.

    Used to correlate audit-log entries with the exact YAML state that
    produced them. Excludes ``retrieved_at`` / timestamp fields so the
    hash is reproducible across clone / re-install.
    """
    payload = json.dumps(
        persona.model_dump(mode="json"), sort_keys=True, ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


__all__ = [
    "DEFAULT_AUDIT_LOG_ROOT",
    "DEFAULT_HUMAN_LAYER_ROOT",
    "Persona",
    "PersonaProvenance",
    "PersonaResponse",
    "PersonaRole",
    "PersonaRuntime",
    "load_persona",
]
