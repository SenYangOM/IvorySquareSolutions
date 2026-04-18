"""Phase 4 live demo.

Runs ``analyze_for_red_flags`` end-to-end against Enron 2000, persists
the JSON output under ``data/demo_outputs/`` (the canonical acceptance
artifact per ``success_criteria.md`` §1), and prints the MCP + OpenAI
catalogs so a reviewer can eyeball all 7 agent-facing specs in one
pass.

Run::

    .venv/bin/python -m mvp.scripts.phase4_demo

Exits 0 on success and prints the Enron JSON on stdout.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from mvp.skills.registry import default_registry


_MVP_ROOT = Path(__file__).resolve().parents[1]
_DEMO_OUT_DIR = _MVP_ROOT / "data" / "demo_outputs"
_DEMO_OUT_PATH = _DEMO_OUT_DIR / "enron_2000_analyze_for_red_flags.json"


def _dump(obj: object) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def main() -> int:
    registry = default_registry()

    # 1. Run the composite skill for the canonical Enron 2000 case.
    skill = registry.get("analyze_for_red_flags")
    result = skill.run({"cik": "0001024401", "fiscal_year_end": "2000-12-31"})
    if "error" in result:
        print("[phase4_demo] composite skill returned an error envelope:", file=sys.stderr)
        print(_dump(result["error"]), file=sys.stderr)
        return 1

    _DEMO_OUT_DIR.mkdir(parents=True, exist_ok=True)
    _DEMO_OUT_PATH.write_text(_dump(result) + "\n", encoding="utf-8")
    print("# Enron 2000 analyze_for_red_flags — full JSON")
    print(_dump(result))
    print()
    print(f"# Written to {_DEMO_OUT_PATH}")
    print()

    # 2. Per-skill summary lines.
    print("# Per-skill summary (skill_id / version / inputs-keys / outputs-keys / cost)")
    for manifest in registry.list_skills():
        input_keys = sorted(
            (manifest.inputs.get("properties") or {}).keys()
        )
        output_keys = sorted(
            (manifest.outputs.get("properties") or {}).keys()
        )
        cost = manifest.cost_estimate
        print(
            f"- {manifest.skill_id:34s} v{manifest.version} "
            f"inputs={input_keys} outputs={output_keys} "
            f"cost=(tokens={cost.llm_tokens_per_call}, "
            f"external={cost.external_api_calls}, "
            f"latency={cost.typical_latency_ms}ms)"
        )
    print()

    # 3. MCP catalog.
    mcp = registry.mcp_catalog()
    print(f"# MCP tool catalog ({len(mcp)} entries)")
    print(_dump(mcp))
    print()

    # 4. OpenAI catalog.
    openai = registry.openai_catalog()
    print(f"# OpenAI tool-use catalog ({len(openai)} entries)")
    print(_dump(openai))
    print()

    # 5. Sanity: CLI and registry invocation produce byte-identical bodies
    #    (modulo timestamps + run_id). We redact those fields and compare.
    cli_result = registry.get("analyze_for_red_flags").run(
        {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}
    )
    redacted_a = _redact_timestamps(result)
    redacted_b = _redact_timestamps(cli_result)
    if redacted_a != redacted_b:
        print(
            "[phase4_demo] WARNING: two consecutive runs of the composite "
            "produced different output bodies (after timestamp redaction). "
            "This breaks P3 determinism. Investigate before proceeding.",
            file=sys.stderr,
        )
        return 1
    print("# Determinism sanity: two registry runs → byte-identical output bodies (modulo timestamps).")
    return 0


def _redact_timestamps(obj: object) -> object:
    """Return a copy of ``obj`` with ``run_id`` / ``run_at`` / ``retrieved_at``
    fields replaced with a sentinel, for byte-level diffing.
    """
    if isinstance(obj, dict):
        out: dict[str, object] = {}
        for k, v in obj.items():
            if k in ("run_id", "run_at", "retrieved_at"):
                out[k] = "<redacted>"
            else:
                out[k] = _redact_timestamps(v)
        return out
    if isinstance(obj, list):
        return [_redact_timestamps(x) for x in obj]
    return obj


if __name__ == "__main__":
    sys.exit(main())
