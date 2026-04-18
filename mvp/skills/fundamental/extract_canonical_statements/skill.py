"""extract_canonical_statements — L1 fundamental skill.

Pulls the three canonical financial statements (IS / BS / CF) for a
given (cik, fiscal_year_end), using :func:`mvp.standardize.statements.build_canonical_statements`.
Thin skill-layer wrapper: validates inputs via the manifest schema,
reformats errors into structured envelopes, flattens the
per-line-item citations into a deduped top-level list, and tags data-
quality flags into ``warnings``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import find_filing
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements


class ExtractCanonicalStatements(Skill):
    id = "extract_canonical_statements"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fiscal_year_end = str(inputs["fiscal_year_end"])
        role_filter = inputs.get("statement_role", "all")

        ref = find_filing(cik, fiscal_year_end)
        if ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} "
                f"fiscal_year_end={fiscal_year_end!r}"
            )
        filing_id = f"{ref.cik}/{ref.accession}"
        statements = build_canonical_statements(filing_id)

        warnings: list[str] = []
        # Propagate data-quality flags — pre-iXBRL filings should
        # surface to downstream callers for confidence degradation.
        if statements and statements[0].data_quality_flag == "pre_ixbrl_sgml_manual_extraction":
            warnings.append(
                "data_quality: pre_ixbrl_sgml_manual_extraction — values sourced "
                "from a hand-authored YAML fixture (reviewed by accounting_expert)."
            )

        filtered = [
            s for s in statements
            if role_filter == "all" or s.statement_role == role_filter
        ]
        statements_json = [s.model_dump(mode="json") for s in filtered]

        # Flatten citations, dedupe on (doc_id, locator).
        seen: set[tuple[str, str]] = set()
        flat: list[dict[str, Any]] = []
        for s in filtered:
            for li in s.line_items:
                key = (li.citation.doc_id, li.citation.locator)
                if key in seen:
                    continue
                seen.add(key)
                flat.append(li.citation.model_dump(mode="json"))

        null_count = sum(
            1 for s in filtered for li in s.line_items if li.value_usd is None
        )
        if null_count > 0:
            warnings.append(
                f"{null_count} line item(s) had no matching concept in the source "
                f"filing; their values are null."
            )

        return {
            "statements": statements_json,
            "citations": flat,
            "warnings": warnings,
        }


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


SKILL = ExtractCanonicalStatements
