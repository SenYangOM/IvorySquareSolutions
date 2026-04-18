"""Smoke tests for workshop.paper_to_skill.inspect_canonical.

Workshop is exempt from the full-test bar (`success_criteria.md` §13.4),
but a few light hermetic checks pin the helper's contract so a future
paper-onboarding subagent doesn't get a confusing AttributeError if
the FilingRef schema drifts.
"""

from __future__ import annotations

from workshop.paper_to_skill.inspect_canonical import (
    CANONICAL_LINE_ITEMS,
    _format_matrix_table,
    line_item_population_for_filing,
    line_item_population_matrix,
)


def test_canonical_line_items_count_matches_mappings() -> None:
    """The 16 canonical line items appear in the helper's exposed tuple."""
    from mvp.standardize.mappings import CONCEPT_MAPPINGS
    assert set(CANONICAL_LINE_ITEMS) == set(CONCEPT_MAPPINGS.keys())
    assert len(CANONICAL_LINE_ITEMS) == 16


def test_population_for_unknown_filing_returns_all_false() -> None:
    """A cik/fye that isn't in the sample catalogue returns all-false."""
    pop = line_item_population_for_filing("0000000000", "1999-01-01")
    assert all(v is False for v in pop.values())
    assert set(pop.keys()) == set(CANONICAL_LINE_ITEMS)


def test_population_matrix_keys_are_five_sample_filings() -> None:
    """The matrix has one entry per MVP sample issuer (5 issuers)."""
    matrix = line_item_population_matrix()
    assert len(matrix) == 5
    labels = [label for (_cik, _fye, label) in matrix.keys()]
    # Ordered by (cik, fye, label) tuple — verify the labels look right.
    expected_labels = {
        "Enron FY2000",
        "WorldCom FY2001",
        "Apple FY2023",
        "Microsoft FY2023",
        "Carvana FY2022",
    }
    assert set(labels) == expected_labels


def test_format_matrix_table_renders_a_markdown_table() -> None:
    """The table renders as Markdown with a header row + separator row."""
    matrix = {
        ("0001234567", "2024-12-31", "Test Co"): {
            name: True for name in CANONICAL_LINE_ITEMS
        }
    }
    table = _format_matrix_table(matrix)
    lines = table.splitlines()
    # Header + separator + 16 data rows = 18 lines.
    assert len(lines) == 18
    assert lines[0].startswith("| line_item | Test Co |")
    assert lines[1].startswith("|---|---|")
    # Every data row marks 'OK' since every line item is populated.
    for row in lines[2:]:
        assert "OK" in row


def test_format_matrix_table_marks_unpopulated_with_period() -> None:
    """Unpopulated cells render as '.' so a glance shows gaps."""
    matrix = {
        ("0001234567", "2024-12-31", "Test Co"): {
            name: False for name in CANONICAL_LINE_ITEMS
        }
    }
    table = _format_matrix_table(matrix)
    # 16 data rows each contain at least one '.' (the only data cell).
    data_rows = table.splitlines()[2:]
    for row in data_rows:
        assert "| . |" in row
