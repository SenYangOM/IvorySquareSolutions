"""Thin wrapper around the ``accounting_expert`` persona.

All domain voice, prompt text, and model choice live in
``mvp/human_layer/personas/accounting_expert.yaml``. This module only
delegates to :class:`mvp.agents.persona_runtime.PersonaRuntime`; it
carries no accounting logic.
"""

from __future__ import annotations

from pathlib import Path

from mvp.agents.persona_runtime import PersonaResponse, PersonaRuntime


PERSONA_ID = "accounting_expert"

_runtime = PersonaRuntime()


def call(user_message: str, *, cache_dir: Path | None = None) -> PersonaResponse:
    """Invoke the accounting_expert persona with ``user_message``."""
    return _runtime.call(PERSONA_ID, user_message, cache_dir=cache_dir)


__all__ = ["PERSONA_ID", "call"]
