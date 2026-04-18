"""Thin wrapper around the ``quant_finance_methodologist`` persona.

All domain voice, prompt text, and model choice live in
``mvp/human_layer/personas/quant_finance_methodologist.yaml``. This
module only delegates to :class:`mvp.agents.persona_runtime.PersonaRuntime`;
it carries no methodology logic.
"""

from __future__ import annotations

from pathlib import Path

from mvp.agents.persona_runtime import PersonaResponse, PersonaRuntime


PERSONA_ID = "quant_finance_methodologist"

_runtime = PersonaRuntime()


def call(user_message: str, *, cache_dir: Path | None = None) -> PersonaResponse:
    """Invoke the quant_finance_methodologist persona with ``user_message``."""
    return _runtime.call(PERSONA_ID, user_message, cache_dir=cache_dir)


__all__ = ["PERSONA_ID", "call"]
