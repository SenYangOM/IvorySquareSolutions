"""workshop.paper_to_skill.inspect_canonical — what's actually populated?

A small helper for the ``quant_finance_methodologist`` persona to ask:
"if I author a skill that needs line items X, Y, Z, will those be
populated for the 5 MVP sample filings?"

Written during paper 2 onboarding (Kim & Nikolaev 2024). The
methodologist had assumed ``net_income`` was a canonical line item
because it's the natural input for the paper's Hayn-1995-style loss
indicator. It is not — the 16 canonical line items stop at EBIT in
the income-statement role and go straight to the balance-sheet items.
That discovery cost ~10 minutes of trial-and-error CLI runs and a
silently-failing first draft of the skill that returned ``loss=null``
for every issuer. This helper would have made the gap visible in
30 seconds.

The point of codifying this is: every future paper-onboarding
iteration starts with "what does the paper need? what do I have?"
The methodologist persona writes the skill against the answer to
the second question, which means the second question must be cheap
to ask.

Usage
-----
As a CLI::

    python -m workshop.paper_to_skill.inspect_canonical

Prints a per-issuer table showing which canonical line items are
populated (value != null) for the 5 MVP sample filings. The
sample-filing catalogue comes from ``mvp.ingestion.filings_ingest``;
the canonical line items come from ``mvp.standardize.mappings``.

As a library::

    from workshop.paper_to_skill.inspect_canonical import (
        line_item_population_for_filing,
        line_item_population_matrix,
    )
    matrix = line_item_population_matrix()  # dict of (cik, fye) → dict[name → bool]

Separation contract per ``SPEC_UPDATES.md`` §13.3: this script may
import from ``mvp.*`` but ``mvp/`` must not import from
``workshop/``.
"""

from __future__ import annotations

import argparse
import sys
from typing import Iterable

from mvp.ingestion.filings_ingest import find_prior_year_filing, sample_filings
from mvp.standardize.mappings import CONCEPT_MAPPINGS
from mvp.standardize.statements import build_canonical_statements


# Sample issuers — ordered by the FYE we score against (year t).
# Mirrors the 5 MVP sample issuers used by every paper-derived skill.
_SAMPLE_PAIRS: tuple[tuple[str, str, str], ...] = (
    ("0001024401", "2000-12-31", "Enron FY2000"),
    ("0000723527", "2001-12-31", "WorldCom FY2001"),
    ("0000320193", "2023-09-30", "Apple FY2023"),
    ("0000789019", "2023-06-30", "Microsoft FY2023"),
    ("0001690820", "2022-12-31", "Carvana FY2022"),
)

CANONICAL_LINE_ITEMS: tuple[str, ...] = tuple(sorted(CONCEPT_MAPPINGS.keys()))


def line_item_population_for_filing(
    cik: str, fiscal_year_end: str
) -> dict[str, bool]:
    """Return a name → populated mapping for one filing.

    A line item is "populated" iff its ``value_usd`` is not None in
    the canonical statements built from the filing's facts. Missing
    line items (mapped concept absent from companyfacts or manual
    extraction) are False; missing-from-the-canonical-set is also
    False.
    """
    cur_ref = _find_filing(cik, fiscal_year_end)
    if cur_ref is None:
        return {name: False for name in CANONICAL_LINE_ITEMS}
    stmts = build_canonical_statements(f"{cur_ref.cik}/{cur_ref.accession}")
    populated: dict[str, bool] = {name: False for name in CANONICAL_LINE_ITEMS}
    for s in stmts:
        for li in s.line_items:
            if li.name in populated:
                populated[li.name] = li.value_usd is not None
    return populated


def line_item_population_matrix() -> dict[tuple[str, str, str], dict[str, bool]]:
    """Return the population matrix for the 5 MVP sample filings.

    Keys are ``(cik, fiscal_year_end, label)`` triples (label is for
    display only). Values are name → populated dicts.
    """
    out: dict[tuple[str, str, str], dict[str, bool]] = {}
    for cik, fye, label in _SAMPLE_PAIRS:
        out[(cik, fye, label)] = line_item_population_for_filing(cik, fye)
    return out


def _find_filing(cik: str, fye: str):
    """Locate the FilingRef for (cik, fye) in the sample catalogue."""
    for ref in sample_filings():
        if ref.cik == cik and str(ref.fiscal_period_end) == fye:
            return ref
    return None


def _format_matrix_table(
    matrix: dict[tuple[str, str, str], dict[str, bool]]
) -> str:
    """Format the population matrix as a Markdown-style table."""
    headers = [label for (_cik, _fye, label) in matrix.keys()]
    lines: list[str] = []
    lines.append("| line_item | " + " | ".join(headers) + " |")
    lines.append("|" + "---|" * (len(headers) + 1))
    for name in CANONICAL_LINE_ITEMS:
        row_cells = [
            "OK" if matrix[k].get(name, False) else "."
            for k in matrix.keys()
        ]
        lines.append(f"| {name} | " + " | ".join(row_cells) + " |")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="workshop.paper_to_skill.inspect_canonical",
        description=(
            "Print a per-issuer table showing which canonical line "
            "items are populated for the 5 MVP sample filings. Useful "
            "before authoring a paper-derived skill: catches gaps like "
            "'net_income is not a canonical line item' before you "
            "discover them via a silent loss=null in your output."
        ),
    )
    p.add_argument(
        "--show-prior-year",
        action="store_true",
        help=(
            "Also print, for each sample issuer, whether a prior-year "
            "filing is available (skills like compute_beneish_m_score "
            "and compute_context_importance_signals need t-1 inputs)."
        ),
    )
    return p


def main(argv: Iterable[str] | None = None) -> int:
    args = _build_parser().parse_args(list(argv) if argv else None)
    matrix = line_item_population_matrix()
    print("# Canonical line-item population for the 5 MVP sample filings")
    print()
    print(_format_matrix_table(matrix))
    if args.show_prior_year:
        print()
        print("## Prior-year availability (for skills that need year t-1)")
        print()
        for cik, fye, label in _SAMPLE_PAIRS:
            prior = find_prior_year_filing(cik, fye)
            status = (
                f"prior FYE {prior.fiscal_period_end}"
                if prior is not None
                else "MISSING — t-1 signals will be null"
            )
            print(f"- {label}: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


__all__ = [
    "CANONICAL_LINE_ITEMS",
    "line_item_population_for_filing",
    "line_item_population_matrix",
    "main",
]
