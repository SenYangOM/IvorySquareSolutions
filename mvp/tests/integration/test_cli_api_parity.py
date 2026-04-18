"""CLI ↔ API parity — THE gate per ``success_criteria.md`` §2, §7 L5 row, §12.

For each of the 7 MVP skills, run the same input payload through:

1. The CLI — invoking ``mvp.cli.main.main`` in-process (same registry).
2. The FastAPI stub — via :class:`fastapi.testclient.TestClient`
   (``ASGITransport`` in-process, no port binding).

Assert the output JSON is byte-identical modulo a fixed set of
non-deterministic timestamp/id fields. The spec names three
(``provenance.run_at``, ``provenance.run_id``, ``provenance.build_id``);
we additionally mask every citation's ``retrieved_at`` because that
field is minted at canonical-statement-read time inside the skill and
changes per invocation — the Phase 4 determinism sanity-check uses the
same mask. This parity property is what Operating Principle P3 requires
of every skill: two call-surfaces invoke the one registry and produce
the same substantive output.
"""

from __future__ import annotations

import copy
import io
import json
from contextlib import redirect_stdout
from typing import Any

import pytest
from fastapi.testclient import TestClient

from mvp.api import app
from mvp.cli.main import main as cli_main

# Every test in this module exercises the CLI/API surface against the real
# registry and live filings (the 10-filing ingested corpus). On a fresh
# clone where `data/filings/` is empty, the registry can load manifests
# but every `.run()` call fails with UnknownFiling. Mark the whole module
# so the suite skips cleanly until `mvp ingest filings --batch all` runs.
pytestmark = pytest.mark.requires_live_data


# ---------------------------------------------------------------------------
# Fixtures.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# Keys to redact at any depth before comparing — these are timestamps or
# per-call identifiers that legitimately differ between two invocations
# of the same deterministic skill.
_VOLATILE_KEYS = frozenset({"run_at", "run_id", "build_id", "retrieved_at"})


def _normalize(obj: Any) -> Any:
    """Recursively replace every ``_VOLATILE_KEYS`` value with ``<ts>``."""
    if isinstance(obj, dict):
        out: dict[str, Any] = {}
        for k, v in obj.items():
            if k in _VOLATILE_KEYS:
                out[k] = "<ts>"
            else:
                out[k] = _normalize(v)
        return out
    if isinstance(obj, list):
        return [_normalize(x) for x in obj]
    return obj


