"""Unit tests for ``mvp.lib.cost_tracking``.

Tests cover the three concerns of the module:

1. Per-call recording — explicit ``record(...)`` calls write JSONL entries.
2. Aggregation — :func:`summarize` sums correctly across stages, personas,
   and models.
3. Wrapping — the context manager monkey-patches
   :class:`mvp.lib.llm.LlmClient.call` so calls inside the ``with`` block
   produce log entries automatically; the wrappers are removed on exit.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mvp.lib.cost_tracking import STAGE_IDS, summarize, track_cost
from mvp.lib.llm import LlmClient


def _populate_cache(
    client: LlmClient, system: str, messages: list[dict], payload: dict
) -> None:
    key = client._derive_key(system, messages, 0.0, 4000)
    cache_dir = client._cache_dir
    assert cache_dir is not None
    cache_dir.mkdir(parents=True, exist_ok=True)
    (cache_dir / f"{key}.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# Explicit-record path.
# ---------------------------------------------------------------------------


def test_record_appends_jsonl_line(tmp_path: Path) -> None:
    run_id = "test_run_1"
    with track_cost(
        "A1_extract",
        "quant_finance_methodologist",
        run_id,
        cost_log_root=tmp_path,
        paper_id="beneish_1999",
    ) as tr:
        tr.record(
            model="claude-opus-4-7",
            input_tokens=100,
            output_tokens=50,
            cache_read_tokens=10,
            cache_creation_tokens=5,
        )
    log_path = tmp_path / f"{run_id}.jsonl"
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["stage_id"] == "A1_extract"
    assert rec["persona"] == "quant_finance_methodologist"
    assert rec["model"] == "claude-opus-4-7"
    assert rec["input_tokens"] == 100
    assert rec["output_tokens"] == 50
    assert rec["cache_read_tokens"] == 10
    assert rec["cache_creation_tokens"] == 5
    assert rec["paper_id"] == "beneish_1999"


def test_record_creates_log_file_even_if_no_calls(tmp_path: Path) -> None:
    run_id = "empty_run"
    with track_cost("A1_extract", None, run_id, cost_log_root=tmp_path) as tr:
        # No record() calls.
        assert tr.log_path.is_file()
    log_path = tmp_path / f"{run_id}.jsonl"
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8") == ""


def test_record_persona_override(tmp_path: Path) -> None:
    run_id = "test_persona_override"
    with track_cost(
        "A6_verification", None, run_id, cost_log_root=tmp_path
    ) as tr:
        tr.record(
            model="claude-sonnet-4-6",
            input_tokens=50,
            output_tokens=25,
            persona_override="citation_auditor",
        )
        tr.record(
            model="claude-opus-4-7",
            input_tokens=200,
            output_tokens=100,
            persona_override="accounting_expert",
        )
    s = summarize(run_id, cost_log_root=tmp_path)
    assert s["n_calls"] == 2
    assert "citation_auditor" in s["by_persona"]
    assert "accounting_expert" in s["by_persona"]
    assert s["by_persona"]["citation_auditor"]["input_tokens"] == 50
    assert s["by_persona"]["accounting_expert"]["input_tokens"] == 200


# ---------------------------------------------------------------------------
# Aggregation.
# ---------------------------------------------------------------------------


def test_summarize_aggregates_per_stage_and_persona(tmp_path: Path) -> None:
    run_id = "agg_test"
    with track_cost(
        "A1_extract",
        "quant_finance_methodologist",
        run_id,
        cost_log_root=tmp_path,
        paper_id="beneish_1999",
    ) as tr:
        tr.record(model="claude-opus-4-7", input_tokens=1000, output_tokens=200)
        tr.record(model="claude-opus-4-7", input_tokens=500, output_tokens=100)
    with track_cost(
        "A2_digest",
        "accounting_expert",
        run_id,
        cost_log_root=tmp_path,
        paper_id="beneish_1999",
    ) as tr:
        tr.record(
            model="claude-opus-4-7",
            input_tokens=10000,
            output_tokens=2000,
            cache_read_tokens=3000,
            cache_creation_tokens=1000,
        )

    s = summarize(run_id, cost_log_root=tmp_path)
    assert s["n_calls"] == 3
    assert s["totals"]["input_tokens"] == 11500
    assert s["totals"]["output_tokens"] == 2300
    assert s["totals"]["cache_read_tokens"] == 3000
    assert s["totals"]["cache_creation_tokens"] == 1000
    assert s["totals"]["tokens_total"] == 17800

    assert s["by_stage"]["A1_extract"]["n_calls"] == 2
    assert s["by_stage"]["A1_extract"]["input_tokens"] == 1500
    assert s["by_stage"]["A2_digest"]["n_calls"] == 1
    assert s["by_stage"]["A2_digest"]["tokens_total"] == 16000

    assert s["by_persona"]["quant_finance_methodologist"]["n_calls"] == 2
    assert s["by_persona"]["accounting_expert"]["n_calls"] == 1

    assert s["by_model"]["claude-opus-4-7"]["n_calls"] == 3
    assert s["by_model"]["claude-opus-4-7"]["tokens_total"] == 17800

    assert s["paper_ids"] == ["beneish_1999"]
    assert s["unknown_stages"] == []


def test_summarize_unknown_stage(tmp_path: Path) -> None:
    run_id = "unk_stage"
    with track_cost(
        "Z9_custom", None, run_id, cost_log_root=tmp_path
    ) as tr:
        tr.record(model="claude-opus-4-7", input_tokens=10, output_tokens=5)
    s = summarize(run_id, cost_log_root=tmp_path)
    assert "Z9_custom" in s["unknown_stages"]


def test_summarize_missing_log_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        summarize("never_ran", cost_log_root=tmp_path)


# ---------------------------------------------------------------------------
# Monkey-patch wrapper.
# ---------------------------------------------------------------------------


def test_wrapping_llm_client_records_token_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real LlmClient call inside the with block produces a log entry."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cache_dir = tmp_path / "_llm_cache"
    client = LlmClient(model="claude-opus-4-7", cache_dir=cache_dir)
    _populate_cache(
        client,
        "sys-prompt",
        [{"role": "user", "content": "hello"}],
        {"text": "world", "input_tokens": 42, "output_tokens": 7},
    )

    cost_log_root = tmp_path / "cost"
    run_id = "wrap_test"

    with track_cost(
        "A2_digest",
        "quant_finance_methodologist",
        run_id,
        cost_log_root=cost_log_root,
        paper_id="beneish_1999",
    ):
        resp = client.call(
            "sys-prompt", [{"role": "user", "content": "hello"}]
        )
        assert resp.text == "world"
        assert resp.cache_hit is True
        assert resp.input_tokens == 42

    s = summarize(run_id, cost_log_root=cost_log_root)
    # Cache hit returns input_tokens=42 (we set them in the cache fixture);
    # the wrapper records what the LlmResponse carries.
    assert s["n_calls"] == 1
    assert s["by_stage"]["A2_digest"]["input_tokens"] == 42
    assert s["by_stage"]["A2_digest"]["output_tokens"] == 7
    assert s["by_persona"]["quant_finance_methodologist"]["n_calls"] == 1


def test_wrapping_restored_on_exit(tmp_path: Path) -> None:
    """After ``__exit__``, ``LlmClient.call`` is the original method again."""
    original_call = LlmClient.call
    run_id = "restore_test"

    with track_cost("A1_extract", None, run_id, cost_log_root=tmp_path):
        # Patched call must be different from the original.
        assert LlmClient.call is not original_call

    # Restored.
    assert LlmClient.call is original_call


def test_stage_ids_constant_complete() -> None:
    """The published STAGE_IDS tuple covers all six pipeline stages."""
    assert STAGE_IDS == (
        "A1_extract",
        "A2_digest",
        "A3_implementation",
        "A4_unit_tests",
        "A5_replication",
        "A6_verification",
    )
