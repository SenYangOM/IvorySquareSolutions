"""workshop.paper_to_skill.draft_manifest — scaffold a manifest.yaml.

First-draft version written during the paper-onboarding of Paper 3
(Bernard et al. 2025). Papers 1 and 2 used the copy-the-nearest-
template-and-adapt flow without tooling help; by Paper 3 the
variation across templates had saturated enough that scaffolding
earned its keep.

What this script does
---------------------
1. Reads a methodologist-notes file at
   ``workshop/paper_to_skill/notes/<paper_id>.md`` (the (a)..(h)
   shape Papers 1-3 established).
2. Takes a chosen layer (``fundamental`` / ``interpretation`` /
   ``paper_derived`` / ``composite``) and a skill_id.
3. Emits a skeleton ``manifest.yaml`` with:

   - ``skill_id``, ``version: 0.1.0``, ``layer``, ``status: alpha``,
     ``maintainer_persona`` pre-filled;
   - ``description_for_llm`` as a TODO block;
   - ``provenance.source_papers[]`` entry constructed from the notes'
     citation block + the ingested PDF path + pdf_sha256 (looked up
     from ``data/papers/<paper_id>.meta.json`` if present);
   - ``provenance.study_scope`` / ``provenance.problem`` /
     ``provenance.methodology`` populated as TODO blocks pulled
     from the notes' (a)..(c) sections;
   - ``implementation_decisions[]`` populated as TODO stubs keyed
     off the notes' (f) section bullets;
   - ``inputs`` / ``outputs`` shapes matching the skill's layer
     (L3 composites emit score/flag/signals/weights/citations);
   - ``limitations[]`` populated from the notes' (g) section;
   - ``examples[]`` populated from the notes' (e) section.

4. Prints the scaffold to stdout as YAML (or writes to a file if
   ``--output`` is provided).

Calibration
-----------
The scaffold is deliberately PARTIAL — ~70% of what ends up shipping.
The engineer's hand-fill is ~30% (the actual math, the citation
contract, the confidence model, the dependencies). This matches the
variation-ratio Papers 1-3 saw across their manifests: the boilerplate
(schema skeleton, provenance, limitations, examples) compresses
cleanly; the skill-specific math + citation contract does not.

The scaffold's emitted structure is a strict subset of what a final
manifest will contain. Tests against Papers 1, 2, and 3's actual
shipped manifests confirm that (a) the scaffold's keys are a subset
of the final manifest's keys, (b) the scaffold's values are TODO
markers or extracted-from-notes strings that the engineer will
refine.

What this script does NOT do
----------------------------
- Guess the skill's math. The ``methodology.formulas_extracted_from_paper``
  and ``methodology.summary`` blocks are emitted as TODO prose.
- Guess the citation contract. Emitted as a TODO with a pointer to
  the established citation-locator format.
- Guess the confidence model. Emitted as a TODO with a pointer to
  the established confidence-calibration pattern.
- Validate the emitted manifest against ``SkillManifest.load_from_yaml``.
  The engineer runs that as a separate step after filling in the
  math.

Usage
-----
As a library::

    from workshop.paper_to_skill.draft_manifest import draft_manifest
    yaml_text = draft_manifest(
        notes_path=Path('workshop/paper_to_skill/notes/bernard_2025_information_acquisition.md'),
        skill_id='compute_business_complexity_signals',
        layer='paper_derived',
        paper_id='bernard_2025_information_acquisition',
    )
    print(yaml_text)

As a CLI::

    python -m workshop.paper_to_skill.draft_manifest \\
        --notes workshop/paper_to_skill/notes/bernard_2025_information_acquisition.md \\
        --skill-id compute_business_complexity_signals \\
        --layer paper_derived \\
        --paper-id bernard_2025_information_acquisition

The separation contract (SPEC_UPDATES §13.3) forbids ``mvp/`` from
importing anything under ``workshop/``. This script in turn MAY
import from ``mvp.lib.*`` for shared utilities (we use nothing from
``mvp`` currently — this keeps the workshop script minimum-coupled).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path


# The default persona for a new skill — chosen to match the
# methodologist persona established in Papers 1-3.
_DEFAULT_PERSONA: str = "quant_finance_methodologist"

# Layer → default status (always ``alpha`` at paper-onboarding time,
# but the table is here so a future status-selection pass has a home).
_DEFAULT_STATUS: str = "alpha"

# Layers that need a rule template (L2 interpretation or L3
# paper-derived with per-component rules). L1 fundamental + L4
# composite do not.
_NEEDS_RULE_TEMPLATE: frozenset[str] = frozenset(
    {"interpretation", "paper_derived"}
)

# Valid layer names — must match SkillManifest's Literal-typed layer
# field so the emitted manifest will validate.
_VALID_LAYERS: tuple[str, ...] = (
    "fundamental",
    "interpretation",
    "paper_derived",
    "composite",
)


@dataclass(frozen=True)
class NotesExtraction:
    """Structured pieces pulled from a methodologist-notes markdown file.

    Each field is the raw text of one section (or an empty string if
    the section wasn't found). Downstream code uses the text as
    TODO-level body for the scaffold; the engineer refines.
    """

    citation_block: str
    section_a_skill_scope: str
    section_b_catalogue_gap: str
    section_c_formulas: str
    section_d_thresholds: str
    section_e_worked_examples: str
    section_f_implementation: str
    section_g_limitations: str


# Section headers in the Paper-1/2/3 notes format. Matches both the
# "## (a) Skill-scope decision" and "## Skill-scope decision" shapes
# to be slightly forgiving.
_SECTION_HEADER_RE = re.compile(
    r"^##\s+(?:\(([a-h])\)\s+)?([A-Z][^\n]+)$",
    re.MULTILINE,
)


def parse_notes(notes_path: Path) -> NotesExtraction:
    """Parse a methodologist-notes file into a :class:`NotesExtraction`.

    Parameters
    ----------
    notes_path:
        Absolute path to a ``workshop/paper_to_skill/notes/<paper_id>.md``
        file.

    Returns
    -------
    NotesExtraction

    Raises
    ------
    FileNotFoundError
        If ``notes_path`` does not exist.
    """
    if not notes_path.is_file():
        raise FileNotFoundError(f"notes file not found at {notes_path}")
    text = notes_path.read_text(encoding="utf-8")

    # Extract the citation block — the "> Kim et al. ..." blockquote at
    # the top of every notes file. Matches all consecutive "> " lines.
    cite_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith(">"):
            # Strip the leading "> " prefix so the block is usable in YAML.
            cite_lines.append(line[1:].strip())
        elif cite_lines:
            # First non-blockquote line ends the citation block.
            break
    citation_block = " ".join(cite_lines).strip()

    # Walk section headers in order and slice the body of each.
    headers: list[tuple[str, str, int]] = []
    for m in _SECTION_HEADER_RE.finditer(text):
        letter = m.group(1) or ""  # "a".."h" when present
        title = m.group(2).strip()
        headers.append((letter, title, m.start()))

    sections: dict[str, str] = {}
    for i, (letter, _title, start) in enumerate(headers):
        if not letter:
            continue
        end = headers[i + 1][2] if i + 1 < len(headers) else len(text)
        # Skip the header line itself — body starts after the next \n.
        body_start = text.find("\n", start) + 1
        if body_start <= 0:
            continue
        sections[letter] = text[body_start:end].strip()

    return NotesExtraction(
        citation_block=citation_block,
        section_a_skill_scope=sections.get("a", ""),
        section_b_catalogue_gap=sections.get("b", ""),
        section_c_formulas=sections.get("c", ""),
        section_d_thresholds=sections.get("d", ""),
        section_e_worked_examples=sections.get("e", ""),
        section_f_implementation=sections.get("f", ""),
        section_g_limitations=sections.get("g", ""),
    )


def load_paper_meta(paper_id: str, mvp_root: Path) -> dict[str, object]:
    """Load ``data/papers/<paper_id>.meta.json`` if present.

    Returns an empty dict when the meta file isn't found, so the
    scaffold emits a TODO pdf_sha256 rather than raising. Non-fatal
    so a methodologist can draft the manifest BEFORE running
    ingest_local_paper.
    """
    meta_path = mvp_root / "data" / "papers" / f"{paper_id}.meta.json"
    if not meta_path.is_file():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def draft_manifest(
    *,
    notes_path: Path,
    skill_id: str,
    layer: str,
    paper_id: str,
    mvp_root: Path | None = None,
) -> str:
    """Produce a skeleton manifest YAML string.

    Parameters
    ----------
    notes_path:
        Path to the methodologist-notes markdown file.
    skill_id:
        The new skill's snake_case id. Validated against the layer
        convention (paper_derived/fundamental skills typically start
        with ``compute_`` / ``extract_``; interpretation with
        ``interpret_``; composite with a verb).
    layer:
        One of ``fundamental`` / ``interpretation`` / ``paper_derived``
        / ``composite``.
    paper_id:
        Stable snake_case id matching the ingested PDF
        (``data/papers/<paper_id>.pdf``).
    mvp_root:
        Absolute path to the mvp/ repo root (for looking up the
        paper meta file). Defaults to two levels up from this script.

    Returns
    -------
    str
        A YAML-formatted manifest scaffold. The caller is expected
        to refine the TODO blocks before running
        ``SkillManifest.load_from_yaml``.

    Raises
    ------
    ValueError
        If ``layer`` is not one of the four valid layer names.
    FileNotFoundError
        If ``notes_path`` does not exist.
    """
    if layer not in _VALID_LAYERS:
        raise ValueError(
            f"layer must be one of {_VALID_LAYERS}, got {layer!r}"
        )

    if mvp_root is None:
        # Default: two-up from this file (workshop/paper_to_skill/ →
        # workshop → repo root → mvp/).
        mvp_root = Path(__file__).resolve().parent.parent.parent / "mvp"

    extraction = parse_notes(notes_path)
    meta = load_paper_meta(paper_id, mvp_root)

    pdf_sha256 = str(meta.get("sha256") or "TODO_pdf_sha256")
    citation = str(meta.get("citation") or extraction.citation_block or "TODO_citation")
    doi_or_url = _guess_doi_or_url(meta, extraction.citation_block)

    lines: list[str] = []
    _emit_header(lines, skill_id=skill_id, paper_id=paper_id, layer=layer)

    # Top-level identity block.
    lines.append(f"skill_id: {skill_id}")
    lines.append("version: 0.1.0")
    lines.append(f"layer: {layer}")
    lines.append(f"status: {_DEFAULT_STATUS}")
    lines.append(f"maintainer_persona: {_DEFAULT_PERSONA}")
    lines.append("description_for_llm: >-")
    lines.append(
        f"  TODO: 2–4 sentences for an LLM caller. What does {skill_id} "
        "do? Typical inputs; typical outputs; when NOT to call it. A "
        "cold agent should pick the right skill from this description "
        "alone."
    )
    lines.append("")

    # Provenance.
    lines.append("provenance:")
    lines.append("  source_papers:")
    lines.append(f'    - citation: "{_yaml_escape(citation)}"')
    lines.append(f'      doi_or_url: "{doi_or_url}"')
    lines.append(f'      local_pdf: "data/papers/{paper_id}.pdf"')
    lines.append(f'      pdf_sha256: "{pdf_sha256}"')
    lines.append("  study_scope:")
    lines.append('    asset_class: "TODO — see notes §(a)"')
    lines.append('    time_period_in_paper: "TODO — see notes §(a)"')
    lines.append('    sample_size_in_paper: "TODO — see notes §(a)"')
    lines.append("  problem:")
    lines.append('    one_line: "TODO — one-sentence problem statement"')
    lines.append("    long_form: >-")
    lines.append("      TODO — see notes §(a) and §(b) for the problem and why-this-skill blocks.")
    lines.append("  methodology:")
    lines.append("    summary: >-")
    lines.append("      TODO — 4-8 sentences covering the computation. See notes §(c).")
    lines.append("    formulas_extracted_from_paper:")
    lines.append("      TODO_key_1: \"TODO — paper formula in original notation\"")
    lines.append("      TODO_key_2: \"TODO — canonical adaptation / proxy\"")
    lines.append('    threshold: "TODO — band cutoffs for the output flag"')
    lines.append("  expected_results:")
    lines.append('    metric_kind: "TODO — what the score is and its range"')
    lines.append("    interpretation_guide: >-")
    lines.append("      TODO — how should a caller read the score? See notes §(e).")
    lines.append("  takeaways:")
    lines.append('    - "TODO — bullet 1 (use notes §(f) as a source)"')
    lines.append('    - "TODO — bullet 2"')
    lines.append("  use_cases:")
    lines.append('    - "TODO — use case 1"')
    lines.append('    - "TODO — use case 2"')
    lines.append("")

    # Implementation decisions.
    lines.append("implementation_decisions:")
    f_bullets = _extract_f_bullets(extraction.section_f_implementation)
    if f_bullets:
        for i, bullet in enumerate(f_bullets, start=1):
            lines.append("  - decision: >-")
            lines.append(f"      TODO_decision_{i}: {_yaml_oneline(bullet)}")
            lines.append("    rationale: >-")
            lines.append("      TODO — why this decision. See notes §(f).")
            lines.append(f"    reviewer_persona: {_DEFAULT_PERSONA}")
    else:
        lines.append("  - decision: >-")
        lines.append("      TODO — one entry per design call. See notes §(f).")
        lines.append("    rationale: >-")
        lines.append("      TODO.")
        lines.append(f"    reviewer_persona: {_DEFAULT_PERSONA}")
    lines.append("")

    # Inputs and outputs — shape varies by layer.
    _emit_inputs_block(lines, layer=layer)
    lines.append("")
    _emit_outputs_block(lines, layer=layer)
    lines.append("")

    # Citation contract.
    lines.append("citation_contract:")
    lines.append("  required_per_field:")
    lines.append('    TODO_field_name: "TODO — which canonical line items must be cited"')
    lines.append('  hash_algorithm: sha256')
    lines.append('  locator_format: "<cik>/<accession>::<role>::<line_item>"')
    lines.append("")

    # Confidence model.
    lines.append("confidence:")
    lines.append("  computed_from:")
    lines.append('    - "TODO — which factors raise/lower confidence"')
    lines.append("  calibration_status: uncalibrated_at_mvp")
    lines.append("")

    # Dependencies.
    lines.append("dependencies:")
    lines.append("  skills: []")
    lines.append("  lib:")
    lines.append("    - mvp.lib.citation")
    lines.append("    - mvp.standardize.statements")
    lines.append("    - mvp.ingestion.filings_ingest")
    if layer in _NEEDS_RULE_TEMPLATE:
        lines.append("  rules:")
        lines.append(f"    - rules/templates/{skill_id}_components.yaml")
    else:
        lines.append("  rules: []")
    lines.append("")

    # Evaluation.
    lines.append("evaluation:")
    lines.append(f'  gold_standard_path: eval/gold/{_derive_gold_subdir(skill_id)}/')
    lines.append("  eval_metrics:")
    lines.append('    - name: TODO_metric_name')
    lines.append('      target: "TODO — e.g. >= 4/5"')
    lines.append("")

    # Limitations.
    lines.append("limitations:")
    g_bullets = _extract_bullet_list(extraction.section_g_limitations)
    if g_bullets:
        for bullet in g_bullets:
            lines.append("  - >-")
            for wrapped in _wrap_lines(bullet, indent="    "):
                lines.append(wrapped)
    else:
        lines.append("  - >-")
        lines.append("    TODO — one bullet per known limitation. See notes §(g).")
    lines.append("")

    # Examples.
    lines.append("examples:")
    e_blocks = _extract_e_blocks(extraction.section_e_worked_examples)
    if e_blocks:
        for title, body in e_blocks:
            lines.append(f'  - name: "{_yaml_escape(title)}"')
            lines.append("    input:")
            lines.append('      TODO_cik: "TODO"')
            lines.append('      TODO_fiscal_year_end: "TODO"')
            lines.append("    notes: >-")
            for wrapped in _wrap_lines(body, indent="      "):
                lines.append(wrapped)
    else:
        lines.append('  - name: "TODO — worked example name"')
        lines.append("    input:")
        lines.append('      cik: "TODO"')
        lines.append('      fiscal_year_end: "TODO"')
        lines.append("    notes: >-")
        lines.append("      TODO.")
    lines.append("")

    # Cost estimate.
    lines.append("cost_estimate:")
    lines.append("  llm_tokens_per_call: 0")
    lines.append("  external_api_calls: 0")
    lines.append("  typical_latency_ms: 250")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private helpers.
# ---------------------------------------------------------------------------


def _emit_header(
    lines: list[str], *, skill_id: str, paper_id: str, layer: str
) -> None:
    lines.append(f"# Manifest SCAFFOLD for {skill_id}")
    lines.append(f"# Generated by workshop.paper_to_skill.draft_manifest from:")
    lines.append(f"#   notes_path = workshop/paper_to_skill/notes/{paper_id}.md")
    lines.append(f"#   layer      = {layer}")
    lines.append("#")
    lines.append("# TODO blocks below require the engineer's hand-fill before the")
    lines.append("# manifest validates against SkillManifest.load_from_yaml. The")
    lines.append("# scaffold is ~70% of the final shipped manifest by line count.")
    lines.append("")


def _emit_inputs_block(lines: list[str], *, layer: str) -> None:
    """Emit the standard inputs block.

    All four layers use the same ``cik`` + ``fiscal_year_end`` shape
    at MVP; layer-specific extensions (e.g. composite skills that take
    additional parameters) are documented by the engineer in the
    hand-fill phase.
    """
    lines.append("inputs:")
    lines.append("  type: object")
    lines.append("  required: [cik, fiscal_year_end]")
    lines.append("  additionalProperties: false")
    lines.append("  properties:")
    lines.append("    cik:")
    lines.append("      type: string")
    lines.append('      pattern: "^[0-9]{10}$"')
    lines.append("      description: >-")
    lines.append(
        "        10-digit zero-padded SEC CIK for the issuer "
        "(e.g. '0000320193' for Apple Inc.)."
    )
    lines.append("    fiscal_year_end:")
    lines.append("      type: string")
    lines.append("      description: >-")
    lines.append(
        "        Fiscal year end of the 10-K filing, ISO yyyy-mm-dd. "
        "Must match an ingested filing under data/filings/."
    )


def _emit_outputs_block(lines: list[str], *, layer: str) -> None:
    """Emit a layer-specific outputs block.

    paper_derived / interpretation skills emit score + flag +
    components + citations + confidence + warnings. fundamental skills
    emit the payload-only envelope (e.g. extract_canonical_statements
    returns statements[]). composite skills emit a two-block
    aggregate.

    The scaffolded shape is the MVP-standard 'score + flag + signals +
    components + weights + citations + confidence + warnings' for
    paper_derived/composite, which is what Papers 1-3 all shipped.
    """
    lines.append("outputs:")
    lines.append("  type: object")
    if layer in {"paper_derived", "composite", "interpretation"}:
        lines.append(
            "  required: [score, flag, signals, components, weights, "
            "citations, confidence, warnings]"
        )
        lines.append("  additionalProperties: true")
        lines.append("  properties:")
        lines.append("    score:")
        lines.append('      type: ["number", "null"]')
        lines.append(
            '      description: "TODO — scalar score in [0, 1]. Null when flag=indeterminate."'
        )
        lines.append("    flag:")
        lines.append("      type: string")
        lines.append("      enum: [TODO_high, TODO_mid, TODO_low, indeterminate]")
        lines.append(
            '      description: "TODO — 4-band categorical flag."'
        )
        lines.append("    signals:")
        lines.append("      type: object")
        lines.append(
            '      description: "TODO — per-signal raw values."'
        )
        lines.append("      additionalProperties: true")
        lines.append("    components:")
        lines.append("      type: object")
        lines.append(
            '      description: "TODO — per-signal fired indicators (I[·] terms)."'
        )
        lines.append("      additionalProperties: true")
        lines.append("    weights:")
        lines.append("      type: object")
        lines.append(
            '      description: "TODO — fixed paper-derived weights, exposed for auditability."'
        )
        lines.append("      additionalProperties: true")
        lines.append("    citations:")
        lines.append("      type: array")
        lines.append(
            '      description: "TODO — citations back to canonical line items consumed by the score."'
        )
        lines.append("      items:")
        lines.append("        type: object")
        lines.append(
            '        description: "One Citation record (mvp.lib.citation.Citation shape)."'
        )
        lines.append("    confidence:")
        lines.append("      type: number")
        lines.append(
            '      description: "TODO — confidence score in [0, 1]."'
        )
        lines.append("    warnings:")
        lines.append("      type: array")
        lines.append("      description: >-")
        lines.append("        TODO — zero or more warning strings.")
        lines.append("      items:")
        lines.append("        type: string")
        lines.append(
            '        description: "One warning string."'
        )
    else:  # fundamental
        lines.append("  required: [TODO_fundamental_payload_field]")
        lines.append("  additionalProperties: true")
        lines.append("  properties:")
        lines.append("    TODO_fundamental_payload_field:")
        lines.append("      type: array")
        lines.append(
            '      description: "TODO — whatever the extractor returns."'
        )


def _guess_doi_or_url(
    meta: dict[str, object], citation_block: str
) -> str:
    """Best-effort DOI/URL extraction.

    Prefer the meta.json source_url if populated; else look for a
    ``DOI: ...`` substring in the citation block.
    """
    src_url = meta.get("source_url")
    if isinstance(src_url, str) and src_url.startswith(("http://", "https://")):
        return src_url
    # Match the DOI tail greedy-through-slashes (e.g. 10.1007/s11142-...),
    # stopping at whitespace or end-of-line. Multiple slashes occur in
    # Springer-style DOIs so a permissive charset is needed.
    doi_match = re.search(
        r"DOI:\s*([0-9A-Za-z./_\-]+)(?:\s|$)", citation_block
    )
    if doi_match:
        return f"https://doi.org/{doi_match.group(1).rstrip('.')}"
    return "TODO_doi_or_url"


def _derive_gold_subdir(skill_id: str) -> str:
    """Map a skill_id to its gold subdirectory name.

    Follows the established Paper-1/2/3 convention: drop the leading
    verb-prefix (compute_ / extract_ / interpret_) to get the short
    form used in eval/gold/<short>/.
    """
    for prefix in ("compute_", "extract_", "interpret_", "analyze_"):
        if skill_id.startswith(prefix):
            return skill_id[len(prefix):]
    return skill_id


def _extract_f_bullets(section_f_text: str) -> list[str]:
    """Extract numbered or bulleted items from the notes' §(f).

    Handles both ``1. **Decision name.** ...`` and ``- Decision ...``
    styles. Returns each item's leading line (up to the first
    newline) as a compact TODO hint.
    """
    bullets: list[str] = []
    # Numbered list items (1. ..., 2. ...).
    for m in re.finditer(
        r"^\d+\.\s+(.+?)$", section_f_text, re.MULTILINE
    ):
        bullets.append(m.group(1).strip())
    if bullets:
        return bullets
    # Fallback: dash-bulleted.
    for m in re.finditer(r"^-\s+(.+?)$", section_f_text, re.MULTILINE):
        bullets.append(m.group(1).strip())
    return bullets


def _extract_bullet_list(text: str) -> list[str]:
    """Extract top-level ``- ...`` bullet items as one-line strings."""
    bullets: list[str] = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("- ") and line[: len(line) - len(stripped)] == "":
            bullets.append(stripped[2:].strip())
    return bullets


def _extract_e_blocks(
    section_e_text: str,
) -> list[tuple[str, str]]:
    """Extract ``N. **Title** — body...`` entries from §(e).

    Returns a list of (title, body) pairs. Each body is the first
    sentence / first paragraph.
    """
    out: list[tuple[str, str]] = []
    for m in re.finditer(
        r"^\s*\d+\.\s+\*\*([^*]+)\*\*[^\n]*\n([^\n]+)",
        section_e_text,
        re.MULTILINE,
    ):
        title = m.group(1).strip().rstrip(".")
        body = m.group(2).strip()
        out.append((title, body))
    return out


def _wrap_lines(text: str, *, indent: str, width: int = 78) -> list[str]:
    """Wrap a long text body into indented YAML-folded-scalar lines.

    Not a full word-wrapper — splits on sentence boundaries and
    truncates at ``width`` chars per line. Sufficient for scaffolded
    YAML; the engineer will re-wrap during hand-fill.
    """
    if not text:
        return [f"{indent}TODO."]
    out: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in text.split():
        if current_len + len(word) + 1 > width - len(indent):
            out.append(f"{indent}{' '.join(current)}")
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word) + 1
    if current:
        out.append(f"{indent}{' '.join(current)}")
    return out


def _yaml_escape(s: str) -> str:
    """Escape a string for use inside a YAML double-quoted scalar."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _yaml_oneline(s: str) -> str:
    """Collapse a multi-line string to a single line for TODO hints."""
    return " ".join(s.split())


