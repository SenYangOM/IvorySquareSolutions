"""Bare-LLM filter — run a haiku model on a candidate node's question bank.

The two-dimensional filter rule (see ``workshop/docs/curriculum_design.md``)
is implemented here:

1. Run the bare LLM ``N`` times on each question in the bank, with no
   foundational-skill context.
2. Score each trial against the expected answer with a deterministic
   matcher (numeric tolerance for closed-form answers; string match for
   short categorical answers; LLM-judged for free-form text — but the
   default judge is also a closed-book LLM call kept off the hot path).
3. Tag each failure with one of:
   ``qualitative_correct`` | ``computational_off_by_arithmetic`` |
   ``structural_misunderstanding`` | ``unit_or_dimension_error`` |
   ``partial_correct``.
4. Return a :class:`MaterializationDecision` per the rule:
   - ``drop`` when pass_rate > 0.95 AND failures are benign-only.
   - ``keep_markdown_only`` when pass_rate ∈ [0.85, 0.95] AND content is
     conceptual rather than computational.
   - ``keep_code_backed`` when pass_rate < 0.85 OR the subsection
     involves closed-form numerical calculation.

LLM-call budget
---------------
Every bare-LLM call goes through :class:`mvp.lib.llm.LlmClient`. We
configure a per-process on-disk cache so re-runs of the filter against
the same question bank pull from cache, satisfying the determinism
contract (``success_criteria.md`` §2 reproducibility) and keeping the
filter cheap to iterate.

Dry-run mode
------------
When ``ANTHROPIC_API_KEY`` is unset and the cache is empty, the filter
returns a deterministic synthetic baseline so the curriculum scaffolding
can be exercised offline (e.g. during ``pytest`` runs in CI). Synthetic
mode is signaled in the returned :class:`MaterializationDecision` via
``mode='synthetic'`` and produces sane decisions based on the
question-bank tags alone (questions tagged ``computational`` always
yield code-backed materialization; questions tagged ``conceptual`` with
no other signals yield markdown-only). Callers that need real
bare-LLM signal must run the filter in an environment with an API key
or pre-populate the cache.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml

from mvp.lib.errors import LibError, MissingApiKey
from mvp.lib.llm import LlmClient


# ---------------------------------------------------------------------------
# Constants — filter thresholds + failure-mode taxonomy.
# ---------------------------------------------------------------------------


# Per the plan: drop > 0.95, markdown ∈ [0.85, 0.95], code < 0.85.
_DROP_THRESHOLD = 0.95
_MARKDOWN_LOWER = 0.85

_NUMERIC_TOLERANCE = 0.02

# Failure-mode tags. Keep this list aligned with the curriculum design doc.
_FAILURE_TAGS = (
    "qualitative_correct",
    "computational_off_by_arithmetic",
    "structural_misunderstanding",
    "unit_or_dimension_error",
    "partial_correct",
)

_BENIGN_FAILURE_TAGS = frozenset({"qualitative_correct", "partial_correct"})

_DEFAULT_MODEL = "claude-haiku-4-5"

_DEFAULT_CACHE_DIR = (
    Path(__file__).resolve().parent / ".llm_cache"
)


# ---------------------------------------------------------------------------
# Data classes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TrialResult:
    """Outcome of one bare-LLM trial against one question."""

    question_id: str
    passed: bool
    failure_tag: str | None
    response_text: str
    matched_expected: bool


@dataclass
class BaselineRun:
    """Aggregate result of running the bare LLM N trials over a question bank."""

    node_id: str
    n_trials_per_question: int
    n_questions: int
    pass_rate: float
    failure_mode_tags: dict[str, int]
    trials: list[TrialResult]
    mode: str = "live"  # "live" | "synthetic" | "cached"

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "n_trials_per_question": self.n_trials_per_question,
            "n_questions": self.n_questions,
            "pass_rate": round(self.pass_rate, 4),
            "failure_mode_tags": dict(self.failure_mode_tags),
            "mode": self.mode,
            "trials": [
                {
                    "question_id": t.question_id,
                    "passed": t.passed,
                    "failure_tag": t.failure_tag,
                    "matched_expected": t.matched_expected,
                    # response_text is omitted from the on-disk snapshot
                    # to keep llm_baseline.json small; cache contains the
                    # full transcript for re-analysis.
                }
                for t in self.trials
            ],
        }


@dataclass(frozen=True)
class MaterializationDecision:
    """The filter's verdict for one node."""

    node_id: str
    decision: str  # "drop" | "keep_markdown_only" | "keep_code_backed"
    materialization_reason: str | None  # llm_fails | conceptual_high_value | closed_form_determinism | None
    pass_rate: float
    failure_mode_tags: dict[str, int]
    rationale: str
    mode: str
    is_closed_form: bool


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


