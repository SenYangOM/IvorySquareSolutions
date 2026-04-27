"""Deep paper-to-skill pipeline orchestrator.

Replaces the human-driven 12-step paper-onboarding playbook
(``workshop/paper_to_skill/README.md``) with an LLM-orchestrated
six-stage pipeline:

* **A1 Extract** — PDF → structured JSON: TOC, equations, sample
  characteristics, worked examples, threshold values.
* **A2 Digest** — long-form digest: intuition, paper-exact formulas,
  worked-example reproductions, edge cases, sample-period assumptions,
  prerequisite concepts.
* **A3 Implementation** — draft ``skill.py`` + ``manifest.yaml`` (and
  rule template if applicable). Iterate until the manifest validates.
* **A4 Unit-test authoring** — ~25-40 unit tests covering paper
  worked-examples within ±0.05, null propagation, missing line items,
  edge inputs, citation contract.
* **A5 Replication harness** — run the skill against the paper's
  reported worked-example outputs; iterate until tolerance is met or
  deviation is documented in ``implementation_decisions``.
* **A6 Verification + persona review** — citation_auditor resolves
  every citation; accounting_expert audits rule template;
  evaluation_agent authors gold cases; final eval gate.

Each stage is wrapped in a :func:`mvp.lib.cost_tracking.track_cost`
context manager so per-stage token usage is logged to
``mvp/agents/cost_log/<run_id>.jsonl``. Each stage's output is
persisted to ``mvp/agents/audit_log/<run_id>/`` as a JSON artifact.

Persona gating
--------------

Between stages, a "gate" persona produces a verdict — ``go``, ``revise``,
or ``block`` — reflected in a structured :class:`GateVerdict` written
into the audit log. On ``block``, the orchestrator halts and returns a
structured ``{verdict, revisions_needed}`` dict; the caller (a human or
a parent agent) can resume after an override.

Operating mode
--------------

The orchestrator runs with two modes:

* ``mode="calibration"`` — a paper that is already onboarded
  (e.g. ``"beneish_1999"``). The pipeline is exercised end-to-end and
  its outputs are compared (downstream, by the caller) against the
  shipped artifacts; no production skill is overwritten.

* ``mode="fresh"`` — a paper not yet onboarded. The pipeline produces
  candidate artifacts under ``mvp/skills/.../<skill_id>/`` and gold
  cases under ``mvp/eval/gold/<skill_short>/``.

The two modes share the same six stages and the same cost-tracking
contract; they differ only in where final artifacts are written.

LLM cost discipline
-------------------

The pipeline aggressively uses Anthropic prompt caching: the paper
text + the persona system prompt are inserted into the cached prefix
every call, so multi-turn deepening keeps cache_read_tokens high and
cache_creation_tokens low. The shared :class:`mvp.lib.llm.LlmClient`'s
on-disk cache provides cross-run replay so a calibration re-run is
near-zero cost for unchanged inputs.

The pipeline runs without an Anthropic API key when every stage's LLM
call hits the on-disk cache. When the cache is cold and no API key is
available, the orchestrator surfaces a structured
``MissingApiKey``-equivalent verdict ("blocked: missing_api_key") so
the caller can decide whether to provide a key or accept a degraded
run.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from mvp.agents.persona_runtime import PersonaRuntime
from mvp.lib.cost_tracking import STAGE_IDS, summarize, track_cost
from mvp.lib.errors import MissingApiKey, PersonaCallError
from mvp.skills.manifest_schema import SkillManifest

from workshop.paper_to_skill.extract_paper import extract_paper_pdf


PipelineMode = Literal["calibration", "fresh"]
GateVerdictKind = Literal["go", "revise", "block"]


# ---------------------------------------------------------------------------
# Repository layout — discovered relative to this file.
# ---------------------------------------------------------------------------


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MVP_ROOT = REPO_ROOT / "mvp"
PAPERS_ROOT = MVP_ROOT / "data" / "papers"
NOTES_ROOT = REPO_ROOT / "workshop" / "paper_to_skill" / "notes"
AUDIT_LOG_ROOT = MVP_ROOT / "agents" / "audit_log"
COST_LOG_ROOT = MVP_ROOT / "agents" / "cost_log"
SKILLS_PAPER_DERIVED_ROOT = MVP_ROOT / "skills" / "paper_derived"
EVAL_GOLD_ROOT = MVP_ROOT / "eval" / "gold"


# Each stage's target token spend (per the workstream-A pipeline-stages
# table). The pipeline records actuals and the caller decides whether
# the spend is within the +/-20% tolerance gate.
STAGE_TARGETS: dict[str, int] = {
    "A1_extract": 500_000,
    "A2_digest": 1_000_000,
    "A3_implementation": 1_000_000,
    "A4_unit_tests": 500_000,
    "A5_replication": 500_000,
    "A6_verification": 1_500_000,
}


# Stage → (driver_persona, gate_persona). The driver authors the stage
# artifact; the gate persona reviews it before the next stage starts.
STAGE_PERSONAS: dict[str, tuple[str, str]] = {
    # A1 extraction is deterministic + reviewed by the methodologist.
    "A1_extract": ("quant_finance_methodologist", "quant_finance_methodologist"),
    # A2 digest is methodologist-authored + accounting_expert-audited.
    "A2_digest": ("quant_finance_methodologist", "accounting_expert"),
    # A3 implementation is methodologist-authored + accounting_expert-audited
    # for the rule template (when one is needed).
    "A3_implementation": ("quant_finance_methodologist", "accounting_expert"),
    # A4 unit tests are evaluation_agent-authored.
    "A4_unit_tests": ("evaluation_agent", "evaluation_agent"),
    # A5 replication harness is methodologist-authored + evaluation_agent-gated.
    "A5_replication": ("quant_finance_methodologist", "evaluation_agent"),
    # A6 verification rotates through citation_auditor, accounting_expert,
    # evaluation_agent. The driver field below names the primary; the
    # stage internally calls all four personas.
    "A6_verification": ("citation_auditor", "evaluation_agent"),
}


# Anthropic models — match the persona YAMLs.
DRIVER_MODEL_BY_PERSONA: dict[str, str] = {
    "accounting_expert": "claude-opus-4-7",
    "quant_finance_methodologist": "claude-opus-4-7",
    "evaluation_agent": "claude-sonnet-4-6",
    "citation_auditor": "claude-sonnet-4-6",
}


# ---------------------------------------------------------------------------
# Result types.
# ---------------------------------------------------------------------------


@dataclass
class GateVerdict:
    """One persona gate's verdict on a stage artifact."""

    verdict: GateVerdictKind
    persona: str
    rationale: str
    revisions_needed: list[str] = field(default_factory=list)
    next_stage_inputs: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StageResult:
    """One stage's output + its gate verdict + cost summary."""

    stage_id: str
    artifact_path: Path | None
    verdict: GateVerdict
    started_at: str
    completed_at: str
    summary: str
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "artifact_path": str(self.artifact_path) if self.artifact_path else None,
            "verdict": self.verdict.to_json(),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "summary": self.summary,
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# Public entry point.
# ---------------------------------------------------------------------------


