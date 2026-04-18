"""interpret_z_score_components — L2 interpretation skill.

Altman-Z analogue of ``interpret_m_score_components``. Takes the five
Altman (1968) component values (X1 through X5) as emitted by
``compute_altman_z_score`` and returns per-component severity bands +
interpretation text + follow-up questions + citations.

Per P1 / P2:
- Thresholds live in ``mvp/rules/templates/z_score_components.yaml``,
  not in Python.
- X4's numerator (market value of equity) does not live on a filing —
  it's an engineering-owned fixture at ``data/market_data/equity_values.yaml``.
  The rule executor's ``citations_required`` list for X4 therefore
  excludes ``market_value_of_equity``; this skill attaches a
  fixture-resolvable citation for X4 via ``build_market_data_citation``
  when the caller passes ``market_value_of_equity_citation`` alongside
  the component values.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from mvp.engine.rule_executor import (
    ComponentInterpretation,
    apply_component_rules,
    build_market_data_citation,
)
from mvp.ingestion.filings_ingest import find_filing
from mvp.ingestion.market_data_loader import load_equity_values
from mvp.lib.citation import Citation
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements


_MVP_ROOT = Path(__file__).resolve().parents[3]
_RULE_TEMPLATE_PATH = _MVP_ROOT / "rules" / "templates" / "z_score_components.yaml"

_ALTMAN_COMPONENTS = ("X1", "X2", "X3", "X4", "X5")


class InterpretZScoreComponents(Skill):
    id = "interpret_z_score_components"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fiscal_year_end = str(inputs["fiscal_year_end"])
        components_raw = inputs["components"]
        if not isinstance(components_raw, dict):
            raise _BadComponents(
                f"components must be a mapping, got {type(components_raw).__name__}"
            )
        source_confidence = inputs.get("source_confidence")

        cur_ref = find_filing(cik, fiscal_year_end)
        if cur_ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fiscal_year_end!r}"
            )
        cur_filing_id = f"{cur_ref.cik}/{cur_ref.accession}"
        cur_stmts = build_canonical_statements(cur_filing_id)
        # Altman Z uses only year-t canonical statements; no prior-year
        # balance is needed (X2, X1, X3, X5 are all current-year).
        canonical_statements = {"t": cur_stmts}

        rule_template = _load_rule_template()
        fpe = date.fromisoformat(fiscal_year_end)

        # Build the X4 fixture citation once (so it can be attached as
        # extra_citations to the X4 component's interpretation).
        x4_citation = _build_x4_citation(cik=cik, fiscal_year_end=fiscal_year_end)

        interpretations: list[ComponentInterpretation] = []
        for name in _ALTMAN_COMPONENTS:
            value = components_raw.get(name)
            if value is not None and not isinstance(value, (int, float)):
                raise _BadComponents(
                    f"components.{name} must be a number or null, got "
                    f"{type(value).__name__}"
                )
            extras = [x4_citation] if (name == "X4" and x4_citation is not None) else None
            interp = apply_component_rules(
                rule_template=rule_template,
                component_name=name,
                value=None if value is None else float(value),
                canonical_statements=canonical_statements,
                fiscal_period_end=fpe,
                extra_citations=extras,
            )
            interpretations.append(interp)

        # Flat dedup citations.
        seen: set[tuple[str, str]] = set()
        flat_citations: list[dict[str, Any]] = []
        for interp in interpretations:
            for c in interp.citations:
                key = (c.doc_id, c.locator)
                if key in seen:
                    continue
                seen.add(key)
                flat_citations.append(c.model_dump(mode="json"))

        warnings: list[str] = []
        null_components = [
            interp.component for interp in interpretations if interp.value is None
        ]
        if null_components:
            warnings.append(
                "null_components: "
                + ", ".join(null_components)
                + " (underlying canonical line items or fixture rows unavailable)."
            )
        pre_ixbrl = any(
            s.data_quality_flag == "pre_ixbrl_sgml_manual_extraction"
            for s in cur_stmts
        )
        if pre_ixbrl:
            warnings.append(
                "pre_ixbrl_manual_extraction: underlying line items for "
                f"filing {cur_filing_id} were sourced from the hand-authored "
                "SGML manual-extraction fixture. Confidence is capped at 0.7."
            )

        overall = _build_overall_interpretation(
            cur_ref_issuer=cur_ref.issuer,
            cur_ref_fye=fiscal_year_end,
            interpretations=interpretations,
            rule_template=rule_template,
            z_score=inputs.get("z_score"),
            z_flag=inputs.get("z_flag"),
        )
        confidence = _compute_confidence(
            source_confidence=source_confidence,
            pre_ixbrl=pre_ixbrl,
            interpretations=interpretations,
        )
        return {
            "component_interpretations": [
                interp.model_dump(mode="json") for interp in interpretations
            ],
            "overall_interpretation": overall,
            "citations": flat_citations,
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "rule_template_path": "rules/templates/z_score_components.yaml",
                "rule_template_version": str(rule_template.get("template_version", "")),
                "cur_filing_id": cur_filing_id,
            },
        }


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _load_rule_template() -> dict[str, Any]:
    with _RULE_TEMPLATE_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict) or "components" not in raw:
        raise _TemplateError(
            f"rule template at {_RULE_TEMPLATE_PATH} is missing 'components' list"
        )
    return raw


def _build_x4_citation(*, cik: str, fiscal_year_end: str) -> Citation | None:
    """Build the market-data-fixture citation for X4's numerator.

    Returns ``None`` when the fixture does not contain a row for
    ``(cik, fiscal_year_end)`` — the rule executor's null-band path
    will then surface the indeterminate_null interpretation.
    """
    try:
        entries = load_equity_values()
    except Exception:
        return None
    for entry in entries:
        if entry.cik == cik and entry.fiscal_year_end == fiscal_year_end:
            fye_date = date.fromisoformat(entry.fiscal_year_end)
            fixture_excerpt = (
                f"cik={entry.cik} fye={entry.fiscal_year_end} "
                f"shares={entry.shares_outstanding} price={entry.share_price_usd} "
                f"mve={entry.market_value_of_equity_usd}"
            )
            return build_market_data_citation(
                cik=cik,
                fiscal_year_end=fye_date,
                fixture_excerpt=fixture_excerpt,
                market_value_of_equity=entry.market_value_of_equity_usd,
            )
    return None


_ZONE_ORDER = ("distress", "grey_zone", "safe")


def _nearest_component_to_threshold(
    interpretations: list[ComponentInterpretation],
    rule_template: dict[str, Any],
) -> list[str]:
    """Return up to two component ids whose values are closest to any
    threshold boundary documented in the rule template.

    The output is a human-readable hint for the overall narrative;
    when all components are null, an empty list is returned.
    """
    # Collect explicit numeric thresholds from each component's rules.
    comp_blocks = {c["component"]: c for c in rule_template.get("components", [])}
    proximities: list[tuple[float, str]] = []
    for interp in interpretations:
        if interp.value is None:
            continue
        block = comp_blocks.get(interp.component)
        if not block:
            continue
        rules = block.get("interpretation_rules", [])
        boundaries: list[float] = []
        for rule in rules:
            cond = str(rule.get("condition", ""))
            boundaries.extend(_extract_numbers(cond))
        if not boundaries:
            continue
        closest = min(abs(interp.value - b) for b in boundaries)
        proximities.append((closest, interp.component))
    proximities.sort()
    return [name for _, name in proximities[:2]]


def _extract_numbers(s: str) -> list[float]:
    """Return every float literal embedded in ``s`` (rule-condition strings)."""
    import re

    out = []
    for m in re.finditer(r"-?\d+(?:\.\d+)?", s):
        try:
            out.append(float(m.group(0)))
        except ValueError:
            continue
    return out


def _build_overall_interpretation(
    *,
    cur_ref_issuer: str,
    cur_ref_fye: str,
    interpretations: list[ComponentInterpretation],
    rule_template: dict[str, Any],
    z_score: Any,
    z_flag: Any,
) -> str:
    """Deterministic summary — names the zone (if z_flag passed) and names
    the two components whose values sit closest to their paper thresholds.
    """
    sentences: list[str] = []
    lead = (
        f"Altman-Z interpretation for {cur_ref_issuer} "
        f"(fiscal year ending {cur_ref_fye}): "
    )

    null = [i for i in interpretations if i.value is None]

    # Z-zone narration
    if z_flag in ("safe", "grey_zone", "distress"):
        thresholds = rule_template.get("z_score_thresholds", {})
        zone_label = {
            "safe": f"safe zone (Z > {thresholds.get('safe_threshold', 2.99)})",
            "grey_zone": (
                f"grey zone ({thresholds.get('distress_threshold', 1.81)} "
                f"<= Z <= {thresholds.get('grey_zone_upper_bound', 2.99)})"
            ),
            "distress": f"distress zone (Z < {thresholds.get('distress_threshold', 1.81)})",
        }[z_flag]
        z_str = f"Z={z_score:.4f}" if isinstance(z_score, (int, float)) else "Z=<unknown>"
        sentences.append(lead + f"composite {z_str} places the filing in the {zone_label}.")
    elif z_flag == "indeterminate" or (z_flag is None and null):
        names = ", ".join(i.component for i in null) or "one or more components"
        sentences.append(
            lead + f"composite Z is indeterminate because {names} could not be computed."
        )
    else:
        sentences.append(lead + "composite Z zone not supplied.")

    # Nearest-threshold component commentary
    nearest = _nearest_component_to_threshold(interpretations, rule_template)
    if nearest:
        phrases = []
        for name in nearest:
            interp = next((i for i in interpretations if i.component == name), None)
            if interp is None or interp.value is None:
                continue
            phrases.append(
                f"{name}={interp.value:.4f} ({interp.band_matched.severity})"
            )
        if phrases:
            sentences.append(
                "Components closest to their paper-threshold boundaries: "
                + ", ".join(phrases) + "."
            )

    if null:
        sentences.append(
            f"{len(null)} component(s) could not be computed: "
            + ", ".join(i.component for i in null)
            + "."
        )

    sentences.append(
        "Altman's 1968 cut-offs place Z < 1.81 in the distress zone, Z > 2.99 in "
        "the safe zone, and 1.81 <= Z <= 2.99 in the zone of ignorance; per-component "
        "interpretations above are drivers of the composite, not independent verdicts."
    )
    return " ".join(sentences)


def _compute_confidence(
    *,
    source_confidence: Any,
    pre_ixbrl: bool,
    interpretations: list[ComponentInterpretation],
) -> float:
    if source_confidence is not None:
        try:
            c = float(source_confidence)
        except (TypeError, ValueError):
            c = 1.0
    else:
        c = 1.0
    cap = 0.7 if pre_ixbrl else 0.95
    if c > cap:
        c = cap
    nulls = sum(1 for i in interpretations if i.value is None)
    if nulls:
        c -= 0.05 * nulls
    if c < 0.0:
        c = 0.0
    return round(c, 4)


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class _BadComponents(LibError):
    error_code = "bad_components"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class _TemplateError(LibError):
    error_code = "rule_template_error"
    error_category = ErrorCategory.INTERNAL
    retry_safe = False


SKILL = InterpretZScoreComponents
