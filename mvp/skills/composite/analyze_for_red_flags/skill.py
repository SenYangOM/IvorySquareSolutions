"""analyze_for_red_flags — L4 composite skill.

Glues the M-score and Altman Z pipelines into a single agent-facing
call. For a given (cik, fiscal_year_end):

1. ``registry.get("compute_beneish_m_score").run(...)`` → m_score_result.
2. ``registry.get("compute_altman_z_score").run(...)``  → z_score_result.
3. ``registry.get("interpret_m_score_components").run({..., components: m_score_result.components})``
   → m interpretation.
4. ``registry.get("interpret_z_score_components").run({..., components: z_score_result.components, z_score, z_flag})``
   → z interpretation.
5. Assemble the combined output per success_criteria §2.

All sub-skill calls go through the registry (P3 "single seam"); there
is no direct import of the sub-skill classes. Version pins come from
the manifest's ``dependencies.skills`` block.

If a sub-skill call returns a structured error envelope (``{"error": {...}}``),
this skill bubbles the error up as its own error rather than emitting a
partial composite output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.skills.registry import default_registry


class AnalyzeForRedFlags(Skill):
    id = "analyze_for_red_flags"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])
        registry = default_registry()

        # 1) Beneish M-score
        m_skill = registry.get("compute_beneish_m_score")
        m_raw = m_skill.run({"cik": cik, "fiscal_year_end": fye})
        _bubble_sub_error(m_raw, sub_skill_id="compute_beneish_m_score")

        # 2) Altman Z-score
        z_skill = registry.get("compute_altman_z_score")
        z_raw = z_skill.run({"cik": cik, "fiscal_year_end": fye})
        _bubble_sub_error(z_raw, sub_skill_id="compute_altman_z_score")

        # 3) M-score interpretations
        mi_skill = registry.get("interpret_m_score_components")
        mi_raw = mi_skill.run(
            {
                "cik": cik,
                "fiscal_year_end": fye,
                "components": m_raw["components"],
                "source_confidence": m_raw.get("confidence"),
            }
        )
        _bubble_sub_error(mi_raw, sub_skill_id="interpret_m_score_components")

        # 4) Z-score interpretations
        zi_skill = registry.get("interpret_z_score_components")
        zi_raw = zi_skill.run(
            {
                "cik": cik,
                "fiscal_year_end": fye,
                "components": z_raw["components"],
                "source_confidence": z_raw.get("confidence"),
                "z_score": z_raw.get("z_score"),
                "z_flag": z_raw.get("flag"),
            }
        )
        _bubble_sub_error(zi_raw, sub_skill_id="interpret_z_score_components")

        # 5) Assemble output per success_criteria §2.
        m_result_block = {
            "score": m_raw.get("m_score"),
            "flag": m_raw.get("flag"),
            "components": m_raw.get("components"),
            "interpretations": mi_raw.get("component_interpretations", []),
            "overall_interpretation": mi_raw.get("overall_interpretation", ""),
            "citations": _merge_citations(m_raw.get("citations", []), mi_raw.get("citations", [])),
            "confidence": mi_raw.get("confidence", m_raw.get("confidence")),
            "warnings": (m_raw.get("warnings") or []) + (mi_raw.get("warnings") or []),
        }
        z_result_block = {
            "score": z_raw.get("z_score"),
            "flag": z_raw.get("flag"),
            "components": z_raw.get("components"),
            "interpretations": zi_raw.get("component_interpretations", []),
            "overall_interpretation": zi_raw.get("overall_interpretation", ""),
            "citations": _merge_citations(z_raw.get("citations", []), zi_raw.get("citations", [])),
            "confidence": zi_raw.get("confidence", z_raw.get("confidence")),
            "warnings": (z_raw.get("warnings") or []) + (zi_raw.get("warnings") or []),
        }
        # sub_skill_versions is populated from each sub-skill's stamped provenance.
        sub_versions = {
            sid: _extract_version(raw)
            for sid, raw in (
                ("compute_beneish_m_score", m_raw),
                ("compute_altman_z_score", z_raw),
                ("interpret_m_score_components", mi_raw),
                ("interpret_z_score_components", zi_raw),
            )
        }
        composite_manifest = self.manifest
        provenance = {
            "composite_skill_id": "analyze_for_red_flags",
            "composite_version": composite_manifest.version,
            "rule_set_version": "0.1.0",
            "build_id": _read_build_id(),
            "run_at": datetime.now(timezone.utc).isoformat(),
            "sub_skill_versions": sub_versions,
            "inputs_echo": {"cik": cik, "fiscal_year_end": fye},
        }
        return {
            "m_score_result": m_result_block,
            "z_score_result": z_result_block,
            "provenance": provenance,
        }


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _bubble_sub_error(raw: dict[str, Any], *, sub_skill_id: str) -> None:
    """If ``raw`` is an error envelope, re-raise as a :class:`_SubSkillError`."""
    err = raw.get("error") if isinstance(raw, dict) else None
    if err is None:
        return
    code = str(err.get("error_code") or "sub_skill_error")
    message = str(err.get("human_message") or "sub-skill returned an error envelope")
    retry_safe = bool(err.get("retry_safe", False))
    raise _SubSkillError(
        f"sub-skill {sub_skill_id!r} failed: {code}: {message}",
        error_code=f"sub_skill_error.{code}",
        retry_safe=retry_safe,
    )


def _extract_version(raw: dict[str, Any]) -> str:
    prov = raw.get("provenance") if isinstance(raw, dict) else None
    if isinstance(prov, dict):
        v = prov.get("skill_version")
        if isinstance(v, str):
            return v
    return "?"


def _merge_citations(
    primary: list[dict[str, Any]], secondary: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge two citation lists deduplicated on ``(doc_id, locator)``."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for lst in (primary, secondary):
        for c in lst:
            if not isinstance(c, dict):
                continue
            key = (str(c.get("doc_id")), str(c.get("locator")))
            if key in seen:
                continue
            seen.add(key)
            out.append(c)
    return out


def _read_build_id() -> str:
    """Read ``BUILD_STATE.json`` and derive a short build id string."""
    state = Path(__file__).resolve().parents[3] / "BUILD_STATE.json"
    if not state.is_file():
        return "unknown"
    try:
        import json as _json

        data = _json.loads(state.read_text(encoding="utf-8"))
        started = str(data.get("started_at", "unknown"))
        phase = str(data.get("current_phase", "?"))
        return f"{started}/phase-{phase}"
    except Exception:
        return "unknown"


class _SubSkillError(LibError):
    error_code = "sub_skill_error"
    error_category = ErrorCategory.INTERNAL
    retry_safe = False


SKILL = AnalyzeForRedFlags