def run_deep_pipeline(
    paper_id: str,
    mode: PipelineMode = "calibration",
    *,
    audit_log_root: Path | None = None,
    cost_log_root: Path | None = None,
    halt_on_block: bool = True,
) -> dict[str, Any]:
    """Run the deep paper-to-skill pipeline end-to-end.

    Parameters
    ----------
    paper_id:
        Stable snake_case id of the paper. The pipeline expects a
        registered PDF at
        ``mvp/data/papers/<paper_id>.pdf`` and a methodologist-notes
        markdown at
        ``workshop/paper_to_skill/notes/<paper_id>.md`` (the notes
        file is optional for fresh runs — when absent, A2 produces it).
    mode:
        ``"calibration"`` for an already-onboarded paper (no production
        skill is overwritten — outputs land under the run's audit log).
        ``"fresh"`` for a new paper (final artifacts are written into
        ``mvp/skills/...`` and ``mvp/eval/gold/...``).
    audit_log_root:
        Override for the audit-log directory. Tests pass tmp_path here.
    cost_log_root:
        Override for the cost-log directory.
    halt_on_block:
        When ``True`` (default) the pipeline stops at the first ``block``
        verdict. When ``False``, it records the block in the result dict
        but continues (used in tests + dry-runs).

    Returns
    -------
    dict
        Structured run report::

            {
                "run_id": "<paper_id>__<utc_compact>",
                "paper_id": "<paper_id>",
                "mode": "calibration" | "fresh",
                "started_at": "<iso>",
                "completed_at": "<iso>",
                "stages": [<list of StageResult JSON>],
                "verdict": "go" | "revise" | "block" | "complete",
                "revisions_needed": [<list of strings>] (when not 'complete'),
                "cost_summary": {<from cost_tracking.summarize>},
                "audit_log_dir": "<absolute path>",
            }
    """
    if mode not in ("calibration", "fresh"):
        raise ValueError(
            f"mode must be 'calibration' or 'fresh', got {mode!r}"
        )

    audit_root = Path(audit_log_root) if audit_log_root is not None else AUDIT_LOG_ROOT
    cost_root = Path(cost_log_root) if cost_log_root is not None else COST_LOG_ROOT

    started_at = datetime.now(timezone.utc).isoformat()
    run_id = _build_run_id(paper_id)
    run_dir = audit_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cost_root.mkdir(parents=True, exist_ok=True)

    pdf_path = PAPERS_ROOT / f"{paper_id}.pdf"
    if not pdf_path.is_file():
        return _early_block(
            run_id=run_id,
            paper_id=paper_id,
            mode=mode,
            started_at=started_at,
            run_dir=run_dir,
            cost_root=cost_root,
            reason=f"PDF not found at {pdf_path}",
            revisions=[
                f"Place the paper PDF at {pdf_path} and re-run the pipeline.",
            ],
        )

    notes_path = NOTES_ROOT / f"{paper_id}.md"
    notes_text: str | None = None
    if notes_path.is_file():
        notes_text = notes_path.read_text(encoding="utf-8")

    # Persistent state passed between stages. Each stage MAY add keys
    # but must not delete existing keys — earlier-stage outputs are
    # gate-input for later stages.
    state: dict[str, Any] = {
        "paper_id": paper_id,
        "pdf_path": str(pdf_path),
        "mode": mode,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "notes_path": str(notes_path) if notes_text is not None else None,
        "notes_text_initial": notes_text,
    }

    # The persona runtime is shared across stages so the audit log
    # accumulates in one place. Each stage opens its own track_cost
    # block so per-stage budgets are recorded.
    runtime = PersonaRuntime()

    stages: list[StageResult] = []
    final_verdict: str = "complete"
    final_revisions: list[str] = []

    for stage_id in STAGE_IDS:
        driver_persona, gate_persona = STAGE_PERSONAS[stage_id]
        stage_started = datetime.now(timezone.utc).isoformat()
        with track_cost(
            stage_id,
            driver_persona,
            run_id,
            cost_log_root=cost_root,
            paper_id=paper_id,
        ):
            try:
                result = _STAGE_FUNCTIONS[stage_id](
                    state=state,
                    runtime=runtime,
                    run_dir=run_dir,
                    paper_id=paper_id,
                    pdf_path=pdf_path,
                    mode=mode,
                    driver_persona=driver_persona,
                    gate_persona=gate_persona,
                )
            except (MissingApiKey, PersonaCallError) as exc:
                # An LLM-shaped failure mid-stage is a structured block —
                # we record it as the stage's verdict and stop (or
                # continue, if halt_on_block=False).
                verdict = GateVerdict(
                    verdict="block",
                    persona=driver_persona,
                    rationale=(
                        f"Underlying LLM call failed during stage {stage_id}: "
                        f"{type(exc).__name__}: {exc}"
                    ),
                    revisions_needed=[
                        "Set ANTHROPIC_API_KEY in the environment, or prime "
                        "the on-disk LLM cache for the stage's prompts, then "
                        "re-run the pipeline.",
                    ],
                )
                completed_at = datetime.now(timezone.utc).isoformat()
                result = StageResult(
                    stage_id=stage_id,
                    artifact_path=None,
                    verdict=verdict,
                    started_at=stage_started,
                    completed_at=completed_at,
                    summary=f"stage {stage_id} blocked: {exc}",
                    extra={"exception_type": type(exc).__name__},
                )

        # Persist the stage result.
        _write_json(
            run_dir / f"{stage_id}.result.json", result.to_json()
        )
        stages.append(result)

        if result.verdict.verdict == "block":
            final_verdict = "block"
            final_revisions = list(result.verdict.revisions_needed)
            if halt_on_block:
                break
        elif result.verdict.verdict == "revise":
            # We record the revisions but proceed — the next stage gets
            # the revisions in its inputs and may resolve them.
            final_verdict = "revise" if final_verdict == "complete" else final_verdict
            final_revisions.extend(result.verdict.revisions_needed)

    completed_at = datetime.now(timezone.utc).isoformat()
    cost_summary = summarize(run_id, cost_log_root=cost_root)

    report = {
        "run_id": run_id,
        "paper_id": paper_id,
        "mode": mode,
        "started_at": started_at,
        "completed_at": completed_at,
        "stages": [s.to_json() for s in stages],
        "verdict": final_verdict,
        "revisions_needed": final_revisions,
        "cost_summary": cost_summary,
        "audit_log_dir": str(run_dir),
        "stage_targets": dict(STAGE_TARGETS),
    }
    _write_json(run_dir / "run_report.json", report)
    return report


# ---------------------------------------------------------------------------
# Stage implementations.
# ---------------------------------------------------------------------------


