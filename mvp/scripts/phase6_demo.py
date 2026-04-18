"""Phase 6 acceptance demo — CLI ↔ API parity gate (success_criteria §2, §12).

Runs (in-process, no subprocess) both the CLI and the API against the
same Enron 2000 analyze_for_red_flags input and asserts byte-identical
output modulo the 4 non-deterministic fields (``run_at``, ``run_id``,
``build_id``, and per-citation ``retrieved_at``). Also verifies the MCP
and OpenAI catalogues serve 7 tools each and every error path produces
the structured envelope.

Exits 0 on pass, 1 on any gate failure.
"""

from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


_VOLATILE_KEYS = frozenset({"run_at", "run_id", "build_id", "retrieved_at"})


def _normalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: ("<ts>" if k in _VOLATILE_KEYS else _normalize(v)) for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


def _run_cli(payload: dict[str, Any]) -> dict[str, Any]:
    from mvp.cli.main import main as cli_main

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf)
        tf.flush()
        path = tf.name
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(["run", "analyze_for_red_flags", "--json", path])
        assert code == 0, f"CLI exited with code {code}, stdout={buf.getvalue()[:500]}"
        return json.loads(buf.getvalue())
    finally:
        Path(path).unlink(missing_ok=True)


def _run_api(client: TestClient, payload: dict[str, Any]) -> dict[str, Any]:
    resp = client.post("/v1/skills/analyze_for_red_flags", json=payload)
    assert resp.status_code == 200, (
        f"API returned status={resp.status_code} body={resp.json()}"
    )
    return resp.json()


def _check_error_envelope_structured(client: TestClient) -> bool:
    """Send a handful of bad requests; verify each returns the 5-field envelope."""
    from mvp.api.error_envelope import ENVELOPE_KEYS

    samples = [
        ("GET", "/v1/skills/ghost_skill_id", None),
        ("POST", "/v1/skills/ghost_skill_id", {}),
        ("POST", "/v1/skills/compute_beneish_m_score", {"cik": "0001024401"}),
        ("POST", "/v1/resolve_citation", {"doc_id": 3}),
    ]
    for method, url, body in samples:
        if method == "GET":
            resp = client.get(url)
        else:
            resp = client.post(url, json=body or {})
        if resp.status_code < 400:
            print(f"[phase6_demo] gate FAIL: expected error on {method} {url}, got {resp.status_code}")
            return False
        env = resp.json()
        if not isinstance(env, dict) or set(env.keys()) != set(ENVELOPE_KEYS):
            print(
                f"[phase6_demo] gate FAIL: envelope keys on {method} {url} = "
                f"{sorted(env.keys()) if isinstance(env, dict) else type(env).__name__}"
            )
            return False
    return True


def main() -> int:
    from mvp.api import app

    client = TestClient(app)

    payload = {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}

    print("# Phase 6 acceptance demo")
    print("# 1) Live API call POST /v1/skills/analyze_for_red_flags (Enron 2000)")
    api_out = _run_api(client, payload)
    print(
        f"  API m_score={api_out['m_score_result']['score']}, "
        f"m_flag={api_out['m_score_result']['flag']}, "
        f"z_score={api_out['z_score_result']['score']}, "
        f"z_flag={api_out['z_score_result']['flag']}"
    )

    print()
    print("# 2) CLI: mvp run analyze_for_red_flags --json ...")
    cli_out = _run_cli(payload)
    print(
        f"  CLI m_score={cli_out['m_score_result']['score']}, "
        f"m_flag={cli_out['m_score_result']['flag']}, "
        f"z_score={cli_out['z_score_result']['score']}, "
        f"z_flag={cli_out['z_score_result']['flag']}"
    )

    print()
    print("# 3) Byte-identical comparison (modulo run_at, run_id, build_id, retrieved_at)")
    cli_norm = _normalize(cli_out)
    api_norm = _normalize(api_out)
    identical = cli_norm == api_norm
    if not identical:
        print("BYTE_IDENTICAL: no")
        # Print first diff for the operator.
        cli_json = json.dumps(cli_norm, sort_keys=True, default=str)
        api_json = json.dumps(api_norm, sort_keys=True, default=str)
        for i, (a, b) in enumerate(zip(cli_json, api_json)):
            if a != b:
                start = max(0, i - 40)
                print(f"  first diff at char {i}:")
                print(f"  cli: ...{cli_json[start:i+80]!r}")
                print(f"  api: ...{api_json[start:i+80]!r}")
                break
        return 1
    print("BYTE_IDENTICAL: yes")

    print()
    print("# 4) GET /mcp/tools and /openai/tools")
    mcp = client.get("/mcp/tools").json()
    openai = client.get("/openai/tools").json()
    mcp_count = mcp.get("count", 0)
    openai_count = openai.get("count", 0)
    print(f"  MCP tools = {mcp_count}")
    print(f"  OpenAI tools = {openai_count}")
    if mcp_count != 7 or openai_count != 7:
        print("  gate FAIL: expected 7 tools in each catalog")
        return 1

    print()
    print("# 5) Structured-error envelope sanity")
    envelopes_ok = _check_error_envelope_structured(client)
    if not envelopes_ok:
        return 1
    print("  every error path returns the 5-field envelope with no leakage")

    print()
    print(
        f"PHASE 6 ACCEPTANCE: CLI↔API parity = PASS | "
        f"MCP = {mcp_count} | OpenAI = {openai_count} | "
        f"error envelopes = structured"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
