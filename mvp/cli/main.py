"""MVP CLI entry point — Phases 4 + 5 + 6 scope.

Subcommands:

- ``mvp ingest filings --cik <cik> --years 1999,2000 [--batch all]`` —
  batch-ingest sample 10-K filings (Phase 6).
- ``mvp ingest paper --id <paper_id> [--batch all]`` — ingest one or
  both sample academic papers (Phase 6).
- ``mvp run <skill_id> [--cik ... --year ... | --json <path> | k=v ...]`` —
  invoke a skill and print its JSON output (Phase 4 + extended Phase 6).
- ``mvp eval [--gold-root <path>]`` — run the eval harness + citation
  check and print the one-page report (Phase 5).
- ``mvp audit citations [--gold-root <path>]`` — run only the citation
  check and print its report (Phase 5).
- ``mvp audit log [--persona P --since DATE]`` — list persona-runtime
  audit-log entries under ``mvp/agents/audit_log/`` (Phase 6).
- ``mvp skills list`` — one-line-per-skill catalogue (Phase 6).
- ``mvp skills show <skill_id>`` — full manifest YAML (Phase 6).
- ``mvp skills mcp`` — MCP tool catalog as JSON (Phase 6).
- ``mvp skills openai`` — OpenAI tool-use catalog as JSON (Phase 6).
- ``mvp skills cost <skill_id>`` — aggregate cost-log entries for the
  named skill across all runs (post-MVP Workstream A).
- ``mvp resolve-citation <doc_id> <locator>`` — resolve a citation via
  the engine's citation validator (Phase 6).

Every error-path returns exit code 1 with the 5-field structured error
envelope printed to stderr. Argparse-level errors return exit code 2.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import sample_filings
from mvp.skills.registry import default_registry


# ---------------------------------------------------------------------------
# Structured error printing.
# ---------------------------------------------------------------------------


def _print_envelope(
    *,
    error_code: str,
    error_category: str,
    human_message: str,
    retry_safe: bool,
    suggested_remediation: str,
) -> None:
    """Print a 5-field envelope to stderr as JSON, matching the API."""
    envelope = {
        "error_code": error_code,
        "error_category": error_category,
        "human_message": human_message,
        "retry_safe": retry_safe,
        "suggested_remediation": suggested_remediation,
    }
    json.dump(envelope, sys.stderr, indent=2, ensure_ascii=False)
    sys.stderr.write("\n")


def _print_skill_error(err_block: dict[str, Any]) -> None:
    """Project a skill's ``{"error": {...}}`` block onto the 5-field envelope."""
    _print_envelope(
        error_code=str(err_block.get("error_code", "internal_error")),
        error_category=str(err_block.get("error_category", "internal")),
        human_message=str(err_block.get("human_message", "")),
        retry_safe=bool(err_block.get("retry_safe", False)),
        suggested_remediation=str(err_block.get("suggested_remediation", "")),
    )


# ---------------------------------------------------------------------------
# Input coercion.
# ---------------------------------------------------------------------------


def _resolve_fiscal_year_end(cik: str, year_arg: str) -> str | None:
    """Normalise ``--year`` to a fiscal_year_end ISO date.

    A 4-digit integer is treated as a calendar year and mapped to the
    sample filing whose CIK matches and whose fiscal_period_end starts
    with that year. An ISO date (``yyyy-mm-dd``) is returned verbatim.
    Returns ``None`` when no mapping is available — caller must surface
    a structured error.
    """
    if len(year_arg) == 10 and year_arg[4] == "-" and year_arg[7] == "-":
        return year_arg
    if not year_arg.isdigit() or len(year_arg) != 4:
        return None
    for ref in sample_filings():
        if ref.cik == cik and ref.fiscal_period_end.startswith(year_arg):
            return ref.fiscal_period_end
    return None


def _parse_key_value(items: list[str]) -> dict[str, Any] | str:
    """Parse ``key=value`` positionals into a dict.

    Value parsing:
    - ``true`` / ``false`` → bool.
    - Integer literal → int.
    - Float literal → float.
    - ``null`` → ``None``.
    - ``{...}`` / ``[...]`` → JSON-parsed.
    - Otherwise → string verbatim.

    Returns the dict on success, a string error message on malformed
    input (caller turns it into a structured error envelope).
    """
    out: dict[str, Any] = {}
    for raw in items:
        if "=" not in raw:
            return f"positional arg {raw!r} missing '=' separator (use key=value)"
        key, val = raw.split("=", 1)
        key = key.strip()
        val = val.strip()
        if not key:
            return f"positional arg {raw!r} has empty key"
        out[key] = _coerce_scalar(val)
    return out