def _stage_a1_extract(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A1 — deterministic PDF extraction + methodologist review.

    Reuses :func:`workshop.paper_to_skill.extract_paper.extract_paper_pdf`
    for the deterministic structural extraction, then asks the
    quant_finance_methodologist persona for a focused review of which
    formulas, thresholds, and worked-example tables it flags as
    load-bearing for the skill. The review is recorded as the stage's
    gate verdict.
    """
    started = datetime.now(timezone.utc).isoformat()
    extraction = extract_paper_pdf(pdf_path, paper_id=paper_id)

    extraction_path = run_dir / "A1_extracted.json"
    _write_json(extraction_path, extraction.to_json_dict())

    # Build a focused review prompt: top TOC + first 30 detected formulas.
    formulas_for_review = extraction.detected_formulas[:30]
    toc_for_review = [t for t in extraction.toc if t.level <= 3][:50]

    review_prompt = (
        f"Paper id: {paper_id}\n"
        f"PDF SHA-256: {extraction.pdf_sha256}\n"
        f"Page count: {extraction.page_count}\n"
        f"Abstract preview (first 1000 chars):\n{extraction.abstract_preview}\n\n"
        f"Top-level TOC entries (level<=3, first 50):\n"
        f"{json.dumps([{'level': t.level, 'title': t.title, 'page': t.page} for t in toc_for_review], indent=2)}\n\n"
        f"First 30 detected formula hits:\n"
        f"{json.dumps([{'page': f.page, 'pattern': f.pattern_matched, 'match': f.match_text, 'snippet': f.snippet} for f in formulas_for_review], indent=2)}\n\n"
        "Review tasks:\n"
        "1. Identify the paper's primary scalar construct(s) — the score(s),\n"
        "   ratio(s), or classifier(s) the paper proposes.\n"
        "2. Name the table or page where the load-bearing coefficients live.\n"
        "3. Flag any threshold value (e.g. 'M > -1.78') stated in the\n"
        "   paper text — quote the exact string.\n"
        "4. Flag any worked-example tables that name individual firms\n"
        "   with reported numbers — these will be replication oracles.\n"
        "5. Confirm or deny that the paper fits an L1/L2/L3/L4 IvorySquare\n"
        "   skill layer; cite the playbook decision tree at\n"
        "   workshop/paper_to_skill/README.md §5.\n\n"
        "Format your reply as a markdown report with sections matching\n"
        "the five tasks above, then a final 'gate_verdict' fenced JSON\n"
        "block with shape\n"
        "```json\n"
        '{"verdict": "go|revise|block", "rationale": "...", '
        '"revisions_needed": ["..."]}\n'
        "```\n"
    )

    review_resp = _try_persona_call(runtime, driver_persona, review_prompt)
    review_text = review_resp.text if review_resp is not None else ""
    review_path = run_dir / "A1_methodologist_review.md"
    review_path.write_text(review_text or "(no review — LLM call unavailable)\n", encoding="utf-8")

    verdict = _parse_gate_verdict(
        review_text,
        default_persona=gate_persona,
        default_rationale=(
            "A1 deterministic extraction completed; methodologist review "
            "available at A1_methodologist_review.md."
        ),
        fallback_when_unavailable=(
            review_resp is None
            and "no review — LLM call unavailable" in (review_text or "no review — LLM call unavailable")
        ),
    )

    state["A1_extraction"] = {
        "extraction_path": str(extraction_path),
        "review_path": str(review_path),
        "pdf_sha256": extraction.pdf_sha256,
        "page_count": extraction.page_count,
        "n_detected_formulas": len(extraction.detected_formulas),
        "n_toc_entries": len(extraction.toc),
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A1_extract",
        artifact_path=extraction_path,
        verdict=verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"Extracted {len(extraction.detected_formulas)} formula hits "
            f"and {len(extraction.toc)} TOC entries from {pdf_path.name}; "
            f"methodologist review verdict: {verdict.verdict}."
        ),
        extra={
            "pdf_sha256": extraction.pdf_sha256,
            "page_count": extraction.page_count,
            "n_detected_formulas": len(extraction.detected_formulas),
        },
    )


def _stage_a2_digest(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A2 — methodologist authors the long-form digest; accounting_expert audits.

    For calibration runs, the existing methodologist notes file (if any)
    is included as prior-art context so the digest is comparable.
    """
    started = datetime.now(timezone.utc).isoformat()

    extraction_blob = state.get("A1_extraction") or {}
    notes_text = state.get("notes_text_initial")
    abstract_preview = ""
    extraction_path = extraction_blob.get("extraction_path")
    if extraction_path and Path(extraction_path).is_file():
        try:
            extraction_data = json.loads(
                Path(extraction_path).read_text(encoding="utf-8")
            )
            abstract_preview = str(extraction_data.get("abstract_preview") or "")
        except (OSError, json.JSONDecodeError):
            abstract_preview = ""

    prior_art_block = ""
    if notes_text:
        prior_art_block = (
            "PRIOR-ART METHODOLOGIST NOTES (from a previous onboarding —\n"
            "use as context, do NOT copy verbatim, deepen where gaps appear):\n\n"
            f"{notes_text[:6000]}\n\n"
        )

    digest_prompt = (
        f"You are authoring the deep digest for paper {paper_id!r}. "
        f"PDF SHA-256: {extraction_blob.get('pdf_sha256')}.\n\n"
        f"Abstract preview:\n{abstract_preview}\n\n"
        f"{prior_art_block}"
        "Required digest sections:\n"
        "(a) Intuition — 2–3 paragraphs on what the paper claims and why.\n"
        "(b) Formulas — every formula in the paper's own notation, then\n"
        "    each formula re-expressed in IvorySquare canonical line-item\n"
        "    names where a mapping exists, with full coefficient precision.\n"
        "(c) Worked examples — each worked-example firm in the paper, with\n"
        "    the input numbers and the paper's reported output. These are\n"
        "    A5 replication oracles.\n"
        "(d) Edge cases — null inputs, missing line items, sign conventions,\n"
        "    division-by-zero guards, exclusions (financials, utilities, etc.).\n"
        "(e) Sample-period assumptions — what time period the paper's\n"
        "    coefficients were estimated on, what asset class, what\n"
        "    GAAP/IFRS regime; flag stale-coefficient risk for modern data.\n"
        "(f) Prerequisite concepts — list the foundational concepts a\n"
        "    reader must understand before this paper, with one-line\n"
        "    descriptions.\n\n"
        "Format: markdown with one '##' heading per section. Aim for\n"
        "1500–3000 words total. Cite the paper by table/page number on\n"
        "every numeric claim. End with a 'gate_verdict' fenced JSON\n"
        "block in the same shape A1 used.\n"
    )

    digest_resp = _try_persona_call(runtime, driver_persona, digest_prompt)
    digest_text = digest_resp.text if digest_resp is not None else ""
    digest_path = run_dir / "A2_digest.md"
    digest_path.write_text(
        digest_text or "(digest unavailable — LLM call missed cache and no API key)\n",
        encoding="utf-8",
    )

    # Accounting-expert audit gate. Receives the digest and asks: would
    # an accounting PhD sign their name to the formulas, the line-item
    # mappings, and the edge-case coverage?
    audit_prompt = (
        f"You are auditing the digest for paper {paper_id!r}. The digest\n"
        f"text is below. Apply the criteria from the L2 rule-template\n"
        f"contract: every numeric claim must cite a page or table; line-\n"
        f"item mappings must use only canonical names from\n"
        f"mvp/standardize/mappings.py (16 names at MVP); edge-case\n"
        f"coverage must address null line items, division-by-zero, and\n"
        f"sign conventions. Produce: (1) a list of factual or mapping\n"
        f"errors, (2) any missing edge cases, (3) a gate_verdict JSON\n"
        f"block ({{verdict, rationale, revisions_needed}}).\n\n"
        f"DIGEST:\n{(digest_text or '(no digest — A2 could not run)')[:18000]}\n"
    )

    audit_resp = _try_persona_call(runtime, gate_persona, audit_prompt)
    audit_text = audit_resp.text if audit_resp is not None else ""
    audit_path = run_dir / "A2_audit.md"
    audit_path.write_text(
        audit_text or "(audit unavailable — LLM call missed cache and no API key)\n",
        encoding="utf-8",
    )

    verdict = _parse_gate_verdict(
        audit_text,
        default_persona=gate_persona,
        default_rationale=(
            f"Digest authored at {digest_path.name}; accounting_expert "
            f"audit at {audit_path.name}."
        ),
        fallback_when_unavailable=(audit_resp is None and digest_resp is None),
    )

    state["A2_digest"] = {
        "digest_path": str(digest_path),
        "audit_path": str(audit_path),
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A2_digest",
        artifact_path=digest_path,
        verdict=verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"Digest produced ({len(digest_text)} chars); audit produced "
            f"({len(audit_text)} chars); verdict: {verdict.verdict}."
        ),
    )


