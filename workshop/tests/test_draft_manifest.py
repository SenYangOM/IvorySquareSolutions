"""Light tests for workshop.paper_to_skill.draft_manifest.

Workshop is exempt from the full-test bar (``success_criteria.md``
§13.4) but a few hermetic checks on draft_manifest pay for
themselves: they pin the scaffold shape so a future paper-4+ author
notices immediately if the emitted structure drifts, and they
exercise the §(e)/§(f)/§(g) notes-parsing heuristics that the
scaffold depends on.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from workshop.paper_to_skill.draft_manifest import (
    NotesExtraction,
    _derive_gold_subdir,
    _extract_bullet_list,
    _extract_e_blocks,
    _extract_f_bullets,
    _guess_doi_or_url,
    draft_manifest,
    load_paper_meta,
    parse_notes,
)


_PAPER_EXAMPLES_NOTES = (
    Path(__file__).resolve().parent.parent
    / "paper_to_skill"
    / "notes"
)


# ---------------------------------------------------------------------------
# parse_notes — validates section-slicing on the three shipped notes files.
# ---------------------------------------------------------------------------


def test_parse_notes_extracts_citation_and_section_headers_for_paper_1() -> None:
    """Paper 1's notes file (fundamentals_text) should parse cleanly."""
    notes = _PAPER_EXAMPLES_NOTES / "fundamentals_text.md"
    if not notes.is_file():
        pytest.skip("paper 1 notes file not present")
    extraction = parse_notes(notes)
    assert extraction.citation_block  # non-empty
    assert "Learning Fundamentals" in extraction.citation_block
    assert extraction.section_a_skill_scope  # non-empty
    assert "L3 paper-derived" in extraction.section_a_skill_scope


def test_parse_notes_extracts_all_a_to_g_sections_for_paper_3() -> None:
    """Paper 3's notes file (Bernard et al. 2025) has all a..h sections."""
    notes = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    extraction = parse_notes(notes)
    assert extraction.citation_block
    assert "Bernard" in extraction.citation_block
    assert extraction.section_a_skill_scope
    assert extraction.section_b_catalogue_gap
    assert extraction.section_c_formulas
    assert extraction.section_d_thresholds
    assert extraction.section_e_worked_examples
    assert extraction.section_f_implementation
    assert extraction.section_g_limitations


def test_parse_notes_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_notes(tmp_path / "nonexistent.md")


# ---------------------------------------------------------------------------
# Section-extractor heuristics.
# ---------------------------------------------------------------------------


def test_extract_f_bullets_parses_numbered_decisions() -> None:
    """The §(f) extractor handles the numbered-decisions style."""
    text = """
1. **First decision.** Some rationale follows.

2. **Second decision.** More rationale.

3. **Third decision.** Yet more rationale.
"""
    bullets = _extract_f_bullets(text)
    assert len(bullets) == 3
    assert bullets[0].startswith("**First decision")
    assert bullets[1].startswith("**Second decision")


def test_extract_f_bullets_falls_back_to_dash_bullets() -> None:
    """When no numbered items, fall back to dash-bulleted list."""
    text = """
- First point
- Second point
- Third point
"""
    bullets = _extract_f_bullets(text)
    assert len(bullets) == 3
    assert bullets[0] == "First point"


def test_extract_bullet_list_ignores_nested_bullets() -> None:
    """Top-level dash bullets only; nested sub-bullets are skipped."""
    text = """
- Top level 1
  - Nested (should be ignored)
- Top level 2
"""
    bullets = _extract_bullet_list(text)
    assert bullets == ["Top level 1", "Top level 2"]


