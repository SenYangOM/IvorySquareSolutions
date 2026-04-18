"""compute_beneish_m_score — Beneish (1999) eight-component discriminant.

Pure arithmetic over canonical statements for year t and year t-1.
NO LLM, NO stochasticity: identical inputs produce identical outputs.
The per-component interpretation text lives in Phase 3's rule
template; this skill emits only scalar component values + the composite
M-score + flag. The L2 ``interpret_m_score_components`` skill turns the
components into natural-language findings.

Coefficients (Beneish 1999 Table 3, Panel A, unweighted probit):

    M = −4.840
        + 0.920 · DSRI
        + 0.528 · GMI
        + 0.404 · AQI
        + 0.892 · SGI
        + 0.115 · DEPI
        − 0.172 · SGAI
        + 4.679 · TATA
        − 0.327 · LVGI

Threshold: M > −1.78 ⇒ manipulator_likely (Beneish 1999 p. 16, 20:1–30:1
cost-ratio regime).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import find_filing, find_prior_year_filing
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement


# Beneish (1999) coefficients — paper-exact, see manifest.
_INTERCEPT = -4.840
_COEF = {
    "DSRI": 0.920,
    "GMI": 0.528,
    "AQI": 0.404,
    "SGI": 0.892,
    "DEPI": 0.115,
    "SGAI": -0.172,
    "TATA": 4.679,
    "LVGI": -0.327,
}
_THRESHOLD = -1.78


class ComputeBeneishMScore(Skill):
    id = "compute_beneish_m_score"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])

        cur_ref = find_filing(cik, fye)
        if cur_ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fye!r}"
            )
        prior_ref = find_prior_year_filing(cik, fye)
        if prior_ref is None:
            raise _MissingPriorYear(
                f"no prior-year sample filing for cik={cik!r} "
                f"(year t fiscal_year_end={fye!r})"
            )

        cur_filing_id = f"{cur_ref.cik}/{cur_ref.accession}"
        prior_filing_id = f"{prior_ref.cik}/{prior_ref.accession}"
        cur_stmts = build_canonical_statements(cur_filing_id)
        prior_stmts = build_canonical_statements(prior_filing_id)

        # Flat value dicts keyed by canonical name.
        cur_values = _values_map(cur_stmts)
        prior_values = _values_map(prior_stmts)

        components, missing = _compute_components(cur_values, prior_values)
        # TATA approximation — warn on every call that completes.
        warnings: list[str] = []
        tata_approximation_applied = False
        if components.get("TATA") is not None:
            warnings.append(
                "tata_approximation: TATA was computed from (ΔCA − ΔCL − D&A) / TA_t. "
                "The paper's full definition additionally subtracts ΔCash, ΔCurrent "
                "Maturities of LTD, and ΔIncome Tax Payable; these are not broken out "
                "as canonical line items at MVP. The approximation drops terms that "
                "are typically small for the 5 sample issuers."
            )
            tata_approximation_applied = True

        pre_ixbrl_count = _count_pre_ixbrl_items(cur_stmts) + _count_pre_ixbrl_items(prior_stmts)
        if pre_ixbrl_count > 0:
            warnings.append(
                f"pre_ixbrl_manual_extraction: {pre_ixbrl_count} of the line items "
                "feeding this score were sourced from a hand-authored YAML fixture "
                "rather than iXBRL facts. Confidence is reduced accordingly."
            )

        flag, m_score = _compute_flag(components, missing, warnings)

        citations = _collect_citations(cur_stmts, prior_stmts)

        confidence = _compute_confidence(
            pre_ixbrl_count=pre_ixbrl_count,
            tata_approx=tata_approximation_applied,
            flag=flag,
        )

        return {
            "m_score": m_score,
            "flag": flag,
            "components": components,
            "citations": [c.model_dump(mode="json") for c in citations],
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "threshold": _THRESHOLD,
                "coefficients": dict(_COEF),
                "intercept": _INTERCEPT,
                "paper_pdf_sha256": "78b2f0143770c9c06871ba8e8d8fb764fc95a4dd379ae37e1c301d16c42faffe",
                "cur_filing_id": cur_filing_id,
                "prior_filing_id": prior_filing_id,
            },
        }


# ---------------------------------------------------------------------------
# Component arithmetic.
# ---------------------------------------------------------------------------


def _values_map(stmts: list[CanonicalStatement]) -> dict[str, float | None]:
    """Return ``{canonical_name: float_or_None}`` flattened across the three statements."""
    out: dict[str, float | None] = {}
    for s in stmts:
        for li in s.line_items:
            v: float | None
            if li.value_usd is None:
                v = None
            else:
                # Decimal → float; the precision loss is <1e-15 relative
                # at the dollar magnitudes in scope and well below the
                # ±0.05 paper-replication tolerance.
                v = float(li.value_usd if isinstance(li.value_usd, Decimal) else Decimal(str(li.value_usd)))
            out[li.name] = v
    return out


def _compute_components(
    t: dict[str, float | None],
    p: dict[str, float | None],
) -> tuple[dict[str, float | None], list[str]]:
    """Compute the 8 Beneish components. ``t`` is year t, ``p`` year t-1.

    Returns ``(components, missing_reasons)`` where missing_reasons is a
    human-readable list of per-component gap explanations.
    """
    missing: list[str] = []
    out: dict[str, float | None] = {}

    def _req(d: dict[str, float | None], name: str) -> float | None:
        return d.get(name)

    rev_t = _req(t, "revenue")
    rev_p = _req(p, "revenue")
    ar_t = _req(t, "trade_receivables_net")
    ar_p = _req(p, "trade_receivables_net")
    cogs_t = _req(t, "cost_of_goods_sold")
    cogs_p = _req(p, "cost_of_goods_sold")
    ca_t = _req(t, "current_assets")
    ca_p = _req(p, "current_assets")
    ppe_t = _req(t, "property_plant_equipment_net")
    ppe_p = _req(p, "property_plant_equipment_net")
    ta_t = _req(t, "total_assets")
    ta_p = _req(p, "total_assets")
    da_t = _req(t, "depreciation_and_amortization")
    da_p = _req(p, "depreciation_and_amortization")
    sga_t = _req(t, "selling_general_admin_expense")
    sga_p = _req(p, "selling_general_admin_expense")
    ltd_t = _req(t, "long_term_debt")
    ltd_p = _req(p, "long_term_debt")
    cl_t = _req(t, "current_liabilities")
    cl_p = _req(p, "current_liabilities")

    # DSRI = (AR_t / Rev_t) / (AR_{t-1} / Rev_{t-1})
    if _all_positive(ar_t, rev_t, ar_p, rev_p):
        out["DSRI"] = (ar_t / rev_t) / (ar_p / rev_p)  # type: ignore[operator]
    else:
        out["DSRI"] = None
        missing.append(
            f"DSRI: inputs missing ("
            f"{_label_missing({'trade_receivables_net_t':ar_t,'revenue_t':rev_t,'trade_receivables_net_{t-1}':ar_p,'revenue_{t-1}':rev_p})}"
            ")"
        )

    # GMI = GM_{t-1} / GM_t
    if _all_positive(rev_t, rev_p) and cogs_t is not None and cogs_p is not None:
        gm_t = (rev_t - cogs_t) / rev_t  # type: ignore[operator]
        gm_p = (rev_p - cogs_p) / rev_p  # type: ignore[operator]
        if gm_t != 0:
            out["GMI"] = gm_p / gm_t
        else:
            out["GMI"] = None
            missing.append("GMI: gross margin year t is zero")
    else:
        out["GMI"] = None
        missing.append(
            f"GMI: inputs missing ("
            f"{_label_missing({'revenue_t':rev_t,'revenue_{t-1}':rev_p,'cost_of_goods_sold_t':cogs_t,'cost_of_goods_sold_{t-1}':cogs_p})}"
            ")"
        )

    # AQI = (1 - (CA_t+PPE_t)/TA_t) / (1 - (CA_{t-1}+PPE_{t-1})/TA_{t-1})
    if _all_positive(ta_t, ta_p) and all(
        v is not None for v in (ca_t, ppe_t, ca_p, ppe_p)
    ):
        inner_t = 1 - (ca_t + ppe_t) / ta_t  # type: ignore[operator]
        inner_p = 1 - (ca_p + ppe_p) / ta_p  # type: ignore[operator]
        if inner_p != 0:
            out["AQI"] = inner_t / inner_p
        else:
            out["AQI"] = None
            missing.append("AQI: denominator year t-1 is zero")
    else:
        out["AQI"] = None
        missing.append(
            f"AQI: inputs missing ("
            f"{_label_missing({'current_assets_t':ca_t,'current_assets_{t-1}':ca_p,'property_plant_equipment_net_t':ppe_t,'property_plant_equipment_net_{t-1}':ppe_p,'total_assets_t':ta_t,'total_assets_{t-1}':ta_p})}"
            ")"
        )

    # SGI = Rev_t / Rev_{t-1}
    if _all_positive(rev_t, rev_p):
        out["SGI"] = rev_t / rev_p  # type: ignore[operator]
    else:
        out["SGI"] = None
        missing.append("SGI: revenue inputs missing or zero")

    # DEPI = (D&A_{t-1}/(D&A_{t-1}+PPE_{t-1})) / (D&A_t/(D&A_t+PPE_t))
    if (
        da_t is not None and da_p is not None and ppe_t is not None and ppe_p is not None
        and (da_t + ppe_t) > 0 and (da_p + ppe_p) > 0
    ):
        rate_p = da_p / (da_p + ppe_p)
        rate_t = da_t / (da_t + ppe_t)
        if rate_t != 0:
            out["DEPI"] = rate_p / rate_t
        else:
            out["DEPI"] = None
            missing.append("DEPI: current-year depreciation rate is zero")
    else:
        out["DEPI"] = None
        missing.append(
            f"DEPI: inputs missing ("
            f"{_label_missing({'depreciation_and_amortization_t':da_t,'depreciation_and_amortization_{t-1}':da_p,'property_plant_equipment_net_t':ppe_t,'property_plant_equipment_net_{t-1}':ppe_p})}"
            ")"
        )

    # SGAI = (SGA_t/Rev_t) / (SGA_{t-1}/Rev_{t-1})
    if _all_positive(rev_t, rev_p) and sga_t is not None and sga_p is not None:
        out["SGAI"] = (sga_t / rev_t) / (sga_p / rev_p)
    else:
        out["SGAI"] = None
        missing.append(
            f"SGAI: inputs missing ("
            f"{_label_missing({'selling_general_admin_expense_t':sga_t,'selling_general_admin_expense_{t-1}':sga_p,'revenue_t':rev_t,'revenue_{t-1}':rev_p})}"
            ")"
        )

    # LVGI = ((LTD_t + CL_t)/TA_t) / ((LTD_{t-1} + CL_{t-1})/TA_{t-1})
    if _all_positive(ta_t, ta_p) and all(
        v is not None for v in (ltd_t, ltd_p, cl_t, cl_p)
    ):
        lev_t = (ltd_t + cl_t) / ta_t  # type: ignore[operator]
        lev_p = (ltd_p + cl_p) / ta_p  # type: ignore[operator]
        if lev_p != 0:
            out["LVGI"] = lev_t / lev_p
        else:
            out["LVGI"] = None
            missing.append("LVGI: year t-1 leverage denominator is zero")
    else:
        out["LVGI"] = None
        missing.append(
            f"LVGI: inputs missing ("
            f"{_label_missing({'long_term_debt_t':ltd_t,'long_term_debt_{t-1}':ltd_p,'current_liabilities_t':cl_t,'current_liabilities_{t-1}':cl_p,'total_assets_t':ta_t,'total_assets_{t-1}':ta_p})}"
            ")"
        )

    # TATA approximation = ((ΔCA − ΔCL) − D&A_t) / TA_t
    if (
        _all_positive(ta_t)
        and all(v is not None for v in (ca_t, ca_p, cl_t, cl_p, da_t))
    ):
        delta_ca = ca_t - ca_p  # type: ignore[operator]
        delta_cl = cl_t - cl_p  # type: ignore[operator]
        numerator = (delta_ca - delta_cl) - da_t  # type: ignore[operator]
        out["TATA"] = numerator / ta_t  # type: ignore[operator]
    else:
        out["TATA"] = None
        missing.append(
            f"TATA: inputs missing ("
            f"{_label_missing({'current_assets_t':ca_t,'current_assets_{t-1}':ca_p,'current_liabilities_t':cl_t,'current_liabilities_{t-1}':cl_p,'depreciation_and_amortization_t':da_t,'total_assets_t':ta_t})}"
            ")"
        )

    return out, missing


def _all_positive(*xs: float | None) -> bool:
    return all(x is not None and x != 0 for x in xs)


def _label_missing(named: dict[str, float | None]) -> str:
    return ", ".join(k for k, v in named.items() if v is None or v == 0)


# ---------------------------------------------------------------------------
# Flag + confidence.
# ---------------------------------------------------------------------------


def _compute_flag(
    components: dict[str, float | None],
    missing: list[str],
    warnings: list[str],
) -> tuple[str, float | None]:
    if any(v is None for v in components.values()):
        warnings.extend(missing)
        return ("indeterminate", None)
    m = _INTERCEPT
    for name, v in components.items():
        m += _COEF[name] * v  # type: ignore[operator]
    flag = "manipulator_likely" if m > _THRESHOLD else "manipulator_unlikely"
    # Round the score to 4 dp for stable output; arithmetic is done in
    # float64 which gives us >>4 dp of precision.
    m_rounded = round(m, 6)
    return (flag, m_rounded)


def _count_pre_ixbrl_items(stmts: list[CanonicalStatement]) -> int:
    n = 0
    for s in stmts:
        if s.data_quality_flag != "pre_ixbrl_sgml_manual_extraction":
            continue
        for li in s.line_items:
            if li.value_usd is not None:
                n += 1
    return n


def _compute_confidence(
    *, pre_ixbrl_count: int, tata_approx: bool, flag: str
) -> float:
    if flag == "indeterminate":
        return 0.0
    c = 1.0
    c -= 0.1 * pre_ixbrl_count
    if tata_approx:
        c -= 0.15
    if c < 0.0:
        c = 0.0
    if c > 1.0:
        c = 1.0
    return round(c, 4)


def _collect_citations(
    cur_stmts: list[CanonicalStatement],
    prior_stmts: list[CanonicalStatement],
):
    seen: set[tuple[str, str]] = set()
    out = []
    for stmts in (cur_stmts, prior_stmts):
        for s in stmts:
            for li in s.line_items:
                if li.value_usd is None:
                    # Only cite present values; a null line item's
                    # sentinel-hash citation is not useful here.
                    continue
                key = (li.citation.doc_id, li.citation.locator)
                if key in seen:
                    continue
                seen.add(key)
                out.append(li.citation)
    return out


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


SKILL = ComputeBeneishMScore
