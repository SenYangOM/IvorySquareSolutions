"""interpret_m_score_components — L2 interpretation skill.

Takes a caller-supplied mapping of the eight Beneish component values
(as emitted by ``compute_beneish_m_score``) and returns, for each
component, a :class:`mvp.engine.rule_executor.ComponentInterpretation`
— the severity band, the paper-anchored interpretation text, the
follow-up questions, and the citations back to the underlying canonical
line items.

Per P1 / P2:
- Thresholds are NOT hard-coded here — they live in
  ``mvp/rules/templates/m_score_components.yaml`` (authored by the
  accounting_expert persona in Phase 3). This skill is the engine-side
  consumer of that template.
- No LLM call. The interpretation text is the YAML's ``interpretation``
  block, prepended with a header line that stamps the specific
  component value + fiscal-year-end (see
  :func:`mvp.engine.rule_executor.apply_component_rules`).

The caller passes ``components`` directly so the composite skill
``analyze_for_red_flags`` can pipe ``compute_beneish_m_score``'s output
into this without re-computing anything.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml

from mvp.engine.rule_executor import (
    ComponentInterpretation,
    apply_component_rules,
)
from mvp.ingestion.filings_ingest import find_filing, find_prior_year_filing
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements


_MVP_ROOT = Path(__file__).resolve().parents[3]
_RULE_TEMPLATE_PATH = _MVP_ROOT / "rules" / "templates" / "m_score_components.yaml"

_BENEISH_COMPONENTS = ("DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA")
"""The eight Beneish ratio components, in the order the paper lists them."""


class InterpretMScoreComponents(Skill):
    id = "interpret_m_score_components"
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

        # Resolve the pair of canonical statements so the rule executor can
        # attach per-component citations back to the underlying line items.
        cur_ref = find_filing(cik, fiscal_year_end)
        if cur_ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fiscal_year_end!r}"
            )
        prior_ref = find_prior_year_filing(cik, fiscal_year_end)
        if prior_ref is None:
            raise _MissingPriorYear(
                f"no prior-year sample filing for cik={cik!r} "
                f"(year t fiscal_year_end={fiscal_year_end!r})"
            )

        cur_filing_id = f"{cur_ref.cik}/{cur_ref.accession}"
        prior_filing_id = f"{prior_ref.cik}/{prior_ref.accession}"
        cur_stmts = build_canonical_statements(cur_filing_id)
        prior_stmts = build_canonical_statements(prior_filing_id)
        canonical_statements = {"t": cur_stmts, "t-1": prior_stmts}

        rule_template = _load_rule_template()
        fpe = date.fromisoformat(fiscal_year_end)

        interpretations: list[ComponentInterpretation] = []
        for name in _BENEISH_COMPONENTS:
            value = components_raw.get(name)
            if value is not None and not isinstance(value, (int, float)):
                raise _BadComponents(
                    f"components.{name} must be a number or null, got "
                    f"{type(value).__name__}"
                )
            interp = apply_component_rules(
                rule_template=rule_template,
                component_name=name,
                value=None if value is None else float(value),
                canonical_statements=canonical_statements,
                fiscal_period_end=fpe,
            )
            interpretations.append(interp)

        # Deduplicate citations at the skill top level so an MCP caller sees
        # one Citation per (doc_id, locator) across the entire output.
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
                + " (underlying canonical line items unavailable)."
            )

        # Pull in the pre-iXBRL data-quality warning if any statement carries it.
        pre_ixbrl = any(
            s.data_quality_flag == "pre_ixbrl_sgml_manual_extraction"
            for s in cur_stmts + prior_stmts
        )
        if pre_ixbrl:
            warnings.append(
                "pre_ixbrl_manual_extraction: underlying line items for "
                f"filing {cur_filing_id} and/or {prior_filing_id} were sourced "
                "from the hand-authored SGML manual-extraction fixture. "
                "Confidence is capped at 0.7."
            )

        overall = _build_overall_interpretation(
            cur_ref_issuer=cur_ref.issuer,
            cur_ref_fye=fiscal_year_end,
            interpretations=interpretations,
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
                "rule_template_path": "rules/templates/m_score_components.yaml",
                "rule_template_version": str(rule_template.get("template_version", "")),
                "cur_filing_id": cur_filing_id,
                "prior_filing_id": prior_filing_id,
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


_SEVERITY_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "indeterminate_null": 0}


def _build_overall_interpretation(
    *,
    cur_ref_issuer: str,
    cur_ref_fye: str,
    interpretations: list[ComponentInterpretation],
) -> str:
    """Deterministic narrative summary — 2–4 sentences, company-specific.

    Names the filing, enumerates high/medium-severity components with
    their values, names indeterminate components, and closes with the
    M-score threshold context. No LLM; the per-company specificity
    comes from real line-item values being substituted into the text.
    """
    flagged = [
        i for i in interpretations if i.band_matched.severity in ("critical", "high")
    ]
    watch = [i for i in interpretations if i.band_matched.severity == "medium"]
    null = [i for i in interpretations if i.value is None]

    sentences: list[str] = []
    lead = (
        f"Beneish-ratio interpretation for {cur_ref_issuer} "
        f"(fiscal year ending {cur_ref_fye}): "
    )

    if flagged:
        phrases = [
            f"{i.component}={i.value:.4f} ({i.band_matched.severity})" for i in flagged
        ]
        sentences.append(
            lead
            + f"{len(flagged)} component(s) reached high or critical severity: "
            + ", ".join(phrases) + "."
        )
    else:
        sentences.append(
            lead + "no component reached high or critical severity."
        )

    if watch:
        phrases = [f"{i.component}={i.value:.4f}" for i in watch]
        sentences.append(
            f"{len(watch)} additional component(s) landed in the medium band "
            f"({', '.join(phrases)}) — worth a read-through but not standalone signals."
        )

    if null:
        sentences.append(
            f"{len(null)} component(s) could not be computed: "
            + ", ".join(i.component for i in null)
            + " (source line items missing)."
        )

    sentences.append(
        "The overall Beneish M-score flags a filing when the composite exceeds the "
        "paper threshold of -1.78; component-level interpretations above should be "
        "read as drivers of that composite, not as independent verdicts."
    )
    return " ".join(sentences)


def _compute_confidence(
    *,
    source_confidence: Any,
    pre_ixbrl: bool,
    interpretations: list[ComponentInterpretation],
) -> float:
    # Inherit the upstream skill's confidence if passed, otherwise derive
    # from the data-quality flag of the underlying statements.
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
    # Drop confidence proportionally to the count of null components.
    nulls = sum(1 for i in interpretations if i.value is None)
    if nulls:
        c -= 0.05 * nulls
    if c < 0.0:
        c = 0.0
    return round(c, 4)


# ---------------------------------------------------------------------------
# Typed errors.
# ---------------------------------------------------------------------------


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class _MissingPriorYear(LibError):
    error_code = "missing_prior_year"
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


SKILL = InterpretMScoreComponents
