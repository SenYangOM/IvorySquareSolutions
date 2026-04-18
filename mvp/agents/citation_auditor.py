"""Thin wrapper around the ``citation_auditor`` persona.

All domain voice, prompt text, and model choice live in
``mvp/human_layer/personas/citation_auditor.yaml``. This module only
delegates to :class:`mvp.agents.persona_runtime.PersonaRuntime`; it
carries no audit logic.
"""

from __future__ import annotations

from pathlib import Path

from mvp.agents.persona_runtime import PersonaResponse, PersonaRuntime


PERSONA_ID = "citation_auditor"

_runtime = PersonaRuntime()


def call(user_message: str, *, cache_dir: Path | None = None) -> PersonaResponse:
    """Invoke the citation_auditor persona with ``user_message``."""
    return _runtime.call(PERSONA_ID, user_message, cache_dir=cache_dir)


__all__ = ["PERSONA_ID", "call"]