def _cli_run(skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Invoke the CLI's ``run`` subcommand in-process and return the parsed JSON.

    Uses ``--json`` to feed the full payload — matches the API body shape
    exactly. Writes the inputs to a temp file path via ``@``-syntax
    would require touching disk; the CLI's _load_json_payload accepts a
    plain path too, so we use a module-local StringIO trick: simpler to
    write to tmp and read back.
    """
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        "w", suffix=".json", delete=False, encoding="utf-8"
    ) as tf:
        json.dump(payload, tf)
        tf.flush()
        path = tf.name
    try:
        buf = io.StringIO()
        with redirect_stdout(buf):
            exit_code = cli_main(["run", skill_id, "--json", path])
        # Exit 0 on success, exit 1 if skill returned an error envelope.
        stdout = buf.getvalue()
        return {"exit_code": exit_code, "payload": json.loads(stdout)}
    finally:
        Path(path).unlink(missing_ok=True)


def _api_run(client: TestClient, skill_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    resp = client.post(f"/v1/skills/{skill_id}", json=payload)
    return {"status_code": resp.status_code, "payload": resp.json()}


def _assert_parity(cli: dict[str, Any], api: dict[str, Any], *, skill_id: str) -> None:
    """Assert the two payloads are byte-identical after volatile-key masking."""
    # Both surfaces must agree on success vs error.
    cli_is_error = isinstance(cli["payload"], dict) and "error" in cli["payload"]
    api_is_error = cli_is_error  # error would also show as 400+ on API
    if cli_is_error:
        # Not expected in these tests; still, surface the diff cleanly.
        pytest.fail(f"skill {skill_id!r} returned error envelope via CLI: {cli['payload']}")
    cli_norm = _normalize(cli["payload"])
    api_norm = _normalize(api["payload"])
    assert cli_norm == api_norm, _diff_preview(cli_norm, api_norm, skill_id)


def _diff_preview(cli: Any, api: Any, skill_id: str) -> str:
    """Build a short human-readable diff message for pytest failure output."""
    cli_json = json.dumps(cli, sort_keys=True, default=str)
    api_json = json.dumps(api, sort_keys=True, default=str)
    if cli_json == api_json:
        return "no diff (should not reach this)"
    # Find the first char that differs.
    for i, (a, b) in enumerate(zip(cli_json, api_json)):
        if a != b:
            start = max(0, i - 40)
            return (
                f"parity failure on {skill_id!r} at char {i}:\n"
                f"  cli: ...{cli_json[start:i+80]!r}\n"
                f"  api: ...{api_json[start:i+80]!r}"
            )
    return (
        f"parity failure on {skill_id!r}: length differs "
        f"(cli={len(cli_json)}, api={len(api_json)})"
    )


# ---------------------------------------------------------------------------
# Live-filing parity tests — the three the spec names explicitly.
# ---------------------------------------------------------------------------


def test_parity_extract_canonical_statements_apple_2023(client: TestClient) -> None:
    payload = {"cik": "0000320193", "fiscal_year_end": "2023-09-30"}
    cli = _cli_run("extract_canonical_statements", payload)
    api = _api_run(client, "extract_canonical_statements", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="extract_canonical_statements")


def test_parity_compute_beneish_m_score_enron_2000(client: TestClient) -> None:
    payload = {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}
    cli = _cli_run("compute_beneish_m_score", payload)
    api = _api_run(client, "compute_beneish_m_score", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="compute_beneish_m_score")


def test_parity_analyze_for_red_flags_enron_2000(client: TestClient) -> None:
    payload = {"cik": "0001024401", "fiscal_year_end": "2000-12-31"}
    cli = _cli_run("analyze_for_red_flags", payload)
    api = _api_run(client, "analyze_for_red_flags", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="analyze_for_red_flags")


# ---------------------------------------------------------------------------
# Remaining-four parity tests — using synthetic inputs per the spec.
# ---------------------------------------------------------------------------


def test_parity_extract_mdna_apple_2023(client: TestClient) -> None:
    payload = {"cik": "0000320193", "fiscal_year_end": "2023-09-30"}
    cli = _cli_run("extract_mdna", payload)
    api = _api_run(client, "extract_mdna", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="extract_mdna")


def test_parity_compute_altman_z_score_apple_2023(client: TestClient) -> None:
    payload = {"cik": "0000320193", "fiscal_year_end": "2023-09-30"}
    cli = _cli_run("compute_altman_z_score", payload)
    api = _api_run(client, "compute_altman_z_score", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="compute_altman_z_score")


def test_parity_interpret_m_score_components_synthetic(client: TestClient) -> None:
    # Synthetic components — doesn't require a filing read, exercises
    # the skill surface on its own.
    payload = {
        "cik": "0001024401",
        "fiscal_year_end": "2000-12-31",
        "components": {
            "DSRI": 1.5,
            "GMI": 1.1,
            "AQI": 1.2,
            "SGI": 1.3,
            "DEPI": 1.0,
            "SGAI": 1.1,
            "LVGI": 1.0,
            "TATA": 0.04,
        },
        "source_confidence": 0.85,
    }
    cli = _cli_run("interpret_m_score_components", payload)
    api = _api_run(client, "interpret_m_score_components", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="interpret_m_score_components")


def test_parity_interpret_z_score_components_synthetic(client: TestClient) -> None:
    payload = {
        "cik": "0001024401",
        "fiscal_year_end": "2000-12-31",
        "components": {"X1": 0.1, "X2": 0.2, "X3": 0.1, "X4": 1.5, "X5": 1.0},
        "source_confidence": 0.85,
        "z_score": 2.5,
        "z_flag": "grey_zone",
    }
    cli = _cli_run("interpret_z_score_components", payload)
    api = _api_run(client, "interpret_z_score_components", payload)
    assert cli["exit_code"] == 0
    assert api["status_code"] == 200
    _assert_parity(cli, api, skill_id="interpret_z_score_components")
