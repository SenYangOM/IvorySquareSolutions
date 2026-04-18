"""Deterministic rule executor for L2 interpretation skills.

Takes the declarative rule-template YAMLs authored in Phase 3 (under
``mvp/rules/templates/``) and applies them to a single component value
(e.g. ``DSRI = 1.365`` for Enron FY2000) plus the canonical statements
for year t and year t-1. Emits a :class:`ComponentInterpretation`:

- ``component``, ``value``, ``band_matched`` — identity + the severity
  band whose ``condition`` matched the value.
- ``interpretation_text`` — the band's ``interpretation`` text as
  authored in YAML (the accounting-expert persona's voice). Additional
  context lines are prepended when the component's underlying line
  items have a salient feature (pre-iXBRL data-quality flag, etc.);
  no LLM is involved.
- ``follow_up_questions`` — the YAML's list for the matched band.
- ``citations`` — one :class:`Citation` per entry in the band's
  ``citations_required`` list, resolved to the actual canonical line
  items for year t / year t-1 (or to the market-data fixture for
  Altman X4).
- ``contextual_caveats`` — the component-level ``contextual_caveats``
  from YAML, carried through verbatim so an agent reader sees the same
  caveats an accounting expert authored.

Determinism
-----------
* Band conditions are evaluated in YAML order; the first match wins.
  The Phase 3 rule templates are authored to partition the real line
  with no gaps, so a non-null numeric value always produces exactly
  one matching band.
* Null inputs (component value = ``None``) short-circuit to a synthetic
  band ``indeterminate_null`` with a scripted interpretation that names
  the missing inputs — no arithmetic is attempted.
* There is NO LLM call. Interpretation text is YAML + f-string-safe
  substitution. The :mod:`mvp.engine.llm_interpreter` is a separate
  optional refinement layer (not wired in at MVP).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict, Field

from mvp.lib.citation import Citation, build_locator
from mvp.lib.hashing import hash_excerpt
from mvp.store.schema import CanonicalLineItem, CanonicalStatement


# ---------------------------------------------------------------------------
# Pydantic output models.
# ---------------------------------------------------------------------------


class BandMatch(BaseModel):
    """The severity band whose ``condition`` matched the component value.

    Attributes
    ----------
    condition:
        Verbatim string from YAML (e.g. ``"value > 1.465"``).
    severity:
        One of ``low``, ``medium``, ``high``, ``critical``,
        or the synthetic ``indeterminate_null`` for missing inputs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    condition: str
    severity: str


