"""LLM-persona runtime. Loads YAML configs from ``mvp/human_layer/personas``.

The runtime class :class:`PersonaRuntime` and the declarative
:class:`Persona` schema live in :mod:`mvp.agents.persona_runtime`. Each
of the four MVP personas has a thin wrapper module
(:mod:`~mvp.agents.accounting_expert`,
:mod:`~mvp.agents.quant_finance_methodologist`,
:mod:`~mvp.agents.evaluation_agent`,
:mod:`~mvp.agents.citation_auditor`) whose only job is to hold a
``PERSONA_ID`` constant and delegate a ``call()`` to a module-level
runtime instance.
"""

from mvp.agents.persona_runtime import (
    Persona,
    PersonaProvenance,
    PersonaResponse,
    PersonaRuntime,
    load_persona,
)


__all__ = [
    "Persona",
    "PersonaProvenance",
    "PersonaResponse",
    "PersonaRuntime",
    "load_persona",
]
