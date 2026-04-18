"""Citation validation + resolution for the skill boundary.

Every skill that produces cited output must pass its outputs through
:func:`validate_citations` before returning — this is the gate that
enforces the manifest's ``citation_contract``. The contract lists
required fields; the validator verifies each has at least one citation
attached.

:func:`resolve_citation` takes a ``(doc_id, locator)`` citation and
returns a dict with ``passage_text``, ``surrounding_context``, and
``source_url``. This is the canonical implementation of Operating
Principle P3's "citations are resolvable via skill, not by parsing" —
a cold agent invokes ``resolve_citation`` rather than reading the
filings tree itself.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from mvp.lib.citation import Citation
from mvp.skills.manifest_schema import SkillManifest
from mvp.standardize.mappings import CONCEPT_MAPPINGS, LINE_ITEM_STATEMENT
from mvp.standardize.statements import build_canonical_statements
from mvp.store.doc_store import get_doc_text


@dataclass(frozen=True)
class CitationValidationError:
    """A single missing-citation violation."""

    field_path: str
    requirement_text: str
    detail: str


def validate_citations(
    outputs: dict[str, Any],
    manifest: SkillManifest,
) -> list[CitationValidationError]:
    """Check the skill's ``outputs`` against the manifest's ``citation_contract``.

    For each entry in ``citation_contract.required_per_field`` the
    validator ensures the named field exists in ``outputs`` AND, if the
    field is supposed to carry citations, at least one :class:`Citation`
    is present. "Supposed to carry citations" is inferred from the key
    name: the contract uses JSON-path-style keys (``"components.*"``,
    ``"m_score"``) — dotted paths resolve in ``outputs``, and the
    validator asserts the `outputs["citations"]` array is non-empty when
    any contract entry is present.

    Returns an empty list on success. A non-empty list is a hard
    violation — the skill boundary turns it into a structured error.
    """
    errors: list[CitationValidationError] = []
    contract = manifest.citation_contract.required_per_field
    if not contract:
        return errors

    # For every required field, ensure (a) the field is present in
    # outputs and non-null, (b) the top-level ``citations`` list exists
    # and is non-empty.
    citations_present = _has_citations(outputs)
    for key, requirement_text in contract.items():
        leaf_value = _resolve_dotted_path(outputs, key)
        if leaf_value is _SENTINEL_MISSING:
            errors.append(
                CitationValidationError(
                    field_path=key,
                    requirement_text=requirement_text,
                    detail=f"required field {key!r} not present in output",
                )
            )
            continue
        if leaf_value is None:
            # A null field is allowed (e.g. indeterminate M-score), but it
            # still needs an accompanying warnings entry — the skill
            # layer handles that; the citation contract is silent on
            # nulls, so we don't flag them here.
            continue
        if not citations_present:
            errors.append(
                CitationValidationError(
                    field_path=key,
                    requirement_text=requirement_text,
                    detail=(
                        "citation_contract lists this field as requiring citations, "
                        "but the output's 'citations' array is missing or empty"
                    ),
                )
            )
    return errors


def resolve_citation(citation: Citation) -> dict[str, Any]:
    """Resolve a :class:`Citation` to a short dict an agent can inspect.

    Returns a mapping with:

    - ``passage_text`` — the canonical excerpt the locator points at.
    - ``surrounding_context`` — a short string snippet around the
      passage inside the source document (best-effort for SGML/HTML
      filings; empty for market-data fixture citations).
    - ``source_url`` — the URL the citation's ``doc_id`` was fetched
      from, pulled from the filing's ``meta.json`` or the market-data
      fixture.

    This function covers the three citation shapes in MVP outputs:

    1. Filing canonical-statement citations — ``doc_id`` is
       ``"<cik>/<accession>"`` and the locator's line-item part matches
       a canonical name. The canonical statement JSON is the source of
       record; we return the line item's value as the passage text.
    2. Sentinel-hash citations on null line items — the hash is the
       deterministic sentinel from :mod:`mvp.standardize.statements`;
       we report the sentinel back.
    3. Market-data fixture citations — ``doc_id`` is
       ``"market_data/equity_values"``; we return the fixture row.
    """
    doc_id = citation.doc_id
    if doc_id == "market_data/equity_values":
        return _resolve_market_data(citation)
    # Filing citation: doc_id = "<cik>/<accession>".
    if "/" in doc_id:
        return _resolve_filing(citation)
    return {
        "passage_text": "",
        "surrounding_context": "",
        "source_url": "",
        "resolved": False,
        "reason": "unknown_doc_id_shape",
    }


# ---------------------------------------------------------------------------
# Resolvers.
# ---------------------------------------------------------------------------


_MVP_ROOT = Path(__file__).resolve().parent.parent
_MARKET_DATA_PATH = _MVP_ROOT / "data" / "market_data" / "equity_values.yaml"
_FILINGS_DIR = _MVP_ROOT / "data" / "filings"


def _resolve_filing(citation: Citation) -> dict[str, Any]:
    # Parse locator: ``<doc_id>::<statement_role>::<line_item>``.
    parts = citation.locator.split("::")
    if len(parts) != 3:
        return _unresolved(citation, "malformed_locator")
    _, statement_role, line_item = parts
    cik, accession = citation.doc_id.split("/", 1)

    if statement_role == "market_data":
        # Shouldn't normally hit here because doc_id wasn't market_data,
        # but defensive.
        return _unresolved(citation, "wrong_role_for_filing_doc_id")

    if statement_role == "mdna":
        # Narrative MD&A citation (locator form
        # ``<cik>/<accession>::mdna::item_7`` used by extract_mdna and
        # compute_mdna_upfrontedness). Resolve by reading the filing's
        # primary document and returning a short passage preview — the
        # full section text is not embedded in the citation envelope.
        return _resolve_mdna(citation, cik, accession, line_item)

    meta_path = _FILINGS_DIR / cik / accession / "meta.json"
    source_url = ""
    if meta_path.exists():
        try:
            import json as _json

            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            source_url = str(meta.get("source_url", ""))
        except (OSError, ValueError):
            source_url = ""

    # The canonical line-item's value is the "passage text" for a
    # structured financial-statement citation — it's what the citation
    # stands for. We rebuild canonical statements (cheap; reads cache)
    # and find the matching line.
    filing_id = f"{cik}/{accession}"
    try:
        stmts = build_canonical_statements(filing_id)
    except Exception as exc:  # standardize errors — we don't want to
        # propagate, per the "citations are resolvable" agent contract.
        return _unresolved(citation, f"standardize_error:{type(exc).__name__}")

    for s in stmts:
        if s.statement_role != statement_role and statement_role not in LINE_ITEM_STATEMENT.values():
            continue
        for li in s.line_items:
            if li.name == line_item and li.citation.locator == citation.locator:
                value_str = "null" if li.value_usd is None else str(li.value_usd)
                concept_hint = (
                    li.source_concept
                    or (CONCEPT_MAPPINGS.get(line_item) or ("unmapped",))[0]
                )
                passage = f"{line_item} ({li.unit}) = {value_str}"
                context = (
                    f"Canonical line item {line_item!r} on "
                    f"{s.statement_role} for filing {filing_id} "
                    f"(fiscal period ending {s.fiscal_period_end.isoformat()}). "
                    f"Source concept: {concept_hint}. "
                    f"Data quality: {s.data_quality_flag}."
                )
                return {
                    "passage_text": passage,
                    "surrounding_context": context,
                    "source_url": source_url,
                    "resolved": True,
                }
    return _unresolved(citation, "line_item_not_found_in_canonical_statements")


def _resolve_market_data(citation: Citation) -> dict[str, Any]:
    if not _MARKET_DATA_PATH.exists():
        return _unresolved(citation, "market_data_fixture_missing")
    try:
        raw = yaml.safe_load(_MARKET_DATA_PATH.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        return _unresolved(citation, f"market_data_yaml_error:{exc}")
    if not isinstance(raw, dict) or not isinstance(raw.get("entries"), list):
        return _unresolved(citation, "market_data_shape_invalid")

    # Locator format: market_data::market_value_of_equity_<cik>_<fye>
    parts = citation.locator.split("::")
    if len(parts) != 3:
        return _unresolved(citation, "malformed_locator")
    line_item = parts[2]
    if not line_item.startswith("market_value_of_equity_"):
        return _unresolved(citation, "market_data_wrong_prefix")
    tail = line_item[len("market_value_of_equity_"):]
    try:
        cik, fye_str = tail.split("_", 1)
        date.fromisoformat(fye_str)
    except ValueError:
        return _unresolved(citation, "market_data_locator_parts_invalid")

    for entry in raw["entries"]:
        if not isinstance(entry, dict):
            continue
        if entry.get("cik") == cik and entry.get("fiscal_year_end") == fye_str:
            mve = entry.get("market_value_of_equity_usd")
            shares = entry.get("shares_outstanding")
            price = entry.get("share_price_usd")
            passage = (
                f"market_value_of_equity_usd = {mve} "
                f"(shares_outstanding = {shares} × share_price_usd = {price})"
            )
            context = (
                f"Market-data fixture entry for issuer {entry.get('issuer', '?')} "
                f"at fiscal year end {fye_str}. "
                f"Shares source: {entry.get('shares_source', 'unknown')}. "
                f"Price source: {entry.get('price_source', 'unknown')}. "
                f"Notes: {entry.get('notes', '').strip()}"
            )
            return {
                "passage_text": passage,
                "surrounding_context": context,
                "source_url": str(entry.get("price_source", "")),
                "resolved": True,
            }
    return _unresolved(citation, "market_data_entry_not_found")


def _resolve_mdna(
    citation: Citation, cik: str, accession: str, line_item: str
) -> dict[str, Any]:
    """Resolve an MD&A narrative citation.

    Locator form: ``<cik>/<accession>::mdna::item_7``. Used by
    :mod:`mvp.skills.fundamental.extract_mdna` and
    :mod:`mvp.skills.paper_derived.compute_mdna_upfrontedness`.

    Resolution strategy:
    1. Re-invoke ``extract_mdna`` via the registry. That's the
       canonical path the section text is reconstructed through.
    2. Return a short preview (first 400 chars, last 400 chars, plus
       a short header) as the passage_text — large enough for an
       agent to verify, small enough to not dump the whole section
       into the citation payload.
    3. The surrounding_context names the filing and the section
       boundaries.
    """
    if line_item != "item_7":
        return _unresolved(citation, "mdna_unknown_line_item")
    # Read source_url from the filing's meta.json.
    import json as _json

    meta_path = _FILINGS_DIR / cik / accession / "meta.json"
    source_url = ""
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            source_url = str(meta.get("source_url", ""))
        except (OSError, ValueError):
            source_url = ""

    # Import at call time to avoid a circular registry bootstrap.
    from mvp.skills.registry import default_registry

    try:
        mdna_skill = default_registry().get("extract_mdna")
    except KeyError:
        return _unresolved(citation, "extract_mdna_not_registered")

    mdna_out = mdna_skill.run(
        {
            "cik": cik,
            "fiscal_year_end": _lookup_fye_for_accession(cik, accession),
        }
    )
    if "error" in mdna_out:
        return _unresolved(
            citation,
            f"extract_mdna_errored:{mdna_out['error'].get('error_code', '?')}",
        )
    section_text = mdna_out.get("section_text")
    if not isinstance(section_text, str) or not section_text.strip():
        return _unresolved(citation, "mdna_section_not_located")

    # Short preview — first 400 chars + ellipsis + last 400 chars.
    preview = section_text.strip()
    if len(preview) > 1000:
        preview = preview[:400] + "\n\n[... truncated ...]\n\n" + preview[-400:]
    context = (
        f"MD&A (Item 7) for filing {cik}/{accession}. "
        f"Section length {len(section_text):,} chars. "
        f"Extractor: mvp.skills.fundamental.extract_mdna."
    )
    return {
        "passage_text": preview,
        "surrounding_context": context,
        "source_url": source_url,
        "resolved": True,
    }


def _lookup_fye_for_accession(cik: str, accession: str) -> str:
    """Look up fiscal_year_end for a (cik, accession) pair.

    ``extract_mdna`` takes fiscal_year_end rather than accession as
    input; we map back via ``mvp.ingestion.filings_ingest.sample_filings``.
    """
    from mvp.ingestion.filings_ingest import sample_filings

    for f in sample_filings():
        if f.cik == cik and f.accession == accession:
            return f.fiscal_period_end
    # Fallback: return an empty string; extract_mdna will error out
    # with unknown_filing, which the caller surfaces as a resolution
    # failure rather than leaking a cryptic error.
    return ""


def _unresolved(citation: Citation, reason: str) -> dict[str, Any]:
    return {
        "passage_text": "",
        "surrounding_context": "",
        "source_url": "",
        "resolved": False,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# Dotted-path resolver.
# ---------------------------------------------------------------------------


_SENTINEL_MISSING = object()


def _resolve_dotted_path(obj: Any, path: str) -> Any:
    """Resolve ``"components.*"`` / ``"m_score"`` style paths into ``obj``.

    - ``"foo"`` looks up obj["foo"].
    - ``"foo.bar"`` looks up obj["foo"]["bar"].
    - ``"foo.*"`` returns the list of values at obj["foo"].* (used for
      "every component's value"). Matches when obj["foo"] is a dict
      with any non-empty contents.
    """
    if not isinstance(obj, dict):
        return _SENTINEL_MISSING
    parts = path.split(".")
    cur: Any = obj
    for i, p in enumerate(parts):
        if p == "*":
            # Wildcard: cur must be a dict; succeed if any key exists.
            if isinstance(cur, dict) and cur:
                return list(cur.values())
            return _SENTINEL_MISSING
        if not isinstance(cur, dict):
            return _SENTINEL_MISSING
        if p not in cur:
            return _SENTINEL_MISSING
        cur = cur[p]
    return cur


def _has_citations(outputs: dict[str, Any]) -> bool:
    """Return True if ``outputs`` carries a non-empty ``citations`` array anywhere."""
    # Top-level "citations"
    top = outputs.get("citations")
    if isinstance(top, list) and len(top) > 0:
        return True
    # Component-level: every component_interpretations[i].citations
    for key in ("component_interpretations", "interpretations"):
        comp = outputs.get(key)
        if isinstance(comp, list):
            for entry in comp:
                if isinstance(entry, dict):
                    cl = entry.get("citations")
                    if isinstance(cl, list) and cl:
                        return True
    # Composite: m_score_result.citations / z_score_result.citations
    for key in ("m_score_result", "z_score_result"):
        nested = outputs.get(key)
        if isinstance(nested, dict):
            if _has_citations(nested):
                return True
    return False


__all__ = [
    "CitationValidationError",
    "resolve_citation",
    "validate_citations",
]