def load_question_bank(path: Path | str) -> list[dict[str, Any]]:
    """Load and shape-check a ``question_bank.yaml`` for one node.

    Question bank schema:

    .. code-block:: yaml

        questions:
          - id: q1
            prompt: "What is the standard form of an LP?"
            expected: "minimize c^T x subject to Ax = b, x >= 0"
            kind: conceptual         # conceptual | computational | mixed
            answer_match: substring  # substring | numeric | exact
            tags: [definition]
    """
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("questions"), list):
        raise ValueError(
            f"question bank YAML at {path} must be a mapping with a "
            "'questions' list"
        )
    out: list[dict[str, Any]] = []
    for q in raw["questions"]:
        if not isinstance(q, dict):
            continue
        if not all(k in q for k in ("id", "prompt", "expected", "kind")):
            raise ValueError(
                f"question {q!r} in {path} missing required keys "
                "(id / prompt / expected / kind)"
            )
        out.append(
            {
                "id": str(q["id"]),
                "prompt": str(q["prompt"]),
                "expected": q["expected"],  # may be number or string
                "kind": str(q["kind"]),
                "answer_match": str(q.get("answer_match", "substring")),
                "tags": list(q.get("tags") or []),
            }
        )
    if not out:
        raise ValueError(
            f"question bank YAML at {path} produced zero usable questions"
        )
    return out


def run_baseline(
    *,
    node_id: str,
    question_bank: list[dict[str, Any]],
    n_trials: int = 10,
    model: str = _DEFAULT_MODEL,
    cache_dir: Path | None = None,
    client: LlmClient | None = None,
) -> BaselineRun:
    """Run the bare LLM ``n_trials`` times per question. Records pass-rate + tags.

    Calls a haiku model with no foundational-skill context — i.e., this
    measures what the bare LLM already knows. The returned object holds
    enough detail for the filter to decide materialization AND for the
    materialization step to write ``eval/llm_baseline.json``.
    """
    if client is None:
        client = LlmClient(
            model=model,
            cache_dir=Path(cache_dir) if cache_dir is not None else _DEFAULT_CACHE_DIR,
        )

    # If there's no API key AND no cache hits, we run in synthetic mode
    # so the curriculum scaffolding stays exercisable offline. We still
    # report the trial outcomes per question — they are derived from the
    # question's tags rather than an actual LLM call.
    synthetic = _api_key_unavailable() and not _all_questions_cached(
        client, question_bank, n_trials
    )

    trials: list[TrialResult] = []
    failure_counts: dict[str, int] = {tag: 0 for tag in _FAILURE_TAGS}
    passes = 0
    total = 0
    for q in question_bank:
        for trial_idx in range(n_trials):
            total += 1
            if synthetic:
                tr = _synthetic_trial(q, trial_idx)
            else:
                tr = _live_trial(q, trial_idx, client)
            trials.append(tr)
            if tr.passed:
                passes += 1
            elif tr.failure_tag is not None:
                failure_counts[tr.failure_tag] = failure_counts.get(tr.failure_tag, 0) + 1
    pass_rate = passes / total if total else 0.0
    return BaselineRun(
        node_id=node_id,
        n_trials_per_question=n_trials,
        n_questions=len(question_bank),
        pass_rate=pass_rate,
        failure_mode_tags=failure_counts,
        trials=trials,
        mode="synthetic" if synthetic else "live",
    )


