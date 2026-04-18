"""Unit tests for the Phase 6 FastAPI stub.

Uses :class:`fastapi.testclient.TestClient` (ASGI in-process transport) —
no port binding, no subprocess, hermetic. Every declared route has at
least one happy-path and one error-path assertion here.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from mvp.api import app
from mvp.api.error_envelope import ENVELOPE_KEYS


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


# ---------------------------------------------------------------------------
# Catalog routes.
# ---------------------------------------------------------------------------


def test_list_skills_returns_all_registered_entries(client: TestClient) -> None:
    """Post-MVP: the catalogue grows one-per-paper as workshop-onboarding
    lands paper_examples/* skills. We assert ≥7 (the MVP floor) and that
    the expected MVP ids are present. The count can tick up as papers
    are onboarded; that is a feature, not a regression."""
    resp = client.get("/v1/skills")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 7
    ids = {entry["skill_id"] for entry in data}
    # MVP 7 skills must always be present.
    for mvp_id in (
        "extract_canonical_statements",
        "extract_mdna",
        "compute_beneish_m_score",
        "compute_altman_z_score",
        "interpret_m_score_components",
        "interpret_z_score_components",
        "analyze_for_red_flags",
    ):
        assert mvp_id in ids, f"MVP skill {mvp_id!r} missing from catalogue"
    for entry in data:
        for key in ("skill_id", "version", "layer", "status",
                    "maintainer_persona", "description_for_llm"):
            assert key in entry, f"list entry missing {key!r}"


def test_get_manifest_returns_full_manifest(client: TestClient) -> None:
    resp = client.get("/v1/skills/compute_beneish_m_score")
    assert resp.status_code == 200
    data = resp.json()
    assert data["skill_id"] == "compute_beneish_m_score"
    assert data["layer"] == "paper_derived"
    # Must include JSON-schema input/output blocks.
    assert "inputs" in data and isinstance(data["inputs"], dict)
    assert "outputs" in data and isinstance(data["outputs"], dict)
    assert "provenance" in data
    assert "citation_contract" in data


def test_get_manifest_unknown_returns_404_envelope(client: TestClient) -> None:
    resp = client.get("/v1/skills/does_not_exist")
    assert resp.status_code == 404
    body = resp.json()
    for key in ENVELOPE_KEYS:
        assert key in body, f"envelope missing {key!r}"
    assert body["error_code"] == "skill_not_found"
    assert body["error_category"] == "input_validation"
    assert "does_not_exist" in body["human_message"]
    assert body["retry_safe"] is False


def test_mcp_catalog_shape(client: TestClient) -> None:
    resp = client.get("/mcp/tools")
    assert resp.status_code == 200
    body = resp.json()
    # MCP catalogue envelope + at least 7 tools (MVP floor). Paper-
    # onboarding iterations grow this count.
    assert body["count"] >= 7
    assert isinstance(body["tools"], list) and len(body["tools"]) >= 7
    assert body["count"] == len(body["tools"])
    for tool in body["tools"]:
        # MCP tool-spec required fields (public spec 2024+).
        assert set(tool.keys()) == {"name", "description", "inputSchema"}, (
            f"tool keys mismatch: {tool.keys()}"
        )
        assert isinstance(tool["name"], str) and tool["name"]
        assert isinstance(tool["description"], str) and len(tool["description"]) >= 40
        assert tool["inputSchema"].get("type") == "object"


def test_openai_catalog_shape(client: TestClient) -> None:
    resp = client.get("/openai/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] >= 7
    assert isinstance(body["tools"], list) and len(body["tools"]) >= 7
    assert body["count"] == len(body["tools"])
    for tool in body["tools"]:
        # OpenAI tool-use spec requires {"type": "function", "function": {...}}.
        assert tool["type"] == "function"
        fn = tool["function"]
        assert isinstance(fn["name"], str) and fn["name"]
        assert isinstance(fn["description"], str)
        assert fn["parameters"].get("type") == "object"


# ---------------------------------------------------------------------------
# Skill dispatch.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_run_skill_happy_path(client: TestClient) -> None:
    resp = client.post(
        "/v1/skills/compute_beneish_m_score",
        json={"cik": "0001024401", "fiscal_year_end": "2000-12-31"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["flag"] == "manipulator_likely"
    assert abs(body["m_score"] - -0.2422) < 1e-3
    assert "components" in body and len(body["components"]) == 8
    assert isinstance(body["citations"], list) and len(body["citations"]) > 0
    assert "provenance" in body
    assert "run_at" in body["provenance"]


def test_run_skill_unknown_id_returns_404(client: TestClient) -> None:
    resp = client.post("/v1/skills/nonexistent_skill", json={"cik": "0001024401"})
    assert resp.status_code == 404
    body = resp.json()
    for key in ENVELOPE_KEYS:
        assert key in body
    assert body["error_code"] == "skill_not_found"


def test_run_skill_bad_input_returns_envelope(client: TestClient) -> None:
    # Missing required 'fiscal_year_end'.
    resp = client.post(
        "/v1/skills/compute_beneish_m_score", json={"cik": "0001024401"}
    )
    assert resp.status_code == 400
    body = resp.json()
    for key in ENVELOPE_KEYS:
        assert key in body
    assert body["error_code"] == "input_validation"


def test_run_skill_non_json_body_returns_400(client: TestClient) -> None:
    resp = client.post(
        "/v1/skills/compute_beneish_m_score",
        content=b"this is not JSON",
        headers={"content-type": "application/json"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["error_code"] == "input_validation"
    assert "JSON" in body["human_message"] or "json" in body["human_message"].lower()


def test_run_skill_unknown_cik_returns_envelope(client: TestClient) -> None:
    # A well-formed CIK that doesn't correspond to any sample filing
    # triggers a typed StoreError inside the skill pipeline, which the
    # skill base class wraps into its error envelope. The API then
    # translates to the public envelope.
    resp = client.post(
        "/v1/skills/compute_beneish_m_score",
        json={"cik": "0009999999", "fiscal_year_end": "2020-12-31"},
    )
    # Some form of error, never a 200.
    assert resp.status_code >= 400
    body = resp.json()
    for key in ENVELOPE_KEYS:
        assert key in body


# ---------------------------------------------------------------------------
# Citation resolution.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_resolve_citation_happy_path(client: TestClient) -> None:
    # Apple FY2023 revenue citation — known to resolve through canonical statements.
    resp = client.post(
        "/v1/resolve_citation",
        json={
            "doc_id": "0000320193/0000320193-23-000106",
            "locator": "0000320193/0000320193-23-000106::income_statement::revenue",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved"] is True
    assert "revenue" in body["passage_text"]
    assert "Canonical line item" in body["surrounding_context"]


def test_resolve_citation_malformed_body(client: TestClient) -> None:
    resp = client.post("/v1/resolve_citation", json={"doc_id": 123})
    assert resp.status_code == 400
    body = resp.json()
    for key in ENVELOPE_KEYS:
        assert key in body


def test_resolve_citation_unknown_doc_id(client: TestClient) -> None:
    # A well-formed citation whose doc_id doesn't match the filing or
    # market-data shapes: resolver returns a structured unresolved dict
    # (resolved=False + reason) rather than a 400 — the input itself is
    # syntactically valid, just doesn't point at a known artifact.
    resp = client.post(
        "/v1/resolve_citation",
        json={
            "doc_id": "0009999999/9999999999-99-999999",
            "locator": "0009999999/9999999999-99-999999::income_statement::revenue",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved"] is False
    assert "reason" in body


# ---------------------------------------------------------------------------
# Eval endpoints.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_eval_latest_shape(client: TestClient) -> None:
    # Phase 5 seeded real eval reports under mvp/eval/reports/. The
    # latest-by-mtime must return with the EvalReport shape.
    resp = client.get("/v1/eval/latest")
    assert resp.status_code == 200
    body = resp.json()
    assert "run_id" in body and "run_at" in body
    assert "cases" in body and isinstance(body["cases"], list)
    assert "metrics" in body


# ---------------------------------------------------------------------------
# Health.
# ---------------------------------------------------------------------------


def test_healthz_returns_expected_shape(client: TestClient) -> None:
    resp = client.get("/healthz")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "build_id" in body
    assert "phase" in body