class ComponentInterpretation(BaseModel):
    """The rule executor's output for a single component.

    This is the per-component payload the L2 ``interpret_*_components``
    skills return as a list, and it is what the L4 composite skill
    embeds into each paper-derived result's ``interpretations`` array.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    component: str = Field(min_length=1)
    value: float | None
    band_matched: BandMatch
    interpretation_text: str = Field(min_length=20)
    follow_up_questions: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    contextual_caveats: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API.
# ---------------------------------------------------------------------------


_COND_RE = re.compile(
    r"""
    ^\s*
    (?:
        value\s*(?P<op1>[<>]=?|==)\s*(?P<num1>-?\d+(?:\.\d+)?)  # e.g. value > 1.465
        |
        (?P<num2>-?\d+(?:\.\d+)?)\s*(?P<op2><=?|<)\s*value\s*(?P<op3><=?)\s*(?P<num3>-?\d+(?:\.\d+)?)
        # e.g. "1.1 < value <= 1.465"
    )
    \s*$
    """,
    re.VERBOSE,
)


def apply_component_rules(
    *,
    rule_template: dict[str, Any],
    component_name: str,
    value: float | None,
    canonical_statements: dict[str, list[CanonicalStatement]],
    fiscal_period_end: date,
    extra_citations: list[Citation] | None = None,
) -> ComponentInterpretation:
    """Apply the ``rule_template``'s rules for ``component_name`` to ``value``.

    Parameters
    ----------
    rule_template:
        The parsed YAML dict from ``rules/templates/m_score_components.yaml``
        or ``z_score_components.yaml``. Must contain a top-level
        ``components`` list of per-component blocks.
    component_name:
        Component id (e.g. ``"DSRI"``, ``"X1"``). Must match one of the
        entries in ``rule_template["components"]``.
    value:
        The computed component value. ``None`` triggers the
        ``indeterminate_null`` band path.
    canonical_statements:
        Mapping ``{"t": [IS, BS, CF], "t-1": [IS, BS, CF]}`` keyed by
        relative period tag. Used to resolve per-component citations.
    fiscal_period_end:
        Fiscal-year-end date of the "year t" filing (used for diagnostic
        stamping of the interpretation text).
    extra_citations:
        Additional :class:`Citation` objects that the skill wants to
        attach (e.g. the Altman X4 market-value-of-equity citation that
        comes from the market-data fixture, not from a filing).

    Returns
    -------
    ComponentInterpretation
        The matched band + interpretation text + citations.

    Raises
    ------
    KeyError
        If ``component_name`` is not present in the rule template.
    ValueError
        If no band matched a non-null ``value`` (indicates a rule-template
        bug — Phase 3 tests guarantee this never happens at runtime for
        the MVP's two templates, but the engine fails loudly per P2).
    """
    block = _find_component_block(rule_template, component_name)
    rules = block.get("interpretation_rules", [])
    if not isinstance(rules, list) or not rules:
        raise ValueError(
            f"rule template for {component_name!r} has no interpretation_rules"
        )

    if value is None:
        return _null_band(
            component_name=component_name,
            block=block,
            fiscal_period_end=fiscal_period_end,
            extra_citations=extra_citations,
        )

    for rule in rules:
        cond = rule.get("condition")
        if not isinstance(cond, str):
            continue
        if _evaluate_condition(cond, value):
            return _build_interpretation(
                component_name=component_name,
                value=value,
                rule=rule,
                block=block,
                canonical_statements=canonical_statements,
                fiscal_period_end=fiscal_period_end,
                extra_citations=extra_citations,
            )
    raise ValueError(
        f"no band in rule template matched value={value} for component {component_name!r}; "
        "rule templates must partition the real line — this is an authoring bug"
    )


# ---------------------------------------------------------------------------
# Internals.
# ---------------------------------------------------------------------------


def _find_component_block(rule_template: dict[str, Any], component_name: str) -> dict[str, Any]:
    comps = rule_template.get("components")
    if not isinstance(comps, list):
        raise KeyError("rule template missing top-level 'components' list")
    for block in comps:
        if isinstance(block, dict) and block.get("component") == component_name:
            return block
    raise KeyError(
        f"rule template has no block for component {component_name!r}"
    )


def _evaluate_condition(cond: str, value: float) -> bool:
    """Evaluate a two-operand arithmetic condition against ``value``.

    Accepts only the limited grammar used in the Phase 3 YAMLs:

    - ``value <op> <num>`` with ``<op>`` one of ``>``, ``>=``, ``<``, ``<=``, ``==``
    - ``<num> <op1> value <op2> <num>`` with each op one of ``<`` or ``<=``

    Any other shape returns ``False`` — no ``eval()`` is involved; the
    conditions are parsed via a fixed regex so a typo can't smuggle in
    arbitrary Python.
    """
    m = _COND_RE.match(cond.strip())
    if not m:
        return False
    if m.group("op1"):
        op = m.group("op1")
        num = float(m.group("num1"))
        return _compare(value, op, num)
    # Ranged: "<num> <op2> value <op3> <num>"
    lo = float(m.group("num2"))
    op2 = m.group("op2")
    op3 = m.group("op3")
    hi = float(m.group("num3"))
    lower_ok = _compare(lo, op2, value)  # e.g. 1.1 < value means 1.1 < value
    upper_ok = _compare(value, op3, hi)  # e.g. value <= 1.465
    return lower_ok and upper_ok


def _compare(a: float, op: str, b: float) -> bool:
    if op == ">":
        return a > b
    if op == ">=":
        return a >= b
    if op == "<":
        return a < b
    if op == "<=":
        return a <= b
    if op == "==":
        return a == b
    return False


def _build_interpretation(
    *,
    component_name: str,
    value: float,
    rule: dict[str, Any],
    block: dict[str, Any],
    canonical_statements: dict[str, list[CanonicalStatement]],
    fiscal_period_end: date,
    extra_citations: list[Citation] | None,
) -> ComponentInterpretation:
    condition = str(rule.get("condition", ""))
    severity = str(rule.get("severity", "unknown"))
    raw_text = str(rule.get("interpretation", "")).strip()
    follow_ups = [str(q) for q in rule.get("follow_up_questions", []) or []]
    caveats = [str(c) for c in block.get("contextual_caveats", []) or []]

    required = [str(c) for c in rule.get("citations_required", []) or []]
    citations = _resolve_citations_required(
        required,
        canonical_statements=canonical_statements,
    )
    if extra_citations:
        citations.extend(extra_citations)

    # Render the interpretation by prepending a one-line data header so
    # the text references the specific filing being scored. This is the
    # P1 "analyze this specific company's specific component values"
    # surface: value, fiscal-year-end, and band.
    header = (
        f"[{component_name} = {value:.4f} ({severity}) — "
        f"fiscal year ending {fiscal_period_end.isoformat()}]"
    )
    full_text = header + "\n\n" + raw_text
    return ComponentInterpretation(
        component=component_name,
        value=float(value),
        band_matched=BandMatch(condition=condition, severity=severity),
        interpretation_text=full_text,
        follow_up_questions=follow_ups,
        citations=citations,
        contextual_caveats=caveats,
    )


def _null_band(
    *,
    component_name: str,
    block: dict[str, Any],
    fiscal_period_end: date,
    extra_citations: list[Citation] | None,
) -> ComponentInterpretation:
    """Synthetic band for ``value is None`` — no line items found / component indeterminate."""
    canonical_inputs = [str(i) for i in block.get("canonical_inputs", []) or []]
    caveats = [str(c) for c in block.get("contextual_caveats", []) or []]

    inputs_line = ", ".join(canonical_inputs) or "(no inputs declared on rule template)"
    text = (
        f"[{component_name} = null (indeterminate) — fiscal year ending "
        f"{fiscal_period_end.isoformat()}]\n\n"
        f"This component could not be computed because one or more required inputs "
        f"were unavailable in the canonical statements for this filing. Required "
        f"inputs per the rule template are: {inputs_line}. The composite score is "
        f"marked indeterminate rather than computed with zero-filled inputs."
    )
    citations = list(extra_citations or [])
    return ComponentInterpretation(
        component=component_name,
        value=None,
        band_matched=BandMatch(
            condition="value is null",
            severity="indeterminate_null",
        ),
        interpretation_text=text,
        follow_up_questions=[],
        citations=citations,
        contextual_caveats=caveats,
    )


def _resolve_citations_required(
    required: Iterable[str],
    *,
    canonical_statements: dict[str, list[CanonicalStatement]],
) -> list[Citation]:
    """Resolve ``citations_required`` entries to concrete :class:`Citation` objects.

    Each ``required`` string follows the Phase 3 convention
    ``"<canonical_name> (period=t)"`` or ``"(period=t-1)"``. We strip the
    ``# ...`` comment tail that YAML preserves, match the canonical name
    against the canonical statements for the relevant period, and
    reuse the citation that :mod:`mvp.standardize.statements` already
    attached to the line item.

    Exogenous inputs (e.g. Altman X4's ``market_value_of_equity_t``)
    are not canonical line items — they don't live in
    ``canonical_statements`` — so they are skipped here; the skill that
    needs such a citation attaches it via the ``extra_citations``
    parameter.
    """
    out: list[Citation] = []
    for raw in required:
        parsed = _parse_required_citation(raw)
        if parsed is None:
            continue
        canonical_name, period_tag = parsed
        stmts = canonical_statements.get(period_tag, [])
        line = _find_line_item(stmts, canonical_name)
        if line is None:
            continue
        # Reuse the citation the standardize layer already built — it has
        # the right hash + locator. If the line item is null-valued, the
        # standardize layer still attached a sentinel-hash citation, which
        # we include so the provenance trail stays complete.
        out.append(line.citation)
    return out


_REQ_CITATION_RE = re.compile(
    r"""
    ^\s*
    (?P<name>[a-z][a-z0-9_]+)            # canonical_name
    \s*
    (?:\(period=(?P<period>t|t-1|t_minus_1)\))?
    .*$                                   # tolerates trailing "# comment" narration
    """,
    re.VERBOSE,
)


def _parse_required_citation(raw: str) -> tuple[str, str] | None:
    """Parse ``"revenue (period=t)"`` → ``("revenue", "t")``. Return ``None`` on junk."""
    m = _REQ_CITATION_RE.match(raw)
    if not m:
        return None
    name = m.group("name")
    period = m.group("period") or "t"
    if period == "t_minus_1":
        period = "t-1"
    return (name, period)


def _find_line_item(
    statements: list[CanonicalStatement], canonical_name: str
) -> CanonicalLineItem | None:
    for s in statements:
        for li in s.line_items:
            if li.name == canonical_name:
                return li
    return None


# ---------------------------------------------------------------------------
# Exogenous-input citation builder (used by compute_altman_z_score skill).
# ---------------------------------------------------------------------------


def build_market_data_citation(
    *,
    cik: str,
    fiscal_year_end: date,
    fixture_excerpt: str,
    market_value_of_equity: float,
) -> Citation:
    """Build a :class:`Citation` for a market-data-fixture entry.

    The X4 numerator (market value of equity) does not live in the
    canonical statements; it lives in ``data/market_data/equity_values.yaml``.
    We still want a resolvable citation so the citation auditor can
    round-trip back to the fixture row.

    The ``doc_id`` is the literal ``"market_data/equity_values"`` string;
    the locator is ``"<doc_id>::market_data::market_value_of_equity_<cik>_<fye>"``.
    """
    doc_id = "market_data/equity_values"
    line_item = f"market_value_of_equity_{cik}_{fiscal_year_end.isoformat()}"
    locator = build_locator(doc_id, "market_data", line_item)
    return Citation(
        doc_id=doc_id,
        statement_role=None,
        locator=locator,
        excerpt_hash=hash_excerpt(fixture_excerpt),
        value=float(market_value_of_equity),
        retrieved_at=datetime.now(timezone.utc),
    )


__all__ = [
    "BandMatch",
    "ComponentInterpretation",
    "apply_component_rules",
    "build_market_data_citation",
]