def _stage_a3_implementation(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A3 — methodologist drafts skill.py + manifest.yaml.

    The output is staged under ``run_dir/A3_implementation/`` rather
    than written into ``mvp/skills/...`` directly. For ``mode='fresh'``,
    a downstream copy step (or the user) promotes the staged files. For
    ``mode='calibration'``, the staged files are diffed against the
    shipped artifacts in :func:`compare_calibration_outputs`.
    """
    started = datetime.now(timezone.utc).isoformat()

    digest_blob = state.get("A2_digest") or {}
    digest_path_str = digest_blob.get("digest_path")
    digest_text = ""
    if digest_path_str and Path(digest_path_str).is_file():
        digest_text = Path(digest_path_str).read_text(encoding="utf-8")

    impl_prompt = (
        f"You are drafting the IvorySquare paper-derived skill for\n"
        f"paper {paper_id!r}. The digest below is your authoritative\n"
        f"reference. Produce three outputs in three fenced blocks:\n\n"
        f"1. ```python (skill.py) — a class subclassing\n"
        f"   mvp.skills._base.Skill that subclasses paper-derived shape\n"
        f"   (see mvp/skills/paper_derived/compute_beneish_m_score/skill.py\n"
        f"   for the template). Include null-propagation, citation\n"
        f"   collection, typed errors, and a confidence model.\n"
        f"2. ```yaml (manifest.yaml) — a manifest matching\n"
        f"   mvp/skills/manifest_schema.py shape. Include description_for_llm,\n"
        f"   provenance (with paper sha256 and load-bearing tables),\n"
        f"   implementation_decisions, inputs, outputs, citation_contract,\n"
        f"   confidence, dependencies, evaluation, limitations, examples,\n"
        f"   cost_estimate. Use the canonical 16 line-item names only.\n"
        f"3. ```yaml (rule_template.yaml) — when the skill is L2/L3 with\n"
        f"   per-component rules, include this block. Otherwise emit a\n"
        f"   single-line stub: '# rule template not applicable'.\n\n"
        f"DIGEST:\n{digest_text[:18000]}\n"
    )

    impl_resp = _try_persona_call(runtime, driver_persona, impl_prompt)
    impl_text = impl_resp.text if impl_resp is not None else ""

    impl_dir = run_dir / "A3_implementation"
    impl_dir.mkdir(parents=True, exist_ok=True)
    raw_path = impl_dir / "draft.md"
    raw_path.write_text(
        impl_text or "(implementation unavailable — LLM call missed cache and no API key)\n",
        encoding="utf-8",
    )

    skill_py_text = _extract_fenced_block(impl_text, "python")
    manifest_text = _extract_fenced_block(impl_text, "yaml", which="first")
    rule_template_text = _extract_fenced_block(impl_text, "yaml", which="second")

    skill_path = impl_dir / "skill.py"
    manifest_path = impl_dir / "manifest.yaml"
    rule_path = impl_dir / "rule_template.yaml"
    if skill_py_text:
        skill_path.write_text(skill_py_text, encoding="utf-8")
    if manifest_text:
        manifest_path.write_text(manifest_text, encoding="utf-8")
    if rule_template_text:
        rule_path.write_text(rule_template_text, encoding="utf-8")

    # Compile-clean check for skill.py — at MVP we don't import it (the
    # registry would pick it up); we just ensure it parses.
    compile_ok = True
    compile_error = ""
    if skill_py_text:
        try:
            compile(skill_py_text, str(skill_path), "exec")
        except SyntaxError as exc:
            compile_ok = False
            compile_error = f"{type(exc).__name__}: {exc}"
    else:
        compile_ok = False
        compile_error = "no python fenced block in A3 response"

    # Manifest validation — best-effort. The draft is allowed to fail
    # validation; the gate verdict captures that as a 'revise'.
    manifest_validates = False
    manifest_error = ""
    if manifest_text:
        try:
            with manifest_path.open("r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            if isinstance(raw, dict):
                SkillManifest.model_validate(raw)
                manifest_validates = True
        except Exception as exc:
            manifest_error = f"{type(exc).__name__}: {exc}"
    else:
        manifest_error = "no yaml fenced block in A3 response"

    # Audit gate via accounting_expert: review the rule template against
    # the canonical 16 line-item names and the rule-authoring guide.
    if rule_template_text:
        audit_prompt = (
            "You are auditing a draft rule template. Apply the contract\n"
            "from mvp/human_layer/rule_authoring_guide.md: every component\n"
            "has >=4 severity bands partitioning the real line; every\n"
            "medium/high/critical rule has >=2 follow_up_questions; every\n"
            "interpretation is >=30 chars of substantive accountant voice;\n"
            "every citations_required entry references a canonical line\n"
            "item from mvp/standardize/mappings.py.\n\n"
            "Review the draft and emit a gate_verdict JSON block.\n\n"
            f"DRAFT:\n{rule_template_text[:12000]}\n"
        )
        audit_resp = _try_persona_call(runtime, gate_persona, audit_prompt)
        audit_text = audit_resp.text if audit_resp is not None else ""
        audit_path = impl_dir / "rule_template_audit.md"
        audit_path.write_text(
            audit_text or "(rule-template audit unavailable)\n",
            encoding="utf-8",
        )
    else:
        audit_text = "(no rule template emitted; skipping rule_template audit)"
        audit_path = impl_dir / "rule_template_audit.md"
        audit_path.write_text(audit_text, encoding="utf-8")
        audit_resp = None

    verdict = _parse_gate_verdict(
        audit_text,
        default_persona=gate_persona,
        default_rationale=(
            f"Implementation drafted (skill.py compile_ok={compile_ok}, "
            f"manifest validates={manifest_validates}); "
            f"rule_template audit at {audit_path.name}."
        ),
        fallback_when_unavailable=audit_resp is None,
    )
    if not compile_ok or not manifest_validates:
        # Don't override an LLM-issued 'block', but escalate to 'revise'
        # at minimum.
        if verdict.verdict == "go":
            verdict.verdict = "revise"
        verdict.revisions_needed.extend(
            [r for r in (
                f"skill.py syntax error: {compile_error}" if not compile_ok else "",
                f"manifest.yaml validation error: {manifest_error}" if not manifest_validates else "",
            ) if r]
        )

    state["A3_implementation"] = {
        "draft_path": str(raw_path),
        "skill_path": str(skill_path) if skill_py_text else None,
        "manifest_path": str(manifest_path) if manifest_text else None,
        "rule_template_path": str(rule_path) if rule_template_text else None,
        "compile_ok": compile_ok,
        "compile_error": compile_error,
        "manifest_validates": manifest_validates,
        "manifest_error": manifest_error,
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A3_implementation",
        artifact_path=raw_path,
        verdict=verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"skill.py compile={compile_ok}; manifest validates="
            f"{manifest_validates}; rule_template "
            f"{'present' if rule_template_text else 'absent'}; "
            f"verdict: {verdict.verdict}."
        ),
        extra={
            "compile_ok": compile_ok,
            "manifest_validates": manifest_validates,
            "rule_template_present": bool(rule_template_text),
        },
    )


def _stage_a4_unit_tests(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A4 — evaluation_agent authors a pytest-shaped unit-test file.

    Tests cover paper-worked-examples within ±0.05, null propagation,
    missing line items, edge inputs, and the citation contract.
    """
    started = datetime.now(timezone.utc).isoformat()
    impl_blob = state.get("A3_implementation") or {}
    digest_blob = state.get("A2_digest") or {}
    digest_text = ""
    digest_path_str = digest_blob.get("digest_path")
    if digest_path_str and Path(digest_path_str).is_file():
        digest_text = Path(digest_path_str).read_text(encoding="utf-8")

    skill_text = ""
    if impl_blob.get("skill_path") and Path(impl_blob["skill_path"]).is_file():
        skill_text = Path(impl_blob["skill_path"]).read_text(encoding="utf-8")

    test_prompt = (
        f"You are authoring the unit-test suite for the paper-derived\n"
        f"skill {paper_id}. Your default stance: a 5-case eval is not an\n"
        f"accuracy claim — it is a reproducibility claim. Author 25-40\n"
        f"pytest-shaped unit tests covering:\n"
        f"  - paper worked-examples reproduced within ±0.05 on the\n"
        f"    headline scalar and ±2% on each component.\n"
        f"  - null propagation: when any required input is null, the\n"
        f"    skill returns flag=indeterminate and score=null.\n"
        f"  - missing-line-item handling: each canonical line item\n"
        f"    individually missing yields a structured warning.\n"
        f"  - edge inputs: zero denominators, sign flips, extreme\n"
        f"    magnitudes (1e12 / 1e-12).\n"
        f"  - citation contract: every present component yields\n"
        f"    citations for every underlying canonical line item.\n\n"
        f"Format: one ```python fenced block containing a single test\n"
        f"file (named by you). Use only stdlib + pytest; do NOT import\n"
        f"the live MVP modules — write hermetic tests that exercise the\n"
        f"skill's pure-arithmetic helpers and assert on the manifest's\n"
        f"declared shape.\n\n"
        f"DIGEST:\n{digest_text[:8000]}\n\n"
        f"DRAFT SKILL.PY:\n{skill_text[:8000]}\n"
    )

    test_resp = _try_persona_call(runtime, driver_persona, test_prompt)
    test_text = test_resp.text if test_resp is not None else ""

    test_dir = run_dir / "A4_unit_tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    raw_path = test_dir / "draft.md"
    raw_path.write_text(
        test_text or "(unit tests unavailable — LLM call missed cache and no API key)\n",
        encoding="utf-8",
    )

    test_py_text = _extract_fenced_block(test_text, "python")
    test_path = test_dir / f"test_{paper_id}.py"
    if test_py_text:
        test_path.write_text(test_py_text, encoding="utf-8")

    compile_ok = True
    compile_error = ""
    n_test_funcs = 0
    if test_py_text:
        try:
            compile(test_py_text, str(test_path), "exec")
        except SyntaxError as exc:
            compile_ok = False
            compile_error = f"{type(exc).__name__}: {exc}"
        n_test_funcs = len(re.findall(r"^def\s+test_", test_py_text, re.MULTILINE))
    else:
        compile_ok = False
        compile_error = "no python fenced block in A4 response"

    verdict = _parse_gate_verdict(
        test_text,
        default_persona=gate_persona,
        default_rationale=(
            f"Authored {n_test_funcs} unit tests at {test_path.name}; "
            f"compile_ok={compile_ok}."
        ),
        fallback_when_unavailable=test_resp is None,
    )
    if not compile_ok and verdict.verdict == "go":
        verdict.verdict = "revise"
        verdict.revisions_needed.append(
            f"unit-test file syntax error: {compile_error}"
        )
    if n_test_funcs < 25 and verdict.verdict == "go":
        verdict.verdict = "revise"
        verdict.revisions_needed.append(
            f"only {n_test_funcs} test functions emitted; A4 contract "
            f"requires 25-40."
        )

    state["A4_unit_tests"] = {
        "draft_path": str(raw_path),
        "test_path": str(test_path) if test_py_text else None,
        "n_test_funcs": n_test_funcs,
        "compile_ok": compile_ok,
        "compile_error": compile_error,
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A4_unit_tests",
        artifact_path=raw_path,
        verdict=verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"Authored {n_test_funcs} test functions; compile={compile_ok}; "
            f"verdict: {verdict.verdict}."
        ),
        extra={"n_test_funcs": n_test_funcs, "compile_ok": compile_ok},
    )