def test_extract_e_blocks_parses_worked_examples() -> None:
    """§(e) extractor pulls N. **Title** — body entries.

    The current implementation returns the FIRST post-title line as
    the body (not the header line itself), which matches how Papers
    1-3's §(e) sections are shaped (the header line names the case,
    the line below expands on it). A more sophisticated multi-line
    body extractor is deferred to Paper 4+.
    """
    text = """
1. **Apple FY2023** — a large, stable, low-overhead profile.
   This firm fires size and stability.

2. **WorldCom FY2001** — a classical overhead-heavy conglomerate.
   This firm fires all three signals.
"""
    blocks = _extract_e_blocks(text)
    assert len(blocks) == 2
    assert blocks[0][0] == "Apple FY2023"
    # Body is the content of the line following the title line.
    assert "size and stability" in blocks[0][1]
    assert blocks[1][0] == "WorldCom FY2001"
    assert "three signals" in blocks[1][1]


# ---------------------------------------------------------------------------
# DOI / URL extraction.
# ---------------------------------------------------------------------------


def test_guess_doi_or_url_prefers_meta_source_url() -> None:
    meta = {"source_url": "https://example.com/paper.pdf"}
    assert _guess_doi_or_url(meta, "") == "https://example.com/paper.pdf"


def test_guess_doi_or_url_falls_back_to_citation_doi() -> None:
    """DOI: 10.1007/... in the citation block is converted to a URL."""
    cite = (
        "Bernard, D. (2025). Some Paper. Some Journal, 30, 1-10. "
        "DOI: 10.1007/s11142-025-09885-5."
    )
    url = _guess_doi_or_url({}, cite)
    assert url == "https://doi.org/10.1007/s11142-025-09885-5"


def test_guess_doi_or_url_returns_todo_when_absent() -> None:
    cite = "Author (2024). Title. Journal, 1, 1-10. Some other text."
    url = _guess_doi_or_url({}, cite)
    assert url == "TODO_doi_or_url"


def test_guess_doi_or_url_handles_wiley_style_doi() -> None:
    """Wiley-style DOI 10.1111/1475-679X.12593 should parse."""
    cite = (
        "Kim, A. G. (2024). Context-Based Interpretation. "
        "Journal of Accounting Research. DOI: 10.1111/1475-679X.12593."
    )
    url = _guess_doi_or_url({}, cite)
    assert url == "https://doi.org/10.1111/1475-679X.12593"


# ---------------------------------------------------------------------------
# _derive_gold_subdir — short names follow the Paper-1/2/3 convention.
# ---------------------------------------------------------------------------


def test_derive_gold_subdir_strips_compute_prefix() -> None:
    assert _derive_gold_subdir("compute_business_complexity_signals") == (
        "business_complexity_signals"
    )


def test_derive_gold_subdir_strips_extract_prefix() -> None:
    assert _derive_gold_subdir("extract_mdna") == "mdna"


def test_derive_gold_subdir_strips_interpret_prefix() -> None:
    assert _derive_gold_subdir("interpret_m_score_components") == (
        "m_score_components"
    )


def test_derive_gold_subdir_passes_through_unprefixed() -> None:
    assert _derive_gold_subdir("some_other_skill") == "some_other_skill"


# ---------------------------------------------------------------------------
# End-to-end: draft_manifest emits a scaffold whose top-level keys match
# what a final paper_derived manifest has.
# ---------------------------------------------------------------------------


def test_draft_manifest_emits_expected_top_level_keys(tmp_path: Path) -> None:
    """Scaffold's top-level keys must be the superset every final manifest has."""
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    mvp_root = Path(__file__).resolve().parent.parent.parent / "mvp"
    yaml_text = draft_manifest(
        notes_path=notes_path,
        skill_id="compute_fake_test_skill",
        layer="paper_derived",
        paper_id="bernard_2025_information_acquisition",
        mvp_root=mvp_root,
    )
    expected_keys = {
        "skill_id",
        "version",
        "layer",
        "status",
        "maintainer_persona",
        "description_for_llm",
        "provenance",
        "implementation_decisions",
        "inputs",
        "outputs",
        "citation_contract",
        "confidence",
        "dependencies",
        "evaluation",
        "limitations",
        "examples",
        "cost_estimate",
    }
    for key in expected_keys:
        assert f"\n{key}:" in yaml_text or yaml_text.startswith(f"{key}:"), (
            f"scaffold missing top-level key {key!r}"
        )


