"""Per-stage / per-paper LLM cost tracking for the deep paper-to-skill pipeline.

The deep pipeline (``workshop/paper_to_skill/orchestrator.py``) targets
~5M tokens per paper across six stages — extract, digest, implementation,
unit-test authoring, replication harness, verification — each with its
own budget. The stages cooperate through one shared mechanism: every LLM
call inside a stage must be accounted for against that stage's budget,
and every call across the run must roll up to a per-paper total. This
module provides that mechanism.

Design — three concerns
-----------------------

1. **Per-call records.** Each call writes one JSON line to
   ``mvp/agents/cost_log/<run_id>.jsonl`` with the fields::

        {
          "stage_id": "A1_extract",
          "persona": "quant_finance_methodologist" | None,
          "model": "claude-opus-4-7",
          "input_tokens": 1234,
          "output_tokens": 567,
          "cache_read_tokens": 0,
          "cache_creation_tokens": 0,
          "timestamp": "2026-04-27T14:23:01.412Z",
          "paper_id": "beneish_1999",       # optional, set by orchestrator
          "call_kind": "persona_runtime"    # 'persona_runtime' | 'raw_llm'
        }

2. **Aggregation.** :func:`summarize` reads back the JSONL for one
   ``run_id`` and produces a structured dict — totals per stage, totals
   per persona, run total, and a per-stage list of records. Aggregation
   is read-only and does not mutate the log.

3. **Wrapping the existing call surfaces.** The pipeline's stages call
   the LLM through one of two paths today: :class:`mvp.lib.llm.LlmClient`
   (raw) and :class:`mvp.agents.persona_runtime.PersonaRuntime`
   (persona-loaded). The :func:`track_cost` context manager
   monkey-patches the ``call`` methods on both for the duration of the
   ``with`` block; on exit it restores the originals. This keeps the
   cost-tracking concern out of every call site — a stage simply runs
   ``with track_cost(...): ...`` and any LLM call inside is logged
   automatically.

The wrapper deliberately does not change call semantics. The original
return value is propagated unchanged; only an extra JSONL append is
performed. If the JSONL write fails for any reason the call still
succeeds — cost tracking is observability, never a correctness gate.

Per Operating Principle P2 (``mvp_build_goal.md`` §0), this module ships
its full contract: nesting is supported, threadsafe append-writes use
the ``"a"``-mode + flush + fsync pattern, and ``summarize`` validates
file shape before accepting records.
"""

from __future__ import annotations

import json
import os
import threading
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Lazy imports of the modules we monkey-patch — done at enter() time so
# this module is safe to import even when the agents subsystem is not
# loaded yet (e.g. tooling that only wants ``summarize`` on an existing
# log).


DEFAULT_COST_LOG_ROOT = (
    Path(__file__).resolve().parent.parent / "agents" / "cost_log"
)


# Stage ids used by the orchestrator. Documented here so callers don't
# typo them; the tracker accepts any string but ``summarize`` reports
# unknown stage_ids in a separate ``unknown_stages`` bucket.
STAGE_IDS: tuple[str, ...] = (
    "A1_extract",
    "A2_digest",
    "A3_implementation",
    "A4_unit_tests",
    "A5_replication",
    "A6_verification",
)


@dataclass(frozen=True)
class CallRecord:
    """One per-call cost record (JSON-serializable through ``__dict__``)."""

    stage_id: str
    persona: str | None
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int
    timestamp: str
    paper_id: str | None
    call_kind: str

    def to_json(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "persona": self.persona,
            "model": self.model,
            "input_tokens": int(self.input_tokens),
            "output_tokens": int(self.output_tokens),
            "cache_read_tokens": int(self.cache_read_tokens),
            "cache_creation_tokens": int(self.cache_creation_tokens),
            "timestamp": self.timestamp,
            "paper_id": self.paper_id,
            "call_kind": self.call_kind,
        }