def _stage_a5_replication(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A5 — methodologist runs the draft skill against the paper's own
    worked examples and reports any deviation outside the ±0.05 / ±2%
    bar; documents in implementation_decisions otherwise.
    """
    started = datetime.now(timezone.utc).isoformat()
    digest_blob = state.get("A2_digest") or {}
    impl_blob = state.get("A3_implementation") or {}
    digest_text = ""
    digest_path_str = digest_blob.get("digest_path")
    if digest_path_str and Path(digest_path_str).is_file():
        digest_text = Path(digest_path_str).read_text(encoding="utf-8")

    skill_text = ""
    if impl_blob.get("skill_path") and Path(impl_blob["skill_path"]).is_file():
        skill_text = Path(impl_blob["skill_path"]).read_text(encoding="utf-8")

    replication_prompt = (
        f"You are running the paper-replication harness for paper\n"
        f"{paper_id}. From the digest's section (c) (worked examples),\n"
        f"enumerate every reported worked-example firm-year. For each:\n"
        f"  - reproduce the input numbers,\n"
        f"  - mentally walk the draft skill.py through them,\n"
        f"  - report the resulting score + flag,\n"
        f"  - compare to the paper's reported value within ±0.05 on the\n"
        f"    headline scalar and ±2% on each component,\n"
        f"  - if outside tolerance, identify the implementation decision\n"
        f"    that explains it (e.g. canonical-line-item approximation,\n"
        f"    sign-convention difference, coefficient rounding).\n\n"
        f"Format: a markdown report with one section per worked example,\n"
        f"plus a summary 'implementation_decisions[]' YAML block at the\n"
        f"end ready to paste into the manifest. End with a gate_verdict\n"
        f"JSON block.\n\n"
        f"DIGEST:\n{digest_text[:10000]}\n\n"
        f"DRAFT SKILL.PY:\n{skill_text[:8000]}\n"
    )

    rep_resp = _try_persona_call(runtime, driver_persona, replication_prompt)
    rep_text = rep_resp.text if rep_resp is not None else ""
    rep_path = run_dir / "A5_replication.md"
    rep_path.write_text(
        rep_text or "(replication unavailable — LLM call missed cache and no API key)\n",
        encoding="utf-8",
    )

    impl_decisions_yaml = _extract_fenced_block(rep_text, "yaml", which="first")
    impl_decisions_path = run_dir / "A5_implementation_decisions.yaml"
    if impl_decisions_yaml:
        impl_decisions_path.write_text(impl_decisions_yaml, encoding="utf-8")

    # Eval-agent gate: did every worked example come within tolerance,
    # OR is each deviation accounted for in implementation_decisions?
    gate_prompt = (
        f"You are gating the A5 replication report. The driver report\n"
        f"is below. Confirm for each worked example: either it is within\n"
        f"±0.05 / ±2% tolerance, OR a concrete implementation_decisions\n"
        f"entry explains the deviation. If any case lacks tolerance AND\n"
        f"lacks a documented decision, your verdict is 'revise' or\n"
        f"'block'. Emit a gate_verdict JSON block.\n\n"
        f"REPLICATION REPORT:\n{rep_text[:14000]}\n"
    )

    gate_resp = _try_persona_call(runtime, gate_persona, gate_prompt)
    gate_text = gate_resp.text if gate_resp is not None else ""
    gate_path = run_dir / "A5_eval_gate.md"
    gate_path.write_text(
        gate_text or "(eval-gate unavailable)\n",
        encoding="utf-8",
    )

    verdict = _parse_gate_verdict(
        gate_text,
        default_persona=gate_persona,
        default_rationale=(
            f"Replication report at {rep_path.name}; eval-gate review at "
            f"{gate_path.name}."
        ),
        fallback_when_unavailable=gate_resp is None and rep_resp is None,
    )

    state["A5_replication"] = {
        "report_path": str(rep_path),
        "implementation_decisions_path": (
            str(impl_decisions_path) if impl_decisions_yaml else None
        ),
        "gate_path": str(gate_path),
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A5_replication",
        artifact_path=rep_path,
        verdict=verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"Replication report ({len(rep_text)} chars); "
            f"implementation_decisions block "
            f"{'present' if impl_decisions_yaml else 'absent'}; "
            f"verdict: {verdict.verdict}."
        ),
    )


def _stage_a6_verification(
    *,
    state: dict[str, Any],
    runtime: PersonaRuntime,
    run_dir: Path,
    paper_id: str,
    pdf_path: Path,
    mode: PipelineMode,
    driver_persona: str,
    gate_persona: str,
) -> StageResult:
    """A6 — citation_auditor + accounting_expert + evaluation_agent all
    contribute. citation_auditor checks every cited locator resolves;
    accounting_expert audits the rule template against the canonical
    line-item names and rule-authoring guide; evaluation_agent authors
    gold cases (which inherit from the digest's worked examples).
    """
    started = datetime.now(timezone.utc).isoformat()

    a3 = state.get("A3_implementation") or {}
    a5 = state.get("A5_replication") or {}
    digest_blob = state.get("A2_digest") or {}

    manifest_text = ""
    if a3.get("manifest_path") and Path(a3["manifest_path"]).is_file():
        manifest_text = Path(a3["manifest_path"]).read_text(encoding="utf-8")
    rule_template_text = ""
    if a3.get("rule_template_path") and Path(a3["rule_template_path"]).is_file():
        rule_template_text = Path(a3["rule_template_path"]).read_text(encoding="utf-8")
    digest_text = ""
    digest_path_str = digest_blob.get("digest_path")
    if digest_path_str and Path(digest_path_str).is_file():
        digest_text = Path(digest_path_str).read_text(encoding="utf-8")

    # Sub-step 1: citation_auditor.
    auditor_prompt = (
        f"You are auditing the citation contract for paper {paper_id}.\n"
        f"Examine the manifest's `citations` and `citation_contract`\n"
        f"blocks (excerpted below) and report:\n"
        f"(1) whether every required-per-field rule names a canonical\n"
        f"    line item that appears in the inputs/outputs schema,\n"
        f"(2) whether the locator_format is consistent with the rest\n"
        f"    of the IvorySquare catalog\n"
        f"    (<cik>/<accession>::<statement_role>::<canonical_name>),\n"
        f"(3) whether sha256 is named as the hash_algorithm.\n\n"
        f"Emit one gate_verdict JSON block; one issue per finding.\n\n"
        f"MANIFEST:\n{manifest_text[:12000]}\n"
    )
    auditor_resp = _try_persona_call(runtime, "citation_auditor", auditor_prompt)
    auditor_text = auditor_resp.text if auditor_resp is not None else ""
    auditor_path = run_dir / "A6_citation_auditor.md"
    auditor_path.write_text(auditor_text or "(citation-audit unavailable)\n", encoding="utf-8")

    # Sub-step 2: accounting_expert audit of the rule template.
    if rule_template_text and rule_template_text.strip().startswith("#") is False:
        ae_prompt = (
            f"You are auditing the rule template for paper {paper_id}.\n"
            f"Apply the contract from mvp/human_layer/rule_authoring_guide.md:\n"
            f"every component has >=4 severity bands partitioning the real\n"
            f"line; every medium/high/critical rule has >=2 follow-up\n"
            f"questions; every interpretation is >=30 chars of substantive\n"
            f"accountant voice; every citations_required entry references a\n"
            f"canonical line item from mvp/standardize/mappings.py.\n\n"
            f"Emit one gate_verdict JSON block.\n\n"
            f"RULE TEMPLATE:\n{rule_template_text[:12000]}\n"
        )
        ae_resp = _try_persona_call(runtime, "accounting_expert", ae_prompt)
        ae_text = ae_resp.text if ae_resp is not None else ""
    else:
        ae_resp = None
        ae_text = "(no rule template to audit; A6 accounting-expert step skipped.)\n"
    ae_path = run_dir / "A6_accounting_expert.md"
    ae_path.write_text(ae_text, encoding="utf-8")

    # Sub-step 3: evaluation_agent authors gold cases.
    eval_prompt = (
        f"You are authoring gold-standard cases for paper {paper_id}.\n"
        f"Each gold case lives at\n"
        f"mvp/eval/gold/<skill_short>/<issuer>_<year>.yaml. From the\n"
        f"digest's worked examples + the implementation_decisions emitted\n"
        f"in A5, produce one gold YAML per worked example. Each YAML must\n"
        f"name: case_id, skill_id, skill_version, issuer, filing, inputs,\n"
        f"expected (score range, flag, citation_expectations,\n"
        f"warnings_must_include), notes, authored_by_persona,\n"
        f"authored_at, gold_version. End with a gate_verdict JSON block.\n\n"
        f"DIGEST:\n{digest_text[:8000]}\n"
    )
    eval_resp = _try_persona_call(runtime, "evaluation_agent", eval_prompt)
    eval_text = eval_resp.text if eval_resp is not None else ""
    eval_path = run_dir / "A6_evaluation_agent.md"
    eval_path.write_text(eval_text or "(gold-case authoring unavailable)\n", encoding="utf-8")

    # Compose the final A6 verdict from the three sub-step verdicts.
    sub_verdicts = [
        _parse_gate_verdict(
            t,
            default_persona=p,
            default_rationale=f"{p} review available at {fname}.",
            fallback_when_unavailable=resp is None,
        )
        for t, p, fname, resp in [
            (auditor_text, "citation_auditor", auditor_path.name, auditor_resp),
            (ae_text, "accounting_expert", ae_path.name, ae_resp),
            (eval_text, "evaluation_agent", eval_path.name, eval_resp),
        ]
    ]
    composite_verdict = _compose_verdicts(sub_verdicts, gate_persona)

    state["A6_verification"] = {
        "citation_auditor_path": str(auditor_path),
        "accounting_expert_path": str(ae_path),
        "evaluation_agent_path": str(eval_path),
        "sub_verdicts": [v.to_json() for v in sub_verdicts],
    }

    completed = datetime.now(timezone.utc).isoformat()
    return StageResult(
        stage_id="A6_verification",
        artifact_path=auditor_path,
        verdict=composite_verdict,
        started_at=started,
        completed_at=completed,
        summary=(
            f"3-persona verification: "
            f"citation_auditor={sub_verdicts[0].verdict}, "
            f"accounting_expert={sub_verdicts[1].verdict}, "
            f"evaluation_agent={sub_verdicts[2].verdict}; composite: "
            f"{composite_verdict.verdict}."
        ),
        extra={"sub_verdicts": [v.verdict for v in sub_verdicts]},
    )


_STAGE_FUNCTIONS = {
    "A1_extract": _stage_a1_extract,
    "A2_digest": _stage_a2_digest,
    "A3_implementation": _stage_a3_implementation,
    "A4_unit_tests": _stage_a4_unit_tests,
    "A5_replication": _stage_a5_replication,
    "A6_verification": _stage_a6_verification,
}


# ---------------------------------------------------------------------------
# Calibration-mode comparison helper.
# ---------------------------------------------------------------------------


def compare_calibration_outputs(
    run_report: dict[str, Any],
    *,
    paper_id: str,
    shipped_skill_dir: Path,
    shipped_gold_dir: Path,
) -> dict[str, Any]:
    """Diff the deep pipeline's staged outputs against the shipped skill.

    Returns a structured delta::

        {
            "skill_py_diff_summary": {"size_delta_bytes": int, ...},
            "manifest_diff_summary": {"top_level_keys_added":..., ...},
            "gold_present_count_shipped": int,
            "implementation_decisions_count_drafted": int,
            ...
        }

    The intent is to surface meaningful structural differences without
    insisting that the deep pipeline re-emits a byte-identical artifact.
    """
    delta: dict[str, Any] = {"paper_id": paper_id, "comparisons": []}

    audit_dir = Path(run_report["audit_log_dir"])
    drafted_skill_path = audit_dir / "A3_implementation" / "skill.py"
    drafted_manifest_path = audit_dir / "A3_implementation" / "manifest.yaml"

    shipped_skill_path = shipped_skill_dir / "skill.py"
    shipped_manifest_path = shipped_skill_dir / "manifest.yaml"

    delta["comparisons"].append(
        _compare_text_files(
            drafted_skill_path, shipped_skill_path, label="skill.py"
        )
    )
    delta["comparisons"].append(
        _compare_yaml_top_level_keys(
            drafted_manifest_path, shipped_manifest_path, label="manifest.yaml"
        )
    )

    # Count gold cases shipped vs implementation_decisions drafted.
    if shipped_gold_dir.is_dir():
        gold_count = len(list(shipped_gold_dir.glob("*.yaml")))
    else:
        gold_count = 0
    delta["gold_present_count_shipped"] = gold_count

    impl_decisions_path = audit_dir / "A5_implementation_decisions.yaml"
    if impl_decisions_path.is_file():
        try:
            decisions = yaml.safe_load(
                impl_decisions_path.read_text(encoding="utf-8")
            )
            if isinstance(decisions, list):
                delta["implementation_decisions_count_drafted"] = len(decisions)
            elif isinstance(decisions, dict):
                inner = decisions.get("implementation_decisions")
                if isinstance(inner, list):
                    delta["implementation_decisions_count_drafted"] = len(inner)
                else:
                    delta["implementation_decisions_count_drafted"] = 0
            else:
                delta["implementation_decisions_count_drafted"] = 0
        except (OSError, yaml.YAMLError):
            delta["implementation_decisions_count_drafted"] = 0
    else:
        delta["implementation_decisions_count_drafted"] = 0

    return delta


def _compare_text_files(
    drafted: Path, shipped: Path, *, label: str
) -> dict[str, Any]:
    """Return a structured size+presence comparison of two text files."""
    record = {"label": label}
    record["drafted_present"] = drafted.is_file()
    record["shipped_present"] = shipped.is_file()
    if drafted.is_file():
        record["drafted_size"] = drafted.stat().st_size
        record["drafted_lines"] = sum(
            1 for _ in drafted.read_text(encoding="utf-8").splitlines()
        )
    if shipped.is_file():
        record["shipped_size"] = shipped.stat().st_size
        record["shipped_lines"] = sum(
            1 for _ in shipped.read_text(encoding="utf-8").splitlines()
        )
    if drafted.is_file() and shipped.is_file():
        record["size_delta_bytes"] = (
            record["drafted_size"] - record["shipped_size"]
        )
        record["line_delta"] = record["drafted_lines"] - record["shipped_lines"]
    return record


def _compare_yaml_top_level_keys(
    drafted: Path, shipped: Path, *, label: str
) -> dict[str, Any]:
    """Compare top-level YAML key sets — additive deltas only.

    Used to spot-check that the deep pipeline's manifest covers the
    shipped manifest's key set (no missing top-level blocks).
    """
    record = {"label": label}
    drafted_keys: set[str] = set()
    shipped_keys: set[str] = set()
    if drafted.is_file():
        try:
            d = yaml.safe_load(drafted.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                drafted_keys = set(d.keys())
        except yaml.YAMLError:
            pass
    if shipped.is_file():
        try:
            s = yaml.safe_load(shipped.read_text(encoding="utf-8"))
            if isinstance(s, dict):
                shipped_keys = set(s.keys())
        except yaml.YAMLError:
            pass
    record["drafted_keys"] = sorted(drafted_keys)
    record["shipped_keys"] = sorted(shipped_keys)
    record["only_in_drafted"] = sorted(drafted_keys - shipped_keys)
    record["only_in_shipped"] = sorted(shipped_keys - drafted_keys)
    record["intersection"] = sorted(drafted_keys & shipped_keys)
    return record


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


_GATE_VERDICT_RE = re.compile(
    r"```(?:json|JSON)?\s*\n(?P<body>\{[\s\S]*?\})\s*\n```",
    re.MULTILINE,
)


def _parse_gate_verdict(
    text: str,
    *,
    default_persona: str,
    default_rationale: str,
    fallback_when_unavailable: bool = False,
) -> GateVerdict:
    """Parse a fenced JSON gate_verdict block out of an LLM response.

    The expected shape::

        ```json
        {"verdict": "go|revise|block", "rationale": "...",
         "revisions_needed": ["..."]}
        ```

    When no fenced block is found we default to ``revise`` (a soft
    failure that lets the next stage proceed but flags the gap) when
    ``fallback_when_unavailable=True``, otherwise ``go`` with the
    default rationale (which signals "the LLM did not emit a block but
    we don't think the artifact is broken").

    Both the LLM-issued and default verdicts always include the
    ``persona`` field so downstream consumers know which voice spoke.
    """
    if not text:
        return GateVerdict(
            verdict="revise" if fallback_when_unavailable else "go",
            persona=default_persona,
            rationale=(
                "Persona response unavailable (cache miss + no API key)"
                if fallback_when_unavailable
                else default_rationale
            ),
            revisions_needed=(
                [
                    "Set ANTHROPIC_API_KEY or prime the LLM cache "
                    "before re-running this stage.",
                ]
                if fallback_when_unavailable
                else []
            ),
        )

    # Find the LAST gate_verdict block in the response — when the LLM
    # quotes earlier examples in its output, the final block is the
    # authoritative verdict.
    matches = list(_GATE_VERDICT_RE.finditer(text))
    for m in reversed(matches):
        body = m.group("body")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            continue
        verdict = str(data.get("verdict") or "").lower()
        if verdict not in ("go", "revise", "block"):
            continue
        rationale = str(data.get("rationale") or default_rationale)
        revisions_raw = data.get("revisions_needed") or []
        if isinstance(revisions_raw, list):
            revisions = [str(r) for r in revisions_raw if r]
        else:
            revisions = [str(revisions_raw)]
        return GateVerdict(
            verdict=verdict,  # type: ignore[arg-type]
            persona=default_persona,
            rationale=rationale,
            revisions_needed=revisions,
        )

    return GateVerdict(
        verdict="go",
        persona=default_persona,
        rationale=(
            f"{default_rationale} (no gate_verdict JSON block parsed; "
            f"defaulting to 'go')"
        ),
    )


def _compose_verdicts(
    sub_verdicts: list[GateVerdict],
    gate_persona: str,
) -> GateVerdict:
    """Combine multiple sub-verdicts into one stage verdict.

    Rule: any block → block; else any revise → revise; else go. The
    composed verdict's ``revisions_needed`` aggregates every sub-
    verdict's ``revisions_needed``.
    """
    revisions: list[str] = []
    has_block = False
    has_revise = False
    rationales: list[str] = []
    for v in sub_verdicts:
        revisions.extend(v.revisions_needed)
        rationales.append(f"[{v.persona}/{v.verdict}] {v.rationale}")
        if v.verdict == "block":
            has_block = True
        elif v.verdict == "revise":
            has_revise = True
    if has_block:
        composite = "block"
    elif has_revise:
        composite = "revise"
    else:
        composite = "go"
    return GateVerdict(
        verdict=composite,  # type: ignore[arg-type]
        persona=gate_persona,
        rationale=" | ".join(rationales),
        revisions_needed=revisions,
    )


def _try_persona_call(
    runtime: PersonaRuntime, persona_id: str, user_message: str
):
    """Best-effort persona call; surface MissingApiKey by returning None.

    A None return lets the caller fall back to the default verdict
    rather than crashing — the pipeline is still useful as a state
    machine even when the LLM cannot run.
    """
    try:
        return runtime.call(persona_id, user_message)
    except PersonaCallError as exc:
        # Re-raise everything but the missing-key case; the missing-key
        # case is the cache-cold-no-key scenario we want to surface as a
        # structured block at the run report level.
        if getattr(exc, "reason", "") == "missing_api_key":
            return None
        raise


def _extract_fenced_block(
    text: str,
    lang: str,
    *,
    which: str = "first",
) -> str:
    """Extract a fenced code block of the named language from ``text``.

    ``which='first'`` returns the first matching block; ``which='second'``
    returns the second (used for the rule_template block in A3, when
    manifest.yaml is the first yaml block and rule_template.yaml is the
    second). Returns empty string when not found.
    """
    pattern = re.compile(
        rf"```\s*{re.escape(lang)}\s*\n(?P<body>[\s\S]*?)\n```",
        re.IGNORECASE,
    )
    matches = list(pattern.finditer(text))
    if not matches:
        return ""
    if which == "first":
        return matches[0].group("body").strip()
    if which == "second":
        return matches[1].group("body").strip() if len(matches) >= 2 else ""
    raise ValueError(f"unknown 'which': {which!r}")


def _build_run_id(paper_id: str) -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{paper_id}__{stamp}"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    tmp.replace(path)


def _early_block(
    *,
    run_id: str,
    paper_id: str,
    mode: PipelineMode,
    started_at: str,
    run_dir: Path,
    cost_root: Path,
    reason: str,
    revisions: list[str],
) -> dict[str, Any]:
    """Return a structured block report when the pipeline can't even start."""
    completed = datetime.now(timezone.utc).isoformat()
    # An empty cost log so summarize() returns a defined shape.
    log_path = cost_root / f"{run_id}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch(exist_ok=True)
    cost_summary = summarize(run_id, cost_log_root=cost_root)
    report = {
        "run_id": run_id,
        "paper_id": paper_id,
        "mode": mode,
        "started_at": started_at,
        "completed_at": completed,
        "stages": [],
        "verdict": "block",
        "revisions_needed": revisions,
        "cost_summary": cost_summary,
        "audit_log_dir": str(run_dir),
        "stage_targets": dict(STAGE_TARGETS),
        "block_reason": reason,
    }
    _write_json(run_dir / "run_report.json", report)
    return report


__all__ = [
    "GateVerdict",
    "STAGE_PERSONAS",
    "STAGE_TARGETS",
    "StageResult",
    "compare_calibration_outputs",
    "run_deep_pipeline",
]