def _coerce_scalar(val: str) -> Any:
    if val.lower() == "true":
        return True
    if val.lower() == "false":
        return False
    if val.lower() == "null":
        return None
    if val and (val[0] in "{[\""):
        try:
            return json.loads(val)
        except json.JSONDecodeError:
            return val
    # Try int, then float, else leave as string. ValueError at each step
    # simply means "this parser didn't apply" — cascade to the next one
    # via contextlib.suppress (no silent swallow; the final ``return val``
    # below is the documented fall-through).
    with contextlib.suppress(ValueError):
        # Avoid bool-as-int confusion — already handled above.
        return int(val)
    with contextlib.suppress(ValueError):
        return float(val)
    return val


# ---------------------------------------------------------------------------
# ingest subcommands.
# ---------------------------------------------------------------------------


def _cmd_ingest_filings(args: argparse.Namespace) -> int:
    from mvp.ingestion.filings_ingest import (
        ingest_filing,
        sample_filings as _samples,
    )
    from mvp.lib.errors import IngestionError

    pairs: list[tuple[str, str]] = []  # (cik, accession)
    if args.batch == "all":
        pairs = [(f.cik, f.accession) for f in _samples()]
    else:
        if not args.cik:
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message="--cik is required unless --batch all is passed",
                retry_safe=False,
                suggested_remediation="Pass --cik <10-digit> and --years YYYY[,YYYY].",
            )
            return 1
        if not args.years:
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message="--years is required unless --batch all is passed",
                retry_safe=False,
                suggested_remediation="Pass a comma-separated list, e.g. --years 1999,2000.",
            )
            return 1
        years = [y.strip() for y in args.years.split(",") if y.strip()]
        for year in years:
            ref = _find_sample_for_year(args.cik, year)
            if ref is None:
                _print_envelope(
                    error_code="unknown_filing",
                    error_category="input_validation",
                    human_message=(
                        f"no sample filing registered for cik={args.cik!r} year={year!r}"
                    ),
                    retry_safe=False,
                    suggested_remediation=(
                        "The MVP ships a fixed 10-filing sample; "
                        "use 'mvp skills list' or see BUILD_REFS.md for the supported pairs."
                    ),
                )
                return 1
            pairs.append((ref.cik, ref.accession))

    results: list[dict[str, Any]] = []
    try:
        for cik, accession in pairs:
            result = ingest_filing(cik, accession)
            results.append(result.model_dump())
    except IngestionError as exc:
        _print_envelope(
            error_code=exc.error_code,
            error_category=exc.error_category.value,
            human_message=exc.message,
            retry_safe=exc.retry_safe,
            suggested_remediation=(
                f"target={exc.target!r} reason={exc.reason!r}. "
                "Re-check the CIK/accession pair against the sample catalogue."
            ),
        )
        return 1
    json.dump(results, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
    return 0


def _cmd_ingest_paper(args: argparse.Namespace) -> int:
    from mvp.ingestion.papers_ingest import ingest_paper, sample_papers
    from mvp.lib.errors import IngestionError

    paper_ids: list[str] = []
    if args.batch == "all":
        paper_ids = [p.paper_id for p in sample_papers()]
    else:
        if not args.id:
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message="--id is required unless --batch all is passed",
                retry_safe=False,
                suggested_remediation="Pass --id beneish_1999 or --id altman_1968.",
            )
            return 1
        paper_ids = [args.id]

    out: list[dict[str, Any]] = []
    try:
        for pid in paper_ids:
            result = ingest_paper(pid)
            out.append(result.model_dump())
    except IngestionError as exc:
        _print_envelope(
            error_code=exc.error_code,
            error_category=exc.error_category.value,
            human_message=exc.message,
            retry_safe=exc.retry_safe,
            suggested_remediation=(
                f"target={exc.target!r} reason={exc.reason!r}. "
                "Valid paper ids are 'beneish_1999' and 'altman_1968'."
            ),
        )
        return 1
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
    return 0


def _find_sample_for_year(cik: str, year: str) -> Any:
    for ref in sample_filings():
        if ref.cik == cik and ref.fiscal_period_end.startswith(year):
            return ref
    return None


# ---------------------------------------------------------------------------
# run subcommand.
# ---------------------------------------------------------------------------


