"""compute_business_complexity_signals — Bernard, Cade, Connors &
de Kok (2025) Section 4 / Table 3 Panel a determinants.

Pure arithmetic over canonical statements (year t and year t-1).
Returns three firm-year signals (size by revenue, revenue stability
year-over-year, corporate-overhead intensity via SG&A / Revenue)
plus a composite score in [0, 1] using paper-derived weights from
Table 3 Panel a column 1 |t-statistics|. NO LLM, NO stochasticity:
identical inputs produce identical outputs.

Why these three signals (and not six — the paper has six)
---------------------------------------------------------
Bernard et al. (2025) Section 4 / Table 3 Panel a regresses
information-acquisition intensity on six store-level regressors:

    Average sales        t ≈ +3.0   (size)
    Sales volatility     t ≈ -2.8   (sign-reversed → stability)
    Average category HHI t ≈ -1.1   (not significant)
    Sells medical        t ≈ -5.1   (industry control, no analog)
    Single store         t ≈ -3.7   (sign-reversed → complexity)
    Parent # of states   t ≈ -1.1   (not significant on email extensive margin)
    Late joiner          t ≈ -5.9   (sample-period control, no analog)
    Early leaver         t ≈ -1.4   (sample-period control, no analog)

We ship the three statistically-significant generalisable
determinants: Average sales (size), Sales volatility (stability,
sign-reversed), Single store (complexity, proxied via SG&A /
Revenue). The weights of the three kept signals are normalised
from their Table 3 Panel a col 1 |t-statistics| to sum to 1.0. See
manifest implementation_decisions[1] for the dropped-signal
documentation and decisions[2]-[6] for the proxy constructions.

Composite shape
---------------

    business_complexity =
          w_size       · I[revenue_t >= $1B]                                    (size)
        + w_stability  · I[|Revenue_t − Revenue_{t-1}| / Revenue_{t-1} <= 0.10] (stability; sign-reversed)
        + w_complexity · I[SG&A_t / Revenue_t >= 0.15]                          (complexity; sign-reversed via proxy)

with weights:

    w_size       = 3.0 / 9.5 = 0.3158
    w_stability  = 2.8 / 9.5 = 0.2947
    w_complexity = 3.7 / 9.5 = 0.3895

Numerator values come from Table 3 Panel a col 1 |t-statistics| for
each kept signal; the denominator is their sum.

Sign-reversal semantics
-----------------------
Two of three paper coefficients are NEGATIVE (sales volatility,
single store). We keep the composite uniformly positive ("higher
score = more monitoring demand") by flipping the indicator
definitions rather than negating the weights:

- Stability: paper's I[volatility > threshold] becomes our
  I[|ΔRev / Rev_{t-1}| <= 0.10] — "stable" firm fires.
- Complexity: paper's I[single_store = 1] (which negatively
  predicts monitoring) is replaced by I[SG&A / Rev >= 0.15] —
  "high-overhead" firm fires (the opposite of single-store).

Indeterminate semantics
-----------------------
- When revenue_t is null, all three signals are unevaluable → score
  null, flag "indeterminate".
- When revenue_t is populated but stability can't compute (no
  prior-year filing or zero prior revenue), stability_fired is null
  and treated as "not fired" in the sum. Same conservative
  under-count as compute_context_importance_signals.
- When revenue_t is populated but SG&A line item is missing,
  complexity_fired is null and treated as "not fired."
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import find_filing, find_prior_year_filing
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement


# ---------------------------------------------------------------------------
# Paper-derived weights (Bernard et al. 2025 Table 3 Panel a col 1
# absolute t-statistics). Normalised across the three kept signals
# (three Table-3 regressors dropped per implementation_decisions[1]).
# ---------------------------------------------------------------------------

_PAPER_ABS_T_STATS: dict[str, float] = {
    "size": 3.0,
    "stability": 2.8,
    "complexity": 3.7,
}

# Sum 9.5; weights computed at module-import time so they are visible
# in the output and reproducible by a caller eyeballing the manifest.
_WEIGHT_DENOMINATOR: float = sum(_PAPER_ABS_T_STATS.values())
WEIGHTS: dict[str, float] = {
    name: round(t / _WEIGHT_DENOMINATOR, 4)
    for name, t in _PAPER_ABS_T_STATS.items()
}

# Per-signal binary thresholds (practitioner defaults, see manifest
# implementation_decisions[6]). Editable in the rule template.
_SIZE_REVENUE_THRESHOLD_USD: float = 1_000_000_000.0   # $1B "large cap" cutoff.
_STABILITY_YOY_THRESHOLD: float = 0.10                 # 10% YoY revenue delta.
_COMPLEXITY_SGA_INTENSITY_THRESHOLD: float = 0.15      # 15% SG&A / Revenue.

# Composite flag bands (presentation convention, matching
# compute_context_importance_signals).
_FLAG_COMPLEX_THRESHOLD: float = 0.60
_FLAG_MODERATE_THRESHOLD: float = 0.30

# Confidence model.
_BASE_CONFIDENCE: float = 0.7  # Capped while the two proxies are active.
_PRE_IXBRL_CONFIDENCE_PENALTY: float = 0.15

_PAPER_PDF_SHA256: str = (
    "1760a4c614f6051052beff0fad61587bdd344bea700f5205e24e5142399d8290"
)


class ComputeBusinessComplexitySignals(Skill):
    id = "compute_business_complexity_signals"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])

        cur_ref = find_filing(cik, fye)
        if cur_ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fye!r}"
            )
        cur_filing_id = f"{cur_ref.cik}/{cur_ref.accession}"
        cur_stmts = build_canonical_statements(cur_filing_id)
        cur_values = _values_map(cur_stmts)

        prior_ref = find_prior_year_filing(cik, fye)
        prior_values: dict[str, float | None] | None
        prior_stmts: list[CanonicalStatement] | None
        if prior_ref is None:
            prior_values = None
            prior_stmts = None
        else:
            prior_filing_id = f"{prior_ref.cik}/{prior_ref.accession}"
            prior_stmts = build_canonical_statements(prior_filing_id)
            prior_values = _values_map(prior_stmts)

        signals = _compute_signals(
            cur_values=cur_values,
            prior_values=prior_values,
        )
        components = _compute_fired_components(signals)
        score, flag = _compute_score_and_flag(components, signals)

        warnings: list[str] = _build_warnings(
            signals=signals,
            cur_stmts=cur_stmts,
            prior_stmts=prior_stmts,
            indeterminate=(flag == "indeterminate"),
        )

        citations = _collect_citations(cur_stmts, prior_stmts, signals)

        pre_ixbrl_count = _count_pre_ixbrl_items(cur_stmts)
        if prior_stmts is not None:
            pre_ixbrl_count += _count_pre_ixbrl_items(prior_stmts)
        confidence = _compute_confidence(
            pre_ixbrl_count=pre_ixbrl_count,
            indeterminate=(flag == "indeterminate"),
        )

        return {
            "business_complexity_score": (
                round(score, 6) if score is not None else None
            ),
            "flag": flag,
            "signals": {
                "revenue_usd": _round_or_none(signals["revenue_usd"], 2),
                "yoy_revenue_change": _round_or_none(
                    signals["yoy_revenue_change"], 6
                ),
                "sga_to_revenue_ratio": _round_or_none(
                    signals["sga_to_revenue_ratio"], 6
                ),
            },
            "components": components,
            "weights": dict(WEIGHTS),
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "paper_pdf_sha256": _PAPER_PDF_SHA256,
                "cur_filing_id": cur_filing_id,
                "prior_filing_id": (
                    f"{prior_ref.cik}/{prior_ref.accession}"
                    if prior_ref is not None
                    else None
                ),
                "weight_source": (
                    "Bernard et al. (2025) Table 3 Panel a column 1 "
                    "absolute t-statistics for the three kept signals "
                    "(size, stability, complexity); normalised to sum "
                    "to 1.0 across the three. Three Table-3 regressors "
                    "dropped per manifest implementation_decisions[1]."
                ),
                "thresholds": {
                    "size_revenue_usd": _SIZE_REVENUE_THRESHOLD_USD,
                    "stability_yoy": _STABILITY_YOY_THRESHOLD,
                    "complexity_sga_intensity": (
                        _COMPLEXITY_SGA_INTENSITY_THRESHOLD
                    ),
                    "flag_complex": _FLAG_COMPLEX_THRESHOLD,
                    "flag_moderate": _FLAG_MODERATE_THRESHOLD,
                },
            },
        }


# ---------------------------------------------------------------------------
# Canonical-statement value extraction.
# ---------------------------------------------------------------------------


def _values_map(stmts: list[CanonicalStatement]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for s in stmts:
        for li in s.line_items:
            if li.value_usd is None:
                out[li.name] = None
            else:
                out[li.name] = float(
                    li.value_usd
                    if isinstance(li.value_usd, Decimal)
                    else Decimal(str(li.value_usd))
                )
    return out


# ---------------------------------------------------------------------------
# Signal computation.
# ---------------------------------------------------------------------------


def _compute_signals(
    *,
    cur_values: dict[str, float | None],
    prior_values: dict[str, float | None] | None,
) -> dict[str, float | None]:
    """Compute the three raw signals.

    Each signal is independently nullable. The composite logic decides
    what to do with nulls (revenue_usd missing → indeterminate; other
    signals missing → treat as 'not fired' conservatively).
    """
    signals: dict[str, float | None] = {
        "revenue_usd": None,
        "yoy_revenue_change": None,
        "sga_to_revenue_ratio": None,
    }

    # (1) Size input — revenue_t.
    rev_t = cur_values.get("revenue")
    if rev_t is not None and rev_t > 0:
        signals["revenue_usd"] = rev_t

    # (2) Stability input — |Revenue_t − Revenue_{t-1}| / Revenue_{t-1}.
    if prior_values is not None:
        rev_p = prior_values.get("revenue")
        if (
            rev_t is not None
            and rev_p is not None
            and rev_p > 0
        ):
            signals["yoy_revenue_change"] = abs(rev_t - rev_p) / rev_p

    # (3) Complexity input — SG&A / Revenue.
    sga_t = cur_values.get("selling_general_admin_expense")
    if (
        rev_t is not None
        and rev_t > 0
        and sga_t is not None
    ):
        signals["sga_to_revenue_ratio"] = sga_t / rev_t

    return signals


def _compute_fired_components(
    signals: dict[str, float | None],
) -> dict[str, int | None]:
    """Convert raw signals to binary fired-or-not indicators.

    Sign-reversal is embedded in the indicator definitions:
    - size fires on HIGH revenue (paper's positive coefficient).
    - stability fires on LOW volatility (paper's negative coefficient
      on volatility becomes positive on "stability" indicator).
    - complexity fires on HIGH SG&A intensity (paper's negative
      coefficient on single-store becomes positive on "corporate
      overhead" indicator; proxy-level sign reversal).
    """
    components: dict[str, int | None] = {}

    if signals["revenue_usd"] is None:
        components["size_fired"] = None
    else:
        components["size_fired"] = (
            1 if signals["revenue_usd"] >= _SIZE_REVENUE_THRESHOLD_USD else 0
        )

    if signals["yoy_revenue_change"] is None:
        components["stability_fired"] = None
    else:
        # Sign-reversed: stable firms fire (low volatility).
        components["stability_fired"] = (
            1 if signals["yoy_revenue_change"] <= _STABILITY_YOY_THRESHOLD else 0
        )

    if signals["sga_to_revenue_ratio"] is None:
        components["complexity_fired"] = None
    else:
        components["complexity_fired"] = (
            1
            if signals["sga_to_revenue_ratio"]
            >= _COMPLEXITY_SGA_INTENSITY_THRESHOLD
            else 0
        )

    return components


def _compute_score_and_flag(
    components: dict[str, int | None],
    signals: dict[str, float | None],
) -> tuple[float | None, str]:
    """Compute the weighted composite + flag.

    Indeterminate semantics: when revenue_t is missing, ALL three
    signals are unevaluable (size directly, stability via missing
    numerator, complexity via missing denominator) — we return
    (None, "indeterminate"). Otherwise, treat any individual missing
    signal as "not fired" (conservative under-count) and publish.
    """
    if signals["revenue_usd"] is None:
        return (None, "indeterminate")

    # Revenue populated → size is always non-null from here on. The
    # other two signals may still be null (no prior year or missing
    # SG&A line item); treat null as not-fired.
    contribution_size = (
        WEIGHTS["size"] * components["size_fired"]
        if components["size_fired"] is not None
        else 0.0
    )
    contribution_stability = (
        WEIGHTS["stability"] * components["stability_fired"]
        if components["stability_fired"] is not None
        else 0.0
    )
    contribution_complexity = (
        WEIGHTS["complexity"] * components["complexity_fired"]
        if components["complexity_fired"] is not None
        else 0.0
    )
    score = (
        contribution_size + contribution_stability + contribution_complexity
    )

    if score >= _FLAG_COMPLEX_THRESHOLD:
        flag = "complex_monitoring_intensive"
    elif score >= _FLAG_MODERATE_THRESHOLD:
        flag = "moderate_monitoring_intensity"
    else:
        flag = "simple_monitoring_light"
    return (score, flag)


# ---------------------------------------------------------------------------
# Warnings + citations + confidence.
# ---------------------------------------------------------------------------


def _build_warnings(
    *,
    signals: dict[str, float | None],
    cur_stmts: list[CanonicalStatement],
    prior_stmts: list[CanonicalStatement] | None,
    indeterminate: bool,
) -> list[str]:
    warnings: list[str] = []

    if signals["yoy_revenue_change"] is not None:
        warnings.append(
            "stability_two_period_proxy: the stability signal is computed "
            "as |Revenue_t − Revenue_{t-1}| / Revenue_{t-1}, a 2-period "
            "proxy for the paper's within-store daily-sales CV (Bernard "
            "et al. 2025 Table 3 Panel a row 'Sales volatility'). "
            "Coarser granularity than the paper's daily-sales volatility. "
            "See manifest implementation_decisions[5]."
        )

    if signals["sga_to_revenue_ratio"] is not None:
        warnings.append(
            "complexity_sga_proxy: the complexity signal is computed as "
            "SG&A / Revenue, a corporate-overhead-intensity proxy for the "
            "paper's Single-store chain-vs-singleton binary (Table 3 Panel "
            "a row 'Single store'). A firm with high SG&A but a single "
            "operating segment would fire complexity without matching the "
            "paper's chain concept. See manifest implementation_decisions[4]."
        )

    if signals["yoy_revenue_change"] is None and prior_stmts is None:
        warnings.append(
            "missing_prior_year: no prior-year filing in the sample; "
            "revenue-stability signal could not be evaluated."
        )

    if signals["sga_to_revenue_ratio"] is None and signals["revenue_usd"] is not None:
        warnings.append(
            "missing_sga: selling_general_admin_expense line item is "
            "not populated for this filing; complexity signal could not "
            "be evaluated."
        )

    pre_ixbrl_cur = _count_pre_ixbrl_items(cur_stmts)
    pre_ixbrl_prior = (
        _count_pre_ixbrl_items(prior_stmts) if prior_stmts is not None else 0
    )
    if pre_ixbrl_cur + pre_ixbrl_prior > 0:
        warnings.append(
            f"pre_ixbrl_manual_extraction: "
            f"{pre_ixbrl_cur + pre_ixbrl_prior} of the line items "
            "feeding this score were sourced from a hand-authored YAML "
            "fixture rather than iXBRL facts. Confidence is reduced "
            "accordingly."
        )

    if indeterminate:
        warnings.append(
            "indeterminate_score: revenue_t is missing; all three signals "
            "depend on revenue either as a threshold input or a "
            "denominator — the composite cannot be evaluated."
        )

    return warnings


_USED_CANONICAL = (
    "revenue",
    "selling_general_admin_expense",
)


def _collect_citations(
    cur_stmts: list[CanonicalStatement],
    prior_stmts: list[CanonicalStatement] | None,
    signals: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Collect citations for every canonical line item feeding the score.

    Year-t citations: revenue (always when signals are produced),
    selling_general_admin_expense (when complexity signal computes).
    Year-(t-1) citations: revenue (when stability signal computes).
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    wanted = set(_USED_CANONICAL)

    # Year-t line items.
    for s in cur_stmts:
        for li in s.line_items:
            if li.name not in wanted:
                continue
            if li.name == "selling_general_admin_expense" and (
                signals["sga_to_revenue_ratio"] is None
            ):
                # Line item exists (with null value) — don't cite.
                continue
            key = (li.citation.doc_id, li.citation.locator)
            if key in seen:
                continue
            seen.add(key)
            out.append(li.citation.model_dump(mode="json"))

    # Year-(t-1) revenue — only cited when stability signal was computed.
    if prior_stmts is not None and signals["yoy_revenue_change"] is not None:
        for s in prior_stmts:
            for li in s.line_items:
                if li.name != "revenue":
                    continue
                key = (li.citation.doc_id, li.citation.locator)
                if key in seen:
                    continue
                seen.add(key)
                out.append(li.citation.model_dump(mode="json"))

    return out


def _count_pre_ixbrl_items(stmts: list[CanonicalStatement]) -> int:
    count = 0
    for s in stmts:
        if s.data_quality_flag == "pre_ixbrl_sgml_manual_extraction":
            count += sum(
                1 for li in s.line_items if li.name in _USED_CANONICAL
            )
    return count


def _compute_confidence(*, pre_ixbrl_count: int, indeterminate: bool) -> float:
    """Compute the skill's confidence score.

    Starts at :data:`_BASE_CONFIDENCE` (0.7, capped while the stability
    and complexity proxies are active), reduced by
    :data:`_PRE_IXBRL_CONFIDENCE_PENALTY` for any pre-iXBRL filing,
    zeroed when the result is indeterminate.
    """
    if indeterminate:
        return 0.0
    c = _BASE_CONFIDENCE
    if pre_ixbrl_count > 0:
        c -= _PRE_IXBRL_CONFIDENCE_PENALTY
    if c < 0.0:
        c = 0.0
    if c > 1.0:
        c = 1.0
    return round(c, 4)


def _round_or_none(x: float | int | None, digits: int) -> float | None:
    if x is None:
        return None
    return round(float(x), digits)


# ---------------------------------------------------------------------------
# Typed errors.
# ---------------------------------------------------------------------------


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


SKILL = ComputeBusinessComplexitySignals