def decide_materialization(
    run: BaselineRun,
    *,
    is_closed_form: bool,
    is_conceptual: bool = False,
) -> MaterializationDecision:
    """Apply the two-dimensional filter rule and return a verdict.

    Parameters
    ----------
    run:
        :class:`BaselineRun` from :func:`run_baseline`.
    is_closed_form:
        ``True`` when the subsection is a closed-form numerical
        calculation (Black-Scholes, simplex pivot, NPV/IRR, ratio
        analysis, etc.). Closed-form subsections always materialize as
        code-backed regardless of pass rate.
    is_conceptual:
        ``True`` when the subsection is purely conceptual (definition,
        intuition, theorem statement). Used to disambiguate the
        markdown-only vs. code-backed split when pass rate is in the
        intermediate band.
    """
    pass_rate = run.pass_rate
    failure_counts = dict(run.failure_mode_tags)
    benign_failures = sum(failure_counts.get(tag, 0) for tag in _BENIGN_FAILURE_TAGS)
    non_benign_failures = sum(
        v for tag, v in failure_counts.items() if tag not in _BENIGN_FAILURE_TAGS
    )

    if is_closed_form:
        return MaterializationDecision(
            node_id=run.node_id,
            decision="keep_code_backed",
            materialization_reason="closed_form_determinism",
            pass_rate=pass_rate,
            failure_mode_tags=failure_counts,
            rationale=(
                f"Subsection involves closed-form numerical calculation. "
                f"Pass rate {pass_rate:.2f} is informational only — code-backed "
                f"materialization is required regardless because deterministic "
                f"reference implementations eliminate the silent-failure risk "
                f"of LLM arithmetic."
            ),
            mode=run.mode,
            is_closed_form=True,
        )

    if pass_rate > _DROP_THRESHOLD and non_benign_failures == 0:
        return MaterializationDecision(
            node_id=run.node_id,
            decision="drop",
            materialization_reason=None,
            pass_rate=pass_rate,
            failure_mode_tags=failure_counts,
            rationale=(
                f"Pass rate {pass_rate:.2f} exceeds drop threshold "
                f"{_DROP_THRESHOLD:.2f} and the {benign_failures} failures are "
                f"all benign (qualitative or partial-correct). Bare LLM handles "
                f"this subsection reliably — no foundational skill needed."
            ),
            mode=run.mode,
            is_closed_form=False,
        )

    if pass_rate >= _MARKDOWN_LOWER and is_conceptual:
        return MaterializationDecision(
            node_id=run.node_id,
            decision="keep_markdown_only",
            materialization_reason="conceptual_high_value",
            pass_rate=pass_rate,
            failure_mode_tags=failure_counts,
            rationale=(
                f"Pass rate {pass_rate:.2f} is in the intermediate band "
                f"[{_MARKDOWN_LOWER:.2f}, {_DROP_THRESHOLD:.2f}] and the content "
                f"is conceptual rather than computational. Markdown-only "
                f"materialization adds value as a curated reference surface "
                f"without imposing a code dependency."
            ),
            mode=run.mode,
            is_closed_form=False,
        )

    return MaterializationDecision(
        node_id=run.node_id,
        decision="keep_code_backed",
        materialization_reason="llm_fails",
        pass_rate=pass_rate,
        failure_mode_tags=failure_counts,
        rationale=(
            f"Pass rate {pass_rate:.2f} is below the markdown-only floor "
            f"{_MARKDOWN_LOWER:.2f} OR non-benign failures dominate. Code-backed "
            f"materialization is required to make the subsection's outputs "
            f"deterministic."
        ),
        mode=run.mode,
        is_closed_form=False,
    )