# ---------------------------------------------------------------------------
# CLI.
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workshop.paper_to_skill.draft_manifest",
        description=(
            "Scaffold a skill manifest.yaml from a methodologist-"
            "notes file. Output is YAML on stdout (or to --output)."
        ),
    )
    p.add_argument(
        "--notes",
        type=Path,
        required=True,
        help="Absolute path to the methodologist-notes markdown file.",
    )
    p.add_argument(
        "--skill-id",
        required=True,
        help="Snake_case skill id (e.g. compute_foo_score).",
    )
    p.add_argument(
        "--layer",
        required=True,
        choices=_VALID_LAYERS,
        help="Skill layer.",
    )
    p.add_argument(
        "--paper-id",
        required=True,
        help=(
            "Stable snake_case paper id matching "
            "data/papers/<paper_id>.{pdf,meta.json}."
        ),
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional output file path. Defaults to stdout.",
    )
    p.add_argument(
        "--mvp-root",
        type=Path,
        default=None,
        help=(
            "Absolute path to the mvp/ repo root. Defaults to "
            "two-up-from-this-script."
        ),
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        yaml_text = draft_manifest(
            notes_path=args.notes,
            skill_id=args.skill_id,
            layer=args.layer,
            paper_id=args.paper_id,
            mvp_root=args.mvp_root,
        )
    except (FileNotFoundError, ValueError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 1

    if args.output is None:
        sys.stdout.write(yaml_text)
        if not yaml_text.endswith("\n"):
            sys.stdout.write("\n")
    else:
        args.output.write_text(yaml_text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "NotesExtraction",
    "draft_manifest",
    "load_paper_meta",
    "main",
    "parse_notes",
]