def _cmd_run(args: argparse.Namespace) -> int:
    registry = default_registry()
    try:
        skill = registry.get(args.skill_id)
    except KeyError:
        _print_envelope(
            error_code="skill_not_found",
            error_category="input_validation",
            human_message=f"no skill registered with id={args.skill_id!r}",
            retry_safe=False,
            suggested_remediation=(
                "Use 'mvp skills list' to see registered skills, "
                "then retry with a valid id. Known ids: "
                + ", ".join(registry.ids())
            ),
        )
        return 1

    # Build input payload — precedence: --json > scalar flags > k=v positionals.
    inputs: dict[str, Any] = {}
    if args.json is not None:
        try:
            inputs.update(_load_json_payload(args.json))
        except (OSError, json.JSONDecodeError) as exc:
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message=f"could not load --json payload: {exc}",
                retry_safe=False,
                suggested_remediation=(
                    "Pass a path to a valid JSON file (use '@path.json' or 'path.json')."
                ),
            )
            return 1

    # Scalar flags overlay on top of --json (explicit flags beat file contents).
    if args.cik is not None:
        inputs["cik"] = args.cik
    if args.year is not None:
        fye = _resolve_fiscal_year_end(args.cik or inputs.get("cik", ""), args.year)
        if fye is None:
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message=(
                    f"--year={args.year!r} did not resolve to a fiscal_year_end "
                    f"for cik={args.cik!r}"
                ),
                retry_safe=False,
                suggested_remediation=(
                    "Pass --year as yyyy-mm-dd, or use a calendar year that maps "
                    "to a filing in the MVP sample set."
                ),
            )
            return 1
        inputs["fiscal_year_end"] = fye
    if args.accession is not None:
        inputs["accession"] = args.accession

    if args.kv:
        parsed = _parse_key_value(args.kv)
        if isinstance(parsed, str):
            _print_envelope(
                error_code="input_validation",
                error_category="input_validation",
                human_message=parsed,
                retry_safe=False,
                suggested_remediation=(
                    "Positional overrides use 'key=value'; quote JSON values "
                    "and escape spaces."
                ),
            )
            return 1
        inputs.update(parsed)

    # Reject unknown keys per manifest (skill.run also does schema
    # validation, but a pre-check gives a friendlier error before we
    # hit the jsonschema layer).
    allowed = set((skill.manifest.inputs.get("properties") or {}).keys())
    extra = set(inputs.keys()) - allowed
    additional_props = skill.manifest.inputs.get("additionalProperties", True)
    if extra and additional_props is False:
        _print_envelope(
            error_code="input_validation",
            error_category="input_validation",
            human_message=(
                f"skill {args.skill_id!r} rejects unknown input keys: "
                f"{sorted(extra)}. Allowed: {sorted(allowed)}."
            ),
            retry_safe=False,
            suggested_remediation=(
                f"Use 'mvp skills show {args.skill_id}' to see the input schema."
            ),
        )
        return 1

    result = skill.run(inputs)
    if args.format == "jsonl":
        json.dump(result, sys.stdout, ensure_ascii=False, default=str, separators=(",", ":"))
    else:
        json.dump(result, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
    # A returned error envelope counts as exit 1 with the envelope ALSO
    # printed to stderr for consistency with every other CLI error path.
    err_block = result.get("error") if isinstance(result, dict) else None
    if isinstance(err_block, dict):
        _print_skill_error(err_block)
        return 1
    return 0


def _load_json_payload(spec: str) -> dict[str, Any]:
    """Load a JSON object from a path. Accepts both ``@path`` and plain path."""
    path_str = spec[1:] if spec.startswith("@") else spec
    data = json.loads(Path(path_str).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise json.JSONDecodeError(
            f"--json payload must be an object, got {type(data).__name__}", path_str, 0
        )
    return data


# ---------------------------------------------------------------------------
# eval + audit subcommands (Phase 5 — unchanged).
# ---------------------------------------------------------------------------


def _cmd_eval(args: argparse.Namespace) -> int:
    from mvp.eval.runner import format_console_report, run_eval

    report = run_eval(gold_root=args.gold_root, write_report=not args.no_report_file)
    sys.stdout.write(format_console_report(report))
    m = report.metrics
    gate_pass = (
        m.m_score_within_0_10[0] >= 4
        and m.m_score_flag_match_rate[0] >= 4
        and m.z_score_within_0_10[0] >= 4
        and m.z_score_zone_match_rate[0] >= 4
        and m.citation_resolves[0] == m.citation_resolves[1]
        and m.gold_present_for_all_cases[0] == m.gold_present_for_all_cases[1]
    )
    return 0 if gate_pass else 1


def _cmd_audit_citations(args: argparse.Namespace) -> int:
    from mvp.eval.citation_check import check_citations, format_console_report

    report = check_citations(gold_root=args.gold_root)
    sys.stdout.write(format_console_report(report))
    return 0 if report.resolution_rate == 1.0 else 2


def _cmd_audit_log(args: argparse.Namespace) -> int:
    """Summarise persona-runtime audit-log entries."""
    from datetime import datetime

    mvp_root = Path(__file__).resolve().parent.parent
    log_dir = mvp_root / "agents" / "audit_log"
    if not log_dir.is_dir():
        _print_envelope(
            error_code="audit_log_unavailable",
            error_category="io",
            human_message=f"audit log directory does not exist: {log_dir}",
            retry_safe=False,
            suggested_remediation=(
                "Run a skill that invokes a persona to populate audit_log/, "
                "or check the repository layout."
            ),
        )
        return 1

    entries: list[dict[str, Any]] = []
    for path in sorted(log_dir.glob("*.json")):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        persona_id = str(raw.get("persona_id", ""))
        called_at = str(raw.get("called_at", ""))
        if args.persona and persona_id != args.persona:
            continue
        if args.since:
            # Malformed --since or called_at falls through to "include the
            # entry" (err on the side of visibility). contextlib.suppress
            # is the documented no-op for this parser-cascade idiom.
            with contextlib.suppress(ValueError):
                since_dt = datetime.fromisoformat(args.since)
                call_dt = datetime.fromisoformat(called_at.replace("Z", "+00:00"))
                if call_dt.replace(tzinfo=None) < since_dt.replace(tzinfo=None):
                    continue
        entries.append(
            {
                "file": path.name,
                "persona_id": persona_id,
                "persona_version": raw.get("persona_version", ""),
                "called_at": called_at,
                "cache_hit": raw.get("cache_hit"),
                "input_tokens": raw.get("input_tokens"),
                "output_tokens": raw.get("output_tokens"),
            }
        )

    if not entries:
        sys.stdout.write(f"# No audit-log entries matched filters under {log_dir}\n")
        return 0

    # Compact, reviewable one-line-per-entry summary + JSON footer.
    sys.stdout.write(f"# {len(entries)} audit-log entries under {log_dir}\n")
    for e in entries:
        sys.stdout.write(
            f"  {e['file']:<64s} persona={e['persona_id']:<32s} "
            f"called_at={e['called_at']} cache_hit={e['cache_hit']} "
            f"tokens_in={e['input_tokens']} out={e['output_tokens']}\n"
        )
    return 0


# ---------------------------------------------------------------------------
# skills subcommands (Phase 6).
# ---------------------------------------------------------------------------


def _cmd_skills_list(_args: argparse.Namespace) -> int:
    import yaml  # pyyaml ships with the project

    registry = default_registry()
    for manifest in registry.list_skills():
        desc = manifest.description_for_llm.strip().replace("\n", " ")
        short = desc[:80] + ("..." if len(desc) > 80 else "")
        sys.stdout.write(
            f"{manifest.skill_id:<36s} v{manifest.version:<7s} "
            f"{manifest.layer:<15s} {manifest.status:<10s} {short}\n"
        )
    return 0


def _cmd_skills_show(args: argparse.Namespace) -> int:
    import yaml

    registry = default_registry()
    try:
        skill = registry.get(args.skill_id)
    except KeyError:
        _print_envelope(
            error_code="skill_not_found",
            error_category="input_validation",
            human_message=f"no skill registered with id={args.skill_id!r}",
            retry_safe=False,
            suggested_remediation=(
                "Use 'mvp skills list' to see registered skills."
            ),
        )
        return 1
    dumped = skill.manifest.model_dump(mode="json")
    sys.stdout.write(yaml.safe_dump(dumped, sort_keys=False, allow_unicode=True))
    return 0


def _cmd_skills_mcp(_args: argparse.Namespace) -> int:
    registry = default_registry()
    catalog = {"tools": registry.mcp_catalog(), "count": len(registry.mcp_catalog())}
    json.dump(catalog, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_skills_openai(_args: argparse.Namespace) -> int:
    registry = default_registry()
    tools = registry.openai_catalog()
    catalog = {"tools": tools, "count": len(tools)}
    json.dump(catalog, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_skills_cost(args: argparse.Namespace) -> int:
    """Aggregate cost-log entries across all deep-pipeline runs for a skill.

    Walks ``mvp/agents/cost_log/<run_id>.jsonl`` and surfaces the runs
    whose ``paper_id`` (after deriving the skill_id from the paper-to-
    skill mapping) matches ``args.skill_id``. Output: JSON shape with
    per-stage totals across the matching runs.
    """
    from mvp.lib.cost_tracking import (
        DEFAULT_COST_LOG_ROOT,
        STAGE_IDS,
        summarize,
    )

    cost_root = (
        Path(args.cost_log_root)
        if getattr(args, "cost_log_root", None)
        else DEFAULT_COST_LOG_ROOT
    )

    if not cost_root.is_dir():
        _print_envelope(
            error_code="cost_log_root_missing",
            error_category="input_validation",
            human_message=f"cost-log directory does not exist at {cost_root}",
            retry_safe=False,
            suggested_remediation=(
                "Run a deep-pipeline orchestrator invocation first; "
                "the cost log is created on the first record."
            ),
        )
        return 1

    matched_runs: list[dict[str, Any]] = []
    aggregate_per_stage: dict[str, dict[str, int]] = {
        s: {
            "n_calls": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "cache_read_tokens": 0,
            "cache_creation_tokens": 0,
            "tokens_total": 0,
        }
        for s in STAGE_IDS
    }
    aggregate_n_calls = 0
    aggregate_tokens_total = 0

    for jsonl in sorted(cost_root.glob("*.jsonl")):
        run_id = jsonl.stem
        try:
            run_summary = summarize(run_id, cost_log_root=cost_root)
        except FileNotFoundError:
            continue
        # Match the run to the requested skill via the paper_id field.
        paper_ids = run_summary.get("paper_ids") or []
        match = False
        for pid in paper_ids:
            if pid == args.skill_id:
                match = True
                break
            # Allow loose matching where the skill_id starts with
            # 'compute_' and the paper_id is a prefix of the skill_id
            # (the typical convention) — this covers the
            # paper_id="beneish_1999" → skill_id="compute_beneish_m_score"
            # mapping.
            if args.skill_id.endswith(pid) or pid in args.skill_id:
                match = True
                break
        if not match:
            continue
        matched_runs.append(
            {"run_id": run_id, "summary": run_summary}
        )
        aggregate_n_calls += run_summary["n_calls"]
        aggregate_tokens_total += run_summary["totals"]["tokens_total"]
        for stage_id, bucket in run_summary["by_stage"].items():
            if stage_id not in aggregate_per_stage:
                continue
            target = aggregate_per_stage[stage_id]
            target["n_calls"] += bucket["n_calls"]
            target["input_tokens"] += bucket["input_tokens"]
            target["output_tokens"] += bucket["output_tokens"]
            target["cache_read_tokens"] += bucket["cache_read_tokens"]
            target["cache_creation_tokens"] += bucket["cache_creation_tokens"]
            target["tokens_total"] += bucket["tokens_total"]

    out = {
        "skill_id": args.skill_id,
        "matched_run_count": len(matched_runs),
        "aggregate_n_calls": aggregate_n_calls,
        "aggregate_tokens_total": aggregate_tokens_total,
        "by_stage": aggregate_per_stage,
        "runs": [r["run_id"] for r in matched_runs],
    }
    json.dump(out, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


# ---------------------------------------------------------------------------
# resolve-citation subcommand (Phase 6).
# ---------------------------------------------------------------------------


def _cmd_resolve_citation(args: argparse.Namespace) -> int:
    from mvp.engine.citation_validator import resolve_citation
    from mvp.lib.citation import Citation
    from pydantic import ValidationError

    from datetime import datetime, timezone

    try:
        citation = Citation(
            doc_id=args.doc_id,
            locator=args.locator,
            excerpt_hash=args.excerpt_hash or "0" * 64,
            retrieved_at=datetime.now(timezone.utc),
        )
    except ValidationError as exc:
        _print_envelope(
            error_code="input_validation",
            error_category="input_validation",
            human_message=f"citation shape invalid: {exc}",
            retry_safe=False,
            suggested_remediation=(
                "doc_id is '<cik>/<accession>' or 'market_data/equity_values'; "
                "locator is '<doc_id>::<role>::<line_item>'."
            ),
        )
        return 1

    resolved = resolve_citation(citation)
    json.dump(resolved, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0 if resolved.get("resolved") else 1


# ---------------------------------------------------------------------------
# curriculum subcommands (foundational layer).
# ---------------------------------------------------------------------------


def _cmd_curriculum_ingest(args: argparse.Namespace) -> int:
    from mvp.curriculum.toc_ingest import ingest_toc

    if not args.toc_path.is_file():
        _print_envelope(
            error_code="input_validation",
            error_category="input_validation",
            human_message=f"TOC YAML not found at {args.toc_path}",
            retry_safe=False,
            suggested_remediation=(
                "Pass an existing path. TOC YAMLs live under "
                "mvp/curriculum/tocs/<book_id>.yaml."
            ),
        )
        return 1
    try:
        result = ingest_toc(args.toc_path)
    except (ValueError, FileNotFoundError) as exc:
        _print_envelope(
            error_code="input_validation",
            error_category="input_validation",
            human_message=str(exc),
            retry_safe=False,
            suggested_remediation=(
                "Check that the TOC YAML matches the documented schema "
                "(book_id, branch, chapters[].sections[].subsections[])."
            ),
        )
        return 1
    if result.book_id != args.book_id:
        sys.stdout.write(
            f"# warning: TOC book_id={result.book_id!r} differs from CLI "
            f"argument {args.book_id!r}\n"
        )
    payload = {
        "book_id": result.book_id,
        "branch": result.branch,
        "nodes_added": result.nodes_added,
        "nodes_skipped": result.nodes_skipped,
        "edges_added": result.edges_added,
    }
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_curriculum_filter(args: argparse.Namespace) -> int:
    from dataclasses import asdict

    from mvp.curriculum.graph import load_default
    from mvp.curriculum.llm_baseline import (
        decide_materialization,
        load_question_bank,
        run_baseline,
    )

    graph = load_default()
    if args.node_id not in graph.nodes:
        _print_envelope(
            error_code="unknown_node",
            error_category="input_validation",
            human_message=f"node {args.node_id!r} is not in the curriculum graph",
            retry_safe=False,
            suggested_remediation=(
                "Run 'mvp curriculum ingest' first, or check the node id with "
                "'mvp curriculum graph'."
            ),
        )
        return 1

    qb_path = args.question_bank
    if qb_path is None:
        # Default location: under the foundational draft directory keyed by node id.
        qb_path = _resolve_default_question_bank(args.node_id)
    if qb_path is None or not qb_path.is_file():
        _print_envelope(
            error_code="missing_question_bank",
            error_category="input_validation",
            human_message=(
                f"no question bank found for {args.node_id!r}; "
                f"pass --question-bank or place at {qb_path}"
            ),
            retry_safe=False,
            suggested_remediation=(
                "Author a question_bank.yaml with 10-25 textbook-style "
                "questions and expected answers."
            ),
        )
        return 1
    bank = load_question_bank(qb_path)
    run = run_baseline(
        node_id=args.node_id,
        question_bank=bank,
        n_trials=args.n_trials,
    )
    decision = decide_materialization(
        run,
        is_closed_form=args.closed_form,
        is_conceptual=args.conceptual,
    )
    payload = {"decision": asdict(decision), "baseline": run.to_jsonable()}
    json.dump(payload, sys.stdout, indent=2, ensure_ascii=False, default=str)
    sys.stdout.write("\n")
    return 0


def _cmd_curriculum_materialize(args: argparse.Namespace) -> int:
    from mvp.curriculum.graph import load_default
    from mvp.curriculum.materialize import materialize_node

    graph = load_default()
    if args.node_id not in graph.nodes:
        _print_envelope(
            error_code="unknown_node",
            error_category="input_validation",
            human_message=f"node {args.node_id!r} is not in the curriculum graph",
            retry_safe=False,
            suggested_remediation=(
                "Run 'mvp curriculum ingest' first, or check the node id with "
                "'mvp curriculum graph'."
            ),
        )
        return 1
    try:
        result = materialize_node(args.node_id, graph=graph, draft_root=args.draft_root)
    except (FileNotFoundError, ValueError) as exc:
        _print_envelope(
            error_code="materialization_failed",
            error_category="input_validation",
            human_message=str(exc),
            retry_safe=False,
            suggested_remediation=(
                "Run 'mvp curriculum filter <node_id>' first, then place "
                "concept.md, question_bank.yaml, and decision.json under the "
                "expected draft directory."
            ),
        )
        return 1
    json.dump(result, sys.stdout, indent=2, ensure_ascii=False)
    sys.stdout.write("\n")
    return 0


def _cmd_curriculum_graph(args: argparse.Namespace) -> int:
    import shutil
    import subprocess

    from mvp.curriculum.graph import load_default

    graph = load_default()
    dot_text = graph.render_dot()

    if args.svg:
        if shutil.which("dot") is None:
            _print_envelope(
                error_code="missing_binary",
                error_category="io",
                human_message="--svg requires the 'dot' binary (Graphviz) on PATH",
                retry_safe=False,
                suggested_remediation=(
                    "Install Graphviz, or omit --svg to print the DOT source instead."
                ),
            )
            return 1
        try:
            proc = subprocess.run(
                ["dot", "-Tsvg"],
                input=dot_text,
                text=True,
                capture_output=True,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            _print_envelope(
                error_code="dot_failed",
                error_category="io",
                human_message=f"dot exited {exc.returncode}: {exc.stderr.strip()}",
                retry_safe=True,
                suggested_remediation="Inspect the DOT output without --svg for hints.",
            )
            return 1
        out = proc.stdout
    else:
        out = dot_text

    if args.output is None:
        sys.stdout.write(out)
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(out, encoding="utf-8")
        sys.stdout.write(f"# wrote {len(out)} bytes to {args.output}\n")
    return 0


def _resolve_default_question_bank(node_id: str) -> Path | None:
    """Map a curriculum node id to the canonical foundational-skill draft path."""
    mvp_root = Path(__file__).resolve().parent.parent
    if not node_id.startswith("foundational/"):
        return None
    rel = node_id[len("foundational/") :]
    return mvp_root / "skills" / "foundational" / rel / "eval" / "question_bank.yaml"


# ---------------------------------------------------------------------------
# Parser wiring.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mvp",
        description=(
            "MVP CLI — thin wrapper over the skill registry. "
            "Phases 4 + 5 + 6 expose ingest, run, eval, audit, skills, "
            "and resolve-citation subcommands."
        ),
    )
    sub = parser.add_subparsers(dest="command")

    # ---- ingest ---------------------------------------------------------
    p_ingest = sub.add_parser("ingest", help="Ingest sample filings or papers.")
    ingest_sub = p_ingest.add_subparsers(dest="ingest_subcommand")

    p_ingest_filings = ingest_sub.add_parser(
        "filings", help="Ingest one or more sample 10-K filings."
    )
    p_ingest_filings.add_argument("--cik", help="10-digit zero-padded SEC CIK.")
    p_ingest_filings.add_argument(
        "--years", help="Comma-separated calendar years, e.g. 1999,2000."
    )
    p_ingest_filings.add_argument(
        "--batch", choices=["all"], help="Ingest all 10 sample filings."
    )
    p_ingest_filings.set_defaults(func=_cmd_ingest_filings)

    p_ingest_paper = ingest_sub.add_parser(
        "paper", help="Ingest a sample academic paper."
    )
    p_ingest_paper.add_argument(
        "--id", help="Paper id: beneish_1999 or altman_1968."
    )
    p_ingest_paper.add_argument(
        "--batch", choices=["all"], help="Ingest both sample papers."
    )
    p_ingest_paper.set_defaults(func=_cmd_ingest_paper)

    # ---- run ------------------------------------------------------------
    p_run = sub.add_parser("run", help="Invoke a skill and print its JSON output.")
    p_run.add_argument("skill_id", help="Skill id, e.g. analyze_for_red_flags")
    p_run.add_argument("--cik", help="10-digit zero-padded SEC CIK.")
    p_run.add_argument(
        "--year", help="Fiscal year (yyyy) or fiscal year end (yyyy-mm-dd)."
    )
    p_run.add_argument("--accession", help="Accession number (skill-dependent).")
    p_run.add_argument(
        "--json",
        dest="json",
        help=(
            "Path to a JSON file containing the full input payload. "
            "Accepts 'path.json' or '@path.json'."
        ),
    )
    p_run.add_argument(
        "--format",
        choices=["json", "jsonl"],
        default="json",
        help="Output format: 'json' (pretty-printed, default) or 'jsonl' (compact).",
    )
    p_run.add_argument(
        "kv",
        nargs="*",
        help=(
            "Additional key=value input pairs. Values are coerced "
            "(true/false/null/int/float/JSON-literal/string)."
        ),
    )
    p_run.set_defaults(func=_cmd_run)

    # ---- eval -----------------------------------------------------------
    p_eval = sub.add_parser(
        "eval",
        help="Run the eval harness + citation check against every gold case.",
    )
    p_eval.add_argument(
        "--gold-root",
        type=Path,
        default=None,
        help="Override the gold root (defaults to mvp/eval/gold).",
    )
    p_eval.add_argument(
        "--no-report-file",
        action="store_true",
        help="Skip writing the JSON report to eval/reports/.",
    )
    p_eval.set_defaults(func=_cmd_eval)

    # ---- audit ----------------------------------------------------------
    p_audit = sub.add_parser("audit", help="Cross-cutting audits.")
    audit_sub = p_audit.add_subparsers(dest="audit_subcommand")

    p_audit_cites = audit_sub.add_parser(
        "citations",
        help="Verify every citation from every gold case resolves (100% required).",
    )
    p_audit_cites.add_argument("--gold-root", type=Path, default=None)
    p_audit_cites.set_defaults(func=_cmd_audit_citations)

    p_audit_log = audit_sub.add_parser(
        "log", help="Summarise persona-runtime audit-log entries."
    )
    p_audit_log.add_argument(
        "--persona", default=None, help="Filter by persona_id."
    )
    p_audit_log.add_argument(
        "--since", default=None, help="ISO date/datetime filter (entries ≥)."
    )
    p_audit_log.set_defaults(func=_cmd_audit_log)

    # ---- skills ---------------------------------------------------------
    p_skills = sub.add_parser("skills", help="Inspect the registered skill catalogue.")
    skills_sub = p_skills.add_subparsers(dest="skills_subcommand")

    p_skills_list = skills_sub.add_parser("list", help="List skills (one line each).")
    p_skills_list.set_defaults(func=_cmd_skills_list)

    p_skills_show = skills_sub.add_parser("show", help="Print a full manifest.")
    p_skills_show.add_argument("skill_id")
    p_skills_show.set_defaults(func=_cmd_skills_show)

    p_skills_mcp = skills_sub.add_parser("mcp", help="Print the MCP tool catalog as JSON.")
    p_skills_mcp.set_defaults(func=_cmd_skills_mcp)

    p_skills_openai = skills_sub.add_parser(
        "openai", help="Print the OpenAI tool-use catalog as JSON."
    )
    p_skills_openai.set_defaults(func=_cmd_skills_openai)

    p_skills_cost = skills_sub.add_parser(
        "cost",
        help=(
            "Aggregate deep-pipeline cost-log entries for one skill across "
            "every recorded run (post-MVP Workstream A)."
        ),
    )
    p_skills_cost.add_argument(
        "skill_id",
        help="Either the skill_id or the paper_id used by the deep pipeline.",
    )
    p_skills_cost.add_argument(
        "--cost-log-root",
        default=None,
        help="Override the cost-log root (defaults to mvp/agents/cost_log).",
    )
    p_skills_cost.set_defaults(func=_cmd_skills_cost)

    # ---- resolve-citation -----------------------------------------------
    p_rc = sub.add_parser(
        "resolve-citation",
        help="Resolve a (doc_id, locator) via the engine's citation validator.",
    )
    p_rc.add_argument("doc_id")
    p_rc.add_argument("locator")
    p_rc.add_argument("--excerpt-hash", default=None)
    p_rc.set_defaults(func=_cmd_resolve_citation)

    # ---- curriculum -----------------------------------------------------
    p_curr = sub.add_parser(
        "curriculum",
        help="Manage the foundational-layer curriculum DAG, filter, and materialization.",
    )
    curr_sub = p_curr.add_subparsers(dest="curriculum_subcommand")

    p_curr_ingest = curr_sub.add_parser(
        "ingest",
        help="Ingest a TOC YAML and add subsection nodes to the curriculum graph.",
    )
    p_curr_ingest.add_argument(
        "book_id",
        help="Book identifier (must match the TOC YAML's book_id field).",
    )
    p_curr_ingest.add_argument(
        "toc_path",
        type=Path,
        help="Path to the TOC YAML.",
    )
    p_curr_ingest.set_defaults(func=_cmd_curriculum_ingest)

    p_curr_filter = curr_sub.add_parser(
        "filter",
        help="Run the bare-LLM filter on a candidate node and print decision + reasoning.",
    )
    p_curr_filter.add_argument("node_id", help="Curriculum node id.")
    p_curr_filter.add_argument(
        "--question-bank",
        type=Path,
        default=None,
        help=(
            "Path to question_bank.yaml (defaults to the candidate skill's "
            "draft path under mvp/skills/foundational/...)."
        ),
    )
    p_curr_filter.add_argument(
        "--n-trials", type=int, default=10, help="Trials per question (default 10)."
    )
    p_curr_filter.add_argument(
        "--closed-form",
        action="store_true",
        help="Force the closed-form-determinism override.",
    )
    p_curr_filter.add_argument(
        "--conceptual",
        action="store_true",
        help="Tag the subsection as conceptual (allows the markdown-only path).",
    )
    p_curr_filter.set_defaults(func=_cmd_curriculum_filter)

    p_curr_mat = curr_sub.add_parser(
        "materialize",
        help="Apply a recorded filter decision and create the foundational skill files.",
    )
    p_curr_mat.add_argument("node_id", help="Curriculum node id.")
    p_curr_mat.add_argument(
        "--draft-root",
        type=Path,
        default=None,
        help=(
            "Optional override for the draft directory containing "
            "concept.md / question_bank.yaml / decision.json."
        ),
    )
    p_curr_mat.set_defaults(func=_cmd_curriculum_materialize)

    p_curr_graph = curr_sub.add_parser(
        "graph",
        help="Render the curriculum DAG to Graphviz DOT (or SVG with --svg).",
    )
    p_curr_graph.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path. Defaults to stdout (DOT).",
    )
    p_curr_graph.add_argument(
        "--svg",
        action="store_true",
        help="Convert DOT to SVG via the system 'dot' binary.",
    )
    p_curr_graph.set_defaults(func=_cmd_curriculum_graph)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
