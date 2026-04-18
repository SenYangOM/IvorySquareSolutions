"""Skill registry — the single seam CLI and API both consume.

Per Operating Principle P3 ("CLI is a thin wrapper over the same
registry the API uses"), the registry is the exclusive dispatch layer
for every skill call in the MVP. A skill is only callable through the
registry; composite skills invoke sub-skills through the registry (not
by direct import) so version-pinning and audit-stamping happen uniformly.

Auto-discovery
--------------
On first use, :meth:`Registry.bootstrap` walks
``mvp/skills/{fundamental,interpretation,paper_derived,composite}/<skill_id>/skill.py``
and imports each. Every discovered module is expected to expose a
``SKILL`` attribute bound to a :class:`Skill` subclass. The class's
``id`` + manifest ``version`` is used as the registration key.

Version routing
---------------
:meth:`Registry.get` resolves ``skill_id`` to the **latest** registered
version by semver ordering. Passing an explicit ``version`` argument
pins to that exact version. The registry is append-only within a
process — re-bootstrapping is a no-op after the first call.

Catalogs
--------
:meth:`Registry.mcp_catalog` and :meth:`Registry.openai_catalog` return
lists of tool specs suitable for handing to an MCP-compatible or
OpenAI-compatible agent. Each spec projects from the same
:class:`SkillManifest`, so CLI / API / MCP / OpenAI cannot drift apart.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Any, Iterable

from .manifest_schema import SkillManifest
from ._base import Skill

_SKILL_SUBPACKAGES = (
    "mvp.skills.fundamental",
    "mvp.skills.interpretation",
    "mvp.skills.paper_derived",
    "mvp.skills.composite",
)


class Registry:
    """Discovery + dispatch registry for all MVP skills.

    A single :class:`Registry` instance is the recommended shared seam;
    :func:`default_registry` returns a cached singleton for CLI / API /
    test use.
    """

    def __init__(self) -> None:
        self._by_id_version: dict[tuple[str, str], type[Skill]] = {}
        self._bootstrapped = False

    # ------------------------------------------------------------------
    # Registration.
    # ------------------------------------------------------------------

    def register(self, skill_cls: type[Skill]) -> None:
        """Register a single :class:`Skill` subclass.

        Raises :exc:`ValueError` if the class's ``id`` does not match
        the manifest YAML's ``skill_id``, or if the same ``(id, version)``
        pair has already been registered (double-registration is a bug).
        """
        instance = skill_cls()
        manifest = instance.manifest
        if manifest.skill_id != skill_cls.id:
            raise ValueError(
                f"skill class {skill_cls.__name__}: id={skill_cls.id!r} does not "
                f"match manifest.skill_id={manifest.skill_id!r}"
            )
        key = (manifest.skill_id, manifest.version)
        if key in self._by_id_version:
            raise ValueError(
                f"skill {manifest.skill_id!r} version {manifest.version} "
                "is already registered"
            )
        self._by_id_version[key] = skill_cls

    def bootstrap(self) -> None:
        """Walk the skills sub-packages and register every ``SKILL`` found.

        Idempotent within a process — subsequent calls are no-ops.
        Each subpackage of ``mvp.skills.<layer>`` is iterated; every
        ``skill`` submodule must expose a ``SKILL`` constant. Packages
        without a ``skill`` submodule are silently skipped (layer
        package itself, ``_base``, ``registry``, etc).
        """
        if self._bootstrapped:
            return
        for sub in _SKILL_SUBPACKAGES:
            try:
                layer_pkg = importlib.import_module(sub)
            except ModuleNotFoundError:
                continue
            pkg_path = getattr(layer_pkg, "__path__", None)
            if not pkg_path:
                continue
            for _finder, modname, ispkg in pkgutil.iter_modules(pkg_path):
                if not ispkg:
                    continue
                full_pkg = f"{sub}.{modname}"
                # Each concrete skill lives under <layer>/<skill_id>/skill.py.
                try:
                    skill_mod = importlib.import_module(f"{full_pkg}.skill")
                except ModuleNotFoundError:
                    continue
                candidate = getattr(skill_mod, "SKILL", None)
                if candidate is None:
                    continue
                if not (isinstance(candidate, type) and issubclass(candidate, Skill)):
                    raise ValueError(
                        f"{full_pkg}.skill.SKILL must be a Skill subclass, "
                        f"got {type(candidate).__name__}"
                    )
                self.register(candidate)
        self._bootstrapped = True

    # ------------------------------------------------------------------
    # Lookup.
    # ------------------------------------------------------------------

    def get(self, skill_id: str, *, version: str | None = None) -> Skill:
        """Instantiate and return the requested skill.

        Parameters
        ----------
        skill_id:
            The skill's ``skill_id``.
        version:
            Optional exact version pin (e.g. ``"0.1.0"``). When ``None``,
            the latest registered version wins by semver ordering.

        Raises
        ------
        KeyError
            If no skill with that ``skill_id`` (or that exact version) is
            registered.
        """
        self.bootstrap()
        if version is not None:
            key = (skill_id, version)
            if key not in self._by_id_version:
                raise KeyError(
                    f"no skill registered with id={skill_id!r} version={version!r}"
                )
            return self._by_id_version[key]()
        candidates = [
            (v, cls) for (sid, v), cls in self._by_id_version.items() if sid == skill_id
        ]
        if not candidates:
            raise KeyError(f"no skill registered with id={skill_id!r}")
        candidates.sort(key=lambda item: _semver_tuple(item[0]), reverse=True)
        _, cls = candidates[0]
        return cls()

    def list_skills(self) -> list[SkillManifest]:
        """Return every registered skill's manifest, sorted by ``(id, version)``.

        For agent-facing callers the :meth:`mcp_catalog` / :meth:`openai_catalog`
        projections are usually more useful; this list is the raw
        manifest stream for admin / audit use.
        """
        self.bootstrap()
        result: list[SkillManifest] = []
        for (_sid, _v), cls in sorted(
            self._by_id_version.items(),
            key=lambda item: (item[0][0], _semver_tuple(item[0][1])),
        ):
            result.append(cls().manifest)
        return result

    def ids(self) -> list[str]:
        """Return the sorted set of distinct registered skill ids."""
        self.bootstrap()
        return sorted({sid for (sid, _v) in self._by_id_version})

    # ------------------------------------------------------------------
    # Agent-facing catalogs.
    # ------------------------------------------------------------------

    def mcp_catalog(self) -> list[dict[str, Any]]:
        """MCP tool catalog — one spec per skill (latest version per id)."""
        return [_latest_manifest(m_list).as_mcp_tool() for m_list in self._grouped_by_id()]

    def openai_catalog(self) -> list[dict[str, Any]]:
        """OpenAI tool-use catalog — one spec per skill (latest version per id)."""
        return [_latest_manifest(m_list).as_openai_tool() for m_list in self._grouped_by_id()]

    def _grouped_by_id(self) -> Iterable[list[SkillManifest]]:
        manifests = self.list_skills()
        by_id: dict[str, list[SkillManifest]] = {}
        for m in manifests:
            by_id.setdefault(m.skill_id, []).append(m)
        # Iterate in sorted id order for deterministic output.
        for sid in sorted(by_id):
            yield by_id[sid]


# ---------------------------------------------------------------------------
# Module-level convenience + helpers.
# ---------------------------------------------------------------------------


_DEFAULT_REGISTRY: Registry | None = None


def default_registry() -> Registry:
    """Return the process-wide singleton registry (lazy-bootstrapped)."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = Registry()
        _DEFAULT_REGISTRY.bootstrap()
    return _DEFAULT_REGISTRY


def reset_default_registry() -> None:
    """Reset the process-wide registry singleton (tests use this)."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None


def _semver_tuple(v: str) -> tuple[int, int, int]:
    parts = v.split(".")
    if len(parts) != 3:
        return (0, 0, 0)
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return (0, 0, 0)


def _latest_manifest(manifests: list[SkillManifest]) -> SkillManifest:
    return max(manifests, key=lambda m: _semver_tuple(m.version))


# Re-export the skill layer roots so callers can discover them via a
# single import path.
SKILL_ROOT = Path(__file__).resolve().parent


__all__ = [
    "Registry",
    "SKILL_ROOT",
    "default_registry",
    "reset_default_registry",
]