class _Tracker(AbstractContextManager["_Tracker"]):
    """The actual context manager. :func:`track_cost` is the public alias.

    Each instance writes to a single JSONL file at
    ``<cost_log_root>/<run_id>.jsonl``. The patched call methods append
    to that file via :meth:`record`. Multiple trackers can be active at
    the same time (nested tracking) — innermost wins for the
    ``stage_id``/``persona`` attribution, because each tracker installs
    its own wrapper that captures the outer one before delegating. On
    ``__exit__`` we restore the wrappers in reverse order.
    """

    # Module-level lock guards monkey-patch installation so concurrent
    # ``with track_cost(...)`` blocks (extremely rare; orchestrator runs
    # serially today) don't race on the patched method object.
    _patch_lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        *,
        stage_id: str,
        persona: str | None,
        run_id: str,
        cost_log_root: Path | None = None,
        paper_id: str | None = None,
    ) -> None:
        if not stage_id:
            raise ValueError("stage_id must be a non-empty string")
        if not run_id:
            raise ValueError("run_id must be a non-empty string")
        self._stage_id = stage_id
        self._persona = persona
        self._run_id = run_id
        self._paper_id = paper_id
        self._cost_log_root = (
            Path(cost_log_root) if cost_log_root is not None else DEFAULT_COST_LOG_ROOT
        )
        self._log_path: Path = self._cost_log_root / f"{run_id}.jsonl"
        self._installed = False
        self._llm_client_original_call = None  # type: ignore[var-annotated]
        self._persona_runtime_original_call = None  # type: ignore[var-annotated]
        # Lock used for serializing JSONL appends from this tracker.
        self._write_lock = threading.Lock()

    # -- Public API used inside the orchestrator ------------------------

    def record(
        self,
        *,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
        call_kind: str = "raw_llm",
        persona_override: str | None = None,
    ) -> CallRecord:
        """Append one record to the run's JSONL file.

        The orchestrator can call this directly when it has its own
        custom call path (e.g. a stage that runs a deterministic helper
        that nonetheless logs into the same per-stage budget). The
        monkey-patched wrappers also call this on every patched LLM
        invocation.
        """
        rec = CallRecord(
            stage_id=self._stage_id,
            persona=persona_override if persona_override is not None else self._persona,
            model=str(model),
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            cache_read_tokens=int(cache_read_tokens or 0),
            cache_creation_tokens=int(cache_creation_tokens or 0),
            timestamp=datetime.now(timezone.utc).isoformat(),
            paper_id=self._paper_id,
            call_kind=call_kind,
        )
        self._append(rec)
        return rec

    @property
    def log_path(self) -> Path:
        """Absolute path to this tracker's JSONL log."""
        return self._log_path

    @property
    def stage_id(self) -> str:
        return self._stage_id

    @property
    def persona(self) -> str | None:
        return self._persona

    # -- Context-manager mechanics --------------------------------------

    def __enter__(self) -> "_Tracker":
        self._cost_log_root.mkdir(parents=True, exist_ok=True)
        # Touch the file so consumers see an empty log even if no LLM
        # call fires during the stage.
        self._log_path.touch(exist_ok=True)
        with _Tracker._patch_lock:
            self._install_wrappers()
            self._installed = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool | None:
        if self._installed:
            with _Tracker._patch_lock:
                self._uninstall_wrappers()
                self._installed = False
        # Never swallow exceptions.
        return None

    # -- Internals ------------------------------------------------------

    def _append(self, rec: CallRecord) -> None:
        """Append one JSON record to the run's JSONL log.

        Writes are line-buffered + flushed; this gives a usable log even
        if the orchestrator process is killed mid-stage. We do NOT raise
        on write failure — the per-call accounting is observational, not
        load-bearing for skill correctness.
        """
        try:
            with self._write_lock:
                with self._log_path.open("a", encoding="utf-8") as f:
                    f.write(json.dumps(rec.to_json(), ensure_ascii=False, sort_keys=True))
                    f.write("\n")
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except OSError:
                        # Best-effort durability; some filesystems don't
                        # implement fsync (tmpfs in CI). Don't crash.
                        pass
        except OSError:
            # Logging failure must never break the LLM call. Surface
            # nothing here; consumers who care about completeness should
            # validate the JSONL after the run.
            return

    def _install_wrappers(self) -> None:
        """Monkey-patch ``LlmClient.call`` and ``PersonaRuntime.call``.

        Wrappers capture token counts from each return value and append
        a record. The originals are restored in :meth:`_uninstall_wrappers`.
        Importing inside the method (a) keeps cost_tracking importable
        even when the agents tree fails to import (rare), and (b) lets
        tests stub these modules with module-level fakes.
        """
        from mvp.agents import persona_runtime as _pr_mod
        from mvp.lib import llm as _llm_mod

        # --- LlmClient.call wrapper ---
        original_llm_call = _llm_mod.LlmClient.call
        self._llm_client_original_call = original_llm_call
        tracker = self

        def _patched_llm_call(self_client, *args, **kwargs):  # type: ignore[no-untyped-def]
            resp = original_llm_call(self_client, *args, **kwargs)
            try:
                model = getattr(self_client, "_model", "unknown")
                tracker.record(
                    model=str(model),
                    input_tokens=int(getattr(resp, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(resp, "output_tokens", 0) or 0),
                    cache_read_tokens=int(getattr(resp, "cache_read_tokens", 0) or 0),
                    cache_creation_tokens=int(
                        getattr(resp, "cache_creation_tokens", 0) or 0
                    ),
                    call_kind="raw_llm",
                )
            except Exception:
                # Never let bookkeeping break the wrapped call.
                pass
            return resp

        _llm_mod.LlmClient.call = _patched_llm_call  # type: ignore[assignment]

        # --- PersonaRuntime.call wrapper ---
        original_pr_call = _pr_mod.PersonaRuntime.call
        self._persona_runtime_original_call = original_pr_call

        def _patched_pr_call(self_runtime, persona_id, *args, **kwargs):  # type: ignore[no-untyped-def]
            resp = original_pr_call(self_runtime, persona_id, *args, **kwargs)
            try:
                tracker.record(
                    model=str(getattr(resp, "model", "unknown")),
                    input_tokens=int(getattr(resp, "input_tokens", 0) or 0),
                    output_tokens=int(getattr(resp, "output_tokens", 0) or 0),
                    cache_read_tokens=int(getattr(resp, "cache_read_tokens", 0) or 0),
                    cache_creation_tokens=int(
                        getattr(resp, "cache_creation_tokens", 0) or 0
                    ),
                    call_kind="persona_runtime",
                    persona_override=str(persona_id),
                )
            except Exception:
                pass
            return resp

        _pr_mod.PersonaRuntime.call = _patched_pr_call  # type: ignore[assignment]

    def _uninstall_wrappers(self) -> None:
        from mvp.agents import persona_runtime as _pr_mod
        from mvp.lib import llm as _llm_mod

        if self._llm_client_original_call is not None:
            _llm_mod.LlmClient.call = self._llm_client_original_call  # type: ignore[assignment]
            self._llm_client_original_call = None
        if self._persona_runtime_original_call is not None:
            _pr_mod.PersonaRuntime.call = self._persona_runtime_original_call  # type: ignore[assignment]
            self._persona_runtime_original_call = None


def track_cost(
    stage_id: str,
    persona: str | None,
    run_id: str,
    *,
    cost_log_root: Path | None = None,
    paper_id: str | None = None,
) -> _Tracker:
    """Context manager that wraps the active LLM clients to log per-call cost.

    Parameters
    ----------
    stage_id:
        Pipeline stage identifier (one of :data:`STAGE_IDS`, or any
        string the orchestrator chooses). Logged on every call made
        inside the ``with`` block.
    persona:
        Persona id (e.g. ``"quant_finance_methodologist"``) when the
        stage is run by a single persona. ``None`` for stages that
        invoke multiple personas — :class:`PersonaRuntime` calls inside
        the block override this with their actual persona id.
    run_id:
        Identifier for the run; the JSONL file is written to
        ``<cost_log_root>/<run_id>.jsonl``. The orchestrator constructs
        a stable run_id of the form ``<paper_id>__<utc_compact>`` so the
        same paper can be re-run without log collisions.
    cost_log_root:
        Override for the default cost-log directory
        (``mvp/agents/cost_log``). Tests pass a tmp_path here.
    paper_id:
        Optional paper identifier; recorded on every per-call entry so
        a multi-paper run's log file is still attributable.

    Returns
    -------
    _Tracker
        The context manager instance. Use it directly in ``with`` form.

    Example
    -------
    .. code-block:: python

        from mvp.lib.cost_tracking import track_cost

        with track_cost("A1_extract", "quant_finance_methodologist", "beneish_1999__20260427"):
            # ... LLM calls inside this block are recorded automatically.
            client = LlmClient(...)
            client.call(system="...", messages=[...])
    """
    return _Tracker(
        stage_id=stage_id,
        persona=persona,
        run_id=run_id,
        cost_log_root=cost_log_root,
        paper_id=paper_id,
    )


def summarize(
    run_id: str,
    *,
    cost_log_root: Path | None = None,
) -> dict[str, Any]:
    """Aggregate the JSONL log for ``run_id`` into a structured summary.

    Output shape::

        {
            "run_id": "<run_id>",
            "log_path": "<absolute path>",
            "n_calls": <int>,
            "totals": {
                "input_tokens": ...,
                "output_tokens": ...,
                "cache_read_tokens": ...,
                "cache_creation_tokens": ...,
                "tokens_total": ...,
            },
            "by_stage": {
                "A1_extract": {
                    "n_calls": 4,
                    "input_tokens": ...,
                    "output_tokens": ...,
                    "cache_read_tokens": ...,
                    "cache_creation_tokens": ...,
                    "tokens_total": ...,
                },
                ...
            },
            "by_persona": { ... same shape, keyed by persona },
            "by_model": { ... same shape, keyed by model },
            "unknown_stages": [<list of stage_ids not in STAGE_IDS>],
            "paper_ids": [<list of distinct paper ids in the log>],
        }

    The function is read-only; it never mutates the JSONL.

    Parameters
    ----------
    run_id:
        Run identifier (matches the filename stem).
    cost_log_root:
        Override for the cost-log directory.

    Raises
    ------
    FileNotFoundError
        If ``<cost_log_root>/<run_id>.jsonl`` does not exist.
    """
    root = Path(cost_log_root) if cost_log_root is not None else DEFAULT_COST_LOG_ROOT
    path = root / f"{run_id}.jsonl"
    if not path.is_file():
        raise FileNotFoundError(f"cost log not found at {path}")

    n_calls = 0
    totals = _empty_bucket()
    by_stage: dict[str, dict[str, int]] = {}
    by_persona: dict[str, dict[str, int]] = {}
    by_model: dict[str, dict[str, int]] = {}
    unknown_stages: set[str] = set()
    paper_ids: set[str] = set()

    with path.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Skip malformed lines; the appender's flush+fsync
                # contract makes mid-line corruption unlikely but not
                # impossible (e.g. external editors).
                continue
            if not isinstance(rec, dict):
                continue
            stage = str(rec.get("stage_id") or "")
            persona = rec.get("persona")
            model = str(rec.get("model") or "")
            paper_id = rec.get("paper_id")
            it = int(rec.get("input_tokens") or 0)
            ot = int(rec.get("output_tokens") or 0)
            crt = int(rec.get("cache_read_tokens") or 0)
            cct = int(rec.get("cache_creation_tokens") or 0)

            n_calls += 1
            _accumulate(totals, it, ot, crt, cct)

            if stage:
                stage_bucket = by_stage.setdefault(stage, _empty_bucket())
                stage_bucket["n_calls"] += 1
                _accumulate(stage_bucket, it, ot, crt, cct)
                if stage not in STAGE_IDS:
                    unknown_stages.add(stage)
            if persona:
                persona_bucket = by_persona.setdefault(str(persona), _empty_bucket())
                persona_bucket["n_calls"] += 1
                _accumulate(persona_bucket, it, ot, crt, cct)
            if model:
                model_bucket = by_model.setdefault(model, _empty_bucket())
                model_bucket["n_calls"] += 1
                _accumulate(model_bucket, it, ot, crt, cct)
            if paper_id:
                paper_ids.add(str(paper_id))

    totals["n_calls"] = n_calls

    return {
        "run_id": run_id,
        "log_path": str(path),
        "n_calls": n_calls,
        "totals": totals,
        "by_stage": by_stage,
        "by_persona": by_persona,
        "by_model": by_model,
        "unknown_stages": sorted(unknown_stages),
        "paper_ids": sorted(paper_ids),
    }


# ---------------------------------------------------------------------------
# Aggregation helpers.
# ---------------------------------------------------------------------------


def _empty_bucket() -> dict[str, int]:
    return {
        "n_calls": 0,
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 0,
        "cache_creation_tokens": 0,
        "tokens_total": 0,
    }


def _accumulate(
    bucket: dict[str, int],
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_creation_tokens: int,
) -> None:
    bucket["input_tokens"] += int(input_tokens)
    bucket["output_tokens"] += int(output_tokens)
    bucket["cache_read_tokens"] += int(cache_read_tokens)
    bucket["cache_creation_tokens"] += int(cache_creation_tokens)
    bucket["tokens_total"] = (
        bucket["input_tokens"]
        + bucket["output_tokens"]
        + bucket["cache_read_tokens"]
        + bucket["cache_creation_tokens"]
    )


__all__ = [
    "CallRecord",
    "DEFAULT_COST_LOG_ROOT",
    "STAGE_IDS",
    "summarize",
    "track_cost",
]