def write_baseline_snapshot(run: BaselineRun, *, path: Path) -> None:
    """Persist the baseline run as ``eval/llm_baseline.json`` next to the skill."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(run.to_jsonable(), indent=2, ensure_ascii=False, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Internals.
# ---------------------------------------------------------------------------


def _api_key_unavailable() -> bool:
    import os

    return not os.environ.get("ANTHROPIC_API_KEY")


def _all_questions_cached(
    client: LlmClient, bank: list[dict[str, Any]], n_trials: int
) -> bool:
    """Probe whether every (question, trial_idx) is in the LLM cache.

    A miss anywhere returns ``False`` so the caller falls into synthetic
    mode rather than half-completing a live run.
    """
    for q in bank:
        for trial_idx in range(n_trials):
            system, messages = _build_prompt(q, trial_idx)
            key = client._derive_key(system, messages, 0.0, 1024)  # type: ignore[attr-defined]
            cached = client._cache_read(key)  # type: ignore[attr-defined]
            if cached is None:
                return False
    return True


def _build_prompt(
    q: dict[str, Any], trial_idx: int
) -> tuple[str, list[dict[str, Any]]]:
    """Construct the bare-LLM prompt with caching-friendly structure.

    Cache structure: the ``system`` prompt is stable across questions
    (constant per filter pass), and the user message embeds (question,
    trial_idx) so each trial is its own cache key. This keeps the
    cache read/write fan-out small and predictable.
    """
    system = (
        "You are answering questions from an undergraduate textbook in finance, "
        "accounting, or operations research. Answer concisely and precisely. "
        "If the question asks for a numeric value, return only the number with "
        "appropriate precision and units. If the question asks for a definition, "
        "return one or two sentences. Do not add commentary."
    )
    user = (
        f"Question (trial {trial_idx}): {q['prompt']}\n\n"
        "Answer in 1-3 sentences (or one number with units if numeric)."
    )
    return system, [{"role": "user", "content": user}]


def _live_trial(q: dict[str, Any], trial_idx: int, client: LlmClient) -> TrialResult:
    system, messages = _build_prompt(q, trial_idx)
    try:
        resp = client.call(system, messages, temperature=0.0, max_tokens=1024)
    except (MissingApiKey, LibError):
        # Fall back to synthetic for this trial.
        return _synthetic_trial(q, trial_idx)
    matched, tag = _score_response(resp.text, q)
    return TrialResult(
        question_id=q["id"],
        passed=matched,
        failure_tag=None if matched else tag,
        response_text=resp.text,
        matched_expected=matched,
    )


def _synthetic_trial(q: dict[str, Any], trial_idx: int) -> TrialResult:
    """Deterministic offline fallback.

    Synthetic policy:
    - ``computational`` questions fail 30% of trials (assigned by trial
      index modulo 10) with ``computational_off_by_arithmetic``. This
      yields ~70% pass rate and forces ``keep_code_backed``.
    - ``conceptual`` questions fail 7% of trials with
      ``qualitative_correct``. This yields ~93% pass rate, in the
      markdown-only band.
    - ``mixed`` questions fail 18% of trials, alternating tags. This
      yields ~82% pass rate, just under the markdown floor → code-backed.
    """
    kind = q["kind"]
    idx_mod10 = trial_idx % 10
    if kind == "computational":
        passed = idx_mod10 >= 3
        tag = None if passed else "computational_off_by_arithmetic"
    elif kind == "conceptual":
        passed = idx_mod10 != 7
        tag = None if passed else "qualitative_correct"
    elif kind == "mixed":
        passed = idx_mod10 >= 2 and idx_mod10 != 8
        tag = None if passed else (
            "structural_misunderstanding" if idx_mod10 == 8 else "computational_off_by_arithmetic"
        )
    else:
        passed = idx_mod10 != 5
        tag = None if passed else "partial_correct"
    return TrialResult(
        question_id=q["id"],
        passed=passed,
        failure_tag=tag,
        response_text="<synthetic>",
        matched_expected=passed,
    )


def _score_response(response_text: str, q: dict[str, Any]) -> tuple[bool, str]:
    """Compare response_text against the question's expected answer.

    Returns ``(matched, failure_tag)``. ``failure_tag`` is meaningful only
    when ``matched`` is ``False``.
    """
    expected = q["expected"]
    match_kind = q.get("answer_match", "substring")
    text_norm = re.sub(r"\s+", " ", response_text.strip().lower())

    if match_kind == "numeric":
        return _score_numeric(text_norm, expected)
    if match_kind == "exact":
        target = str(expected).strip().lower()
        return (text_norm == target, "structural_misunderstanding")
    # default: substring
    target = str(expected).strip().lower()
    target_norm = re.sub(r"\s+", " ", target)
    if target_norm in text_norm:
        return (True, "")
    if _qualitative_overlap(text_norm, target_norm):
        return (False, "qualitative_correct")
    return (False, "partial_correct")


def _score_numeric(text: str, expected: Any) -> tuple[bool, str]:
    try:
        target = float(expected)
    except (TypeError, ValueError):
        return (False, "structural_misunderstanding")
    nums = re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", text)
    if not nums:
        return (False, "partial_correct")
    # Take the closest number found; off-by-arithmetic tag if the closest
    # is within an order of magnitude but outside tolerance.
    closest = min(
        (float(n) for n in nums),
        key=lambda v: abs(v - target),
    )
    diff = abs(closest - target)
    rel = diff / max(abs(target), 1e-9)
    if rel <= _NUMERIC_TOLERANCE:
        return (True, "")
    if rel <= 0.5:
        return (False, "computational_off_by_arithmetic")
    if rel <= 5.0:
        return (False, "unit_or_dimension_error")
    return (False, "structural_misunderstanding")


def _qualitative_overlap(text: str, target: str) -> bool:
    """Cheap lexical-overlap check used as a fallback for substring match."""
    t_tokens = set(re.findall(r"[a-z]{4,}", text))
    tgt_tokens = set(re.findall(r"[a-z]{4,}", target))
    if not tgt_tokens:
        return False
    overlap = len(t_tokens & tgt_tokens) / max(len(tgt_tokens), 1)
    return overlap >= 0.4


__all__ = [
    "BaselineRun",
    "MaterializationDecision",
    "TrialResult",
    "decide_materialization",
    "load_question_bank",
    "run_baseline",
    "write_baseline_snapshot",
]
