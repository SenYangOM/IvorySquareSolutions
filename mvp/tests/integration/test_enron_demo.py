"""End-to-end acceptance test for the Phase 4 Enron demo.

Runs ``analyze_for_red_flags`` for (cik=0001024401, fye=2000-12-31),
asserts both result blocks are present and consistent with expected
flags, every citation resolves through
``engine.citation_validator.resolve_citation``, and the output
validates against the composite skill's own output JSON schema.
Persists the actual JSON to
``data/demo_outputs/enron_2000_analyze_for_red_flags.json`` — that
file is the Phase 4 acceptance artifact per
``success_criteria.md`` §1.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import jsonschema
import pytest

from mvp.engine.citation_validator import resolve_citation
from mvp.lib.citation import Citation
from mvp.skills.manifest_schema import SkillManifest
from mvp.skills.registry import Registry, reset_default_registry

# The whole Enron demo module requires the ingested Enron filing (and the
# Apple negative control via the composite's sub-skills). Mark at module
# scope — no test here survives on a fresh clone without `mvp ingest`.
pytestmark = pytest.mark.requires_live_data


_MVP_ROOT = Path(__file__).resolve().parents[2]
_DEMO_OUT_DIR = _MVP_ROOT / "data" / "demo_outputs"


def _run_composite() -> dict:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r.get("analyze_for_red_flags").run(
        {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}
    )


def test_enron_composite_happy_path_and_persists() -> None:
    result = _run_composite()
    assert "error" not in result, f"composite returned error: {result.get('error')}"
    # Persist the acceptance artifact (success_criteria §1).
    _DEMO_OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = _DEMO_OUT_DIR / "enron_2000_analyze_for_red_flags.json"
    out_path.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, default=str) + "\n",
        encoding="utf-8",
    )
    assert out_path.is_file()


def test_enron_both_result_blocks_present() -> None:
    result = _run_composite()
    assert "error" not in result
    assert "m_score_result" in result
    assert "z_score_result" in result
    assert result["m_score_result"]["flag"] == "manipulator_likely"
    assert result["z_score_result"]["flag"] in {"grey_zone", "distress"}
    assert result["m_score_result"]["interpretations"], "must include M-component interpretations"
    assert result["z_score_result"]["interpretations"], "must include Z-component interpretations"


def test_enron_every_citation_resolves() -> None:
    result = _run_composite()
    assert "error" not in result
    all_cits: list[dict] = []
    for block in ("m_score_result", "z_score_result"):
        all_cits.extend(result[block].get("citations") or [])
    assert all_cits, "composite must produce some citations"
    unresolved: list[dict] = []
    for raw in all_cits:
        # Rehydrate the Citation from the dumped dict.
        rehydrated = Citation(**{**raw, "retrieved_at": datetime.fromisoformat(raw["retrieved_at"].replace("Z", "+00:00")) if isinstance(raw["retrieved_at"], str) else raw["retrieved_at"]})
        resolved = resolve_citation(rehydrated)
        if not resolved.get("resolved"):
            unresolved.append({"locator": raw["locator"], "reason": resolved.get("reason")})
    assert not unresolved, f"unresolved citations: {unresolved}"


def test_enron_validates_against_composite_output_schema() -> None:
    """The composite output must validate against its own output JSON schema."""
    result = _run_composite()
    manifest_path = (
        _MVP_ROOT / "skills" / "composite" / "analyze_for_red_flags" / "manifest.yaml"
    )
    manifest = SkillManifest.load_from_yaml(manifest_path)
    schema = manifest.outputs
    # Coerce non-JSON-native primitives (datetime values inside citations)
    # to strings so jsonschema's "string" type check is satisfied.
    coerced = json.loads(json.dumps(result, default=str))
    jsonschema.validate(instance=coerced, schema=schema)


def test_enron_flags_consistent_with_expected() -> None:
    """Sanity on the expected canonical outcome."""
    result = _run_composite()
    assert result["m_score_result"]["flag"] == "manipulator_likely"
    assert result["m_score_result"]["score"] is not None
    assert result["m_score_result"]["score"] > -1.78  # manipulator side of the cutoff
    z_flag = result["z_score_result"]["flag"]
    assert z_flag in {"grey_zone", "distress"}
    z = result["z_score_result"]["score"]
    assert z is not None and z < 2.99