def test_draft_manifest_raises_on_invalid_layer(tmp_path: Path) -> None:
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    with pytest.raises(ValueError, match="layer must be one of"):
        draft_manifest(
            notes_path=notes_path,
            skill_id="compute_foo",
            layer="not_a_layer",
            paper_id="bernard_2025_information_acquisition",
        )


def test_draft_manifest_includes_paper_sha256_when_meta_present() -> None:
    """If data/papers/<paper_id>.meta.json exists, pdf_sha256 is populated."""
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    mvp_root = Path(__file__).resolve().parent.parent.parent / "mvp"
    yaml_text = draft_manifest(
        notes_path=notes_path,
        skill_id="compute_business_complexity_signals",
        layer="paper_derived",
        paper_id="bernard_2025_information_acquisition",
        mvp_root=mvp_root,
    )
    # Paper-3 sha256 prefix.
    assert "1760a4c614f6051052beff0fad61587" in yaml_text


def test_draft_manifest_emits_todo_sha256_when_meta_absent(tmp_path: Path) -> None:
    """When meta.json is missing, pdf_sha256 is a TODO marker."""
    # Redirect mvp_root to a temp dir so the meta lookup misses.
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    yaml_text = draft_manifest(
        notes_path=notes_path,
        skill_id="compute_fake",
        layer="paper_derived",
        paper_id="no_such_paper",
        mvp_root=tmp_path,
    )
    assert "TODO_pdf_sha256" in yaml_text


def test_draft_manifest_includes_rule_template_path_for_l3() -> None:
    """paper_derived + interpretation skills get a rules-template entry."""
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    mvp_root = Path(__file__).resolve().parent.parent.parent / "mvp"
    yaml_text = draft_manifest(
        notes_path=notes_path,
        skill_id="compute_fake",
        layer="paper_derived",
        paper_id="bernard_2025_information_acquisition",
        mvp_root=mvp_root,
    )
    assert "rules/templates/compute_fake_components.yaml" in yaml_text


def test_draft_manifest_omits_rule_template_for_fundamental() -> None:
    """fundamental skills do NOT get a rules-template entry."""
    notes_path = _PAPER_EXAMPLES_NOTES / "bernard_2025_information_acquisition.md"
    mvp_root = Path(__file__).resolve().parent.parent.parent / "mvp"
    yaml_text = draft_manifest(
        notes_path=notes_path,
        skill_id="extract_fake",
        layer="fundamental",
        paper_id="bernard_2025_information_acquisition",
        mvp_root=mvp_root,
    )
    # L1 fundamental gets an empty rules list, no template path.
    assert "rules: []" in yaml_text
    assert "rules/templates/extract_fake_components.yaml" not in yaml_text


# ---------------------------------------------------------------------------
# load_paper_meta — handles missing / corrupt metas gracefully.
# ---------------------------------------------------------------------------


def test_load_paper_meta_returns_empty_dict_when_absent(tmp_path: Path) -> None:
    meta = load_paper_meta("no_such_paper", tmp_path)
    assert meta == {}


def test_load_paper_meta_loads_valid_json(tmp_path: Path) -> None:
    papers_dir = tmp_path / "data" / "papers"
    papers_dir.mkdir(parents=True)
    meta_path = papers_dir / "fake_paper.meta.json"
    meta_path.write_text('{"sha256": "deadbeef", "citation": "Test cite"}')
    meta = load_paper_meta("fake_paper", tmp_path)
    assert meta == {"sha256": "deadbeef", "citation": "Test cite"}


def test_load_paper_meta_returns_empty_dict_on_corrupt_json(tmp_path: Path) -> None:
    papers_dir = tmp_path / "data" / "papers"
    papers_dir.mkdir(parents=True)
    (papers_dir / "corrupt.meta.json").write_text("{not valid json")
    meta = load_paper_meta("corrupt", tmp_path)
    assert meta == {}
