"""compute_altman_z_score — Altman (1968) five-variable bankruptcy discriminant.

Pure arithmetic over year-t canonical statements + a fiscal-year-end
market-value-of-equity fixture entry. NO LLM, NO stochasticity.

Coefficients (Altman 1968 Equation I, paper-exact):

    Z = 0.012·X1 + 0.014·X2 + 0.033·X3 + 0.006·X4 + 0.999·X5

with X1-X4 entered as **percentages** and X5 as a ratio (this is how
Equation I is printed in the 1968 paper). The paper's zones:

- Z > 2.99  → safe
- 1.81 <= Z <= 2.99 → grey_zone
- Z < 1.81  → distress

X5's coefficient is 0.999 — NOT the rounded 1.0 some textbooks use.
See ``rules/templates/z_score_components.yaml`` and this skill's
README for the paper citation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from mvp.engine.rule_executor import build_market_data_citation
from mvp.ingestion.filings_ingest import find_filing
from mvp.ingestion.market_data_loader import load_equity_values
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement


_MVP_ROOT = Path(__file__).resolve().parents[3]
_RULE_TEMPLATE_PATH = _MVP_ROOT / "rules" / "templates" / "z_score_components.yaml"


# Altman (1968) Equation I coefficients — paper-exact.
_COEF = {
    "X1": 0.012,
    "X2": 0.014,
    "X3": 0.033,
    "X4": 0.006,
    "X5": 0.999,
}


class ComputeAltmanZScore(Skill):
    id = "compute_altman_z_score"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])

        cur_ref = find_filing(cik, fye)
        if cur_ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fye!r}"
            )
        filing_id = f"{cur_ref.cik}/{cur_ref.accession}"
        stmts = build_canonical_statements(filing_id)
        values = _values_map(stmts)

        mve_entry = _load_mve_for(cik=cik, fiscal_year_end=fye)
        if mve_entry is None:
            raise _MissingMarketData(
                f"no market_value_of_equity fixture entry for cik={cik!r} "
                f"fiscal_year_end={fye!r}; add it to data/market_data/equity_values.yaml"
            )

        components, missing = _compute_components(values, mve=mve_entry.mve)
        thresholds = _load_thresholds()
        warnings: list[str] = []

        # Market-data flag: estimated_from_aggregated_market_cap.
        if mve_entry.market_cap_source == "estimated_from_aggregated_market_cap":
            warnings.append(
                "market_value_estimated: market_value_of_equity_usd is an "
                "estimated aggregate (source="
                f"{mve_entry.market_cap_source!r}) rather than a closing-price"
                " × share-count product. X4 should be treated as a noisier "
                "input for this filing."
            )
        if mve_entry.shares_source_flag:
            warnings.append(
                f"shares_source_flag: {mve_entry.shares_source_flag} — the "
                "share count is not dated exactly on the fiscal-year-end "
                "(cover-page post-FYE or similar). X4 is approximate."
            )

        pre_ixbrl_count = _count_pre_ixbrl_items(stmts)
        if pre_ixbrl_count > 0:
            warnings.append(
                f"pre_ixbrl_manual_extraction: {pre_ixbrl_count} of the line "
                "items feeding this score were sourced from a hand-authored "
                "YAML fixture rather than iXBRL facts. Confidence is reduced "
                "accordingly."
            )

        z_score, flag = _compute_z(components, missing, thresholds, warnings)

        citations = _collect_citations(stmts, values_used=list(components.keys()))
        # X4 market-data citation (always attached when the fixture lookup
        # succeeded, even if Z is indeterminate because another component is null).
        fixture_excerpt = (
            f"cik={mve_entry.cik} fye={mve_entry.fiscal_year_end} "
            f"shares={mve_entry.shares_outstanding} "
            f"price={mve_entry.share_price_usd} "
            f"mve={mve_entry.mve}"
        )
        mve_citation = build_market_data_citation(
            cik=cik,
            fiscal_year_end=date.fromisoformat(fye),
            fixture_excerpt=fixture_excerpt,
            market_value_of_equity=mve_entry.mve,
        )
        citations.append(mve_citation.model_dump(mode="json"))

        confidence = _compute_confidence(
            pre_ixbrl_count=pre_ixbrl_count,
            mve_flagged=bool(
                mve_entry.market_cap_source or mve_entry.shares_source_flag
            ),
            flag=flag,
        )
        return {
            "z_score": z_score,
            "flag": flag,
            "components": components,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "coefficients": dict(_COEF),
                "thresholds": thresholds,
                "filing_id": filing_id,
                "market_data_fixture": "data/market_data/equity_values.yaml",
                "paper_pdf_sha256": "34ba13a102ee4f1767762786e2720e9c6211e4d3d9252fb45856ca45cb21dd99",
            },
        }


# ---------------------------------------------------------------------------
# Market-data loader helper.
# ---------------------------------------------------------------------------


class _MveEntry:
    __slots__ = (
        "cik",
        "fiscal_year_end",
        "shares_outstanding",
        "share_price_usd",
        "mve",
        "market_cap_source",
        "shares_source_flag",
    )

    def __init__(
        self,
        *,
        cik: str,
        fiscal_year_end: str,
        shares_outstanding: int,
        share_price_usd: float,
        mve: float,
        market_cap_source: str | None,
        shares_source_flag: str | None,
    ) -> None:
        self.cik = cik
        self.fiscal_year_end = fiscal_year_end
        self.shares_outstanding = shares_outstanding
        self.share_price_usd = share_price_usd
        self.mve = mve
        self.market_cap_source = market_cap_source
        self.shares_source_flag = shares_source_flag


def _load_mve_for(*, cik: str, fiscal_year_end: str) -> _MveEntry | None:
    for entry in load_equity_values():
        if entry.cik == cik and entry.fiscal_year_end == fiscal_year_end:
            return _MveEntry(
                cik=entry.cik,
                fiscal_year_end=entry.fiscal_year_end,
                shares_outstanding=entry.shares_outstanding,
                share_price_usd=entry.share_price_usd,
                mve=entry.market_value_of_equity_usd,
                market_cap_source=entry.market_cap_source,
                shares_source_flag=entry.shares_source_flag,
            )
    return None


# ---------------------------------------------------------------------------
# Component arithmetic.
# ---------------------------------------------------------------------------


def _values_map(stmts: list[CanonicalStatement]) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    for s in stmts:
        for li in s.line_items:
            if li.value_usd is None:
                out[li.name] = None
            else:
                out[li.name] = float(
                    li.value_usd if isinstance(li.value_usd, Decimal) else Decimal(str(li.value_usd))
                )
    return out


def _compute_components(
    v: dict[str, float | None], *, mve: float
) -> tuple[dict[str, float | None], list[str]]:
    missing: list[str] = []
    out: dict[str, float | None] = {}

    ca = v.get("current_assets")
    cl = v.get("current_liabilities")
    ta = v.get("total_assets")
    re = v.get("retained_earnings")
    ebit = v.get("ebit")
    tl = v.get("total_liabilities")
    rev = v.get("revenue")

    # X1 = (current_assets - current_liabilities) / total_assets
    if _all_nonnull(ca, cl) and _pos(ta):
        out["X1"] = (ca - cl) / ta  # type: ignore[operator]
    else:
        out["X1"] = None
        missing.append(
            "X1: inputs missing ("
            + _label_missing(
                {"current_assets": ca, "current_liabilities": cl, "total_assets": ta}
            )
            + ")"
        )

    # X2 = retained_earnings / total_assets
    if _all_nonnull(re) and _pos(ta):
        out["X2"] = re / ta  # type: ignore[operator]
    else:
        out["X2"] = None
        missing.append(
            "X2: inputs missing ("
            + _label_missing({"retained_earnings": re, "total_assets": ta})
            + ")"
        )

    # X3 = ebit / total_assets
    if _all_nonnull(ebit) and _pos(ta):
        out["X3"] = ebit / ta  # type: ignore[operator]
    else:
        out["X3"] = None
        missing.append(
            "X3: inputs missing ("
            + _label_missing({"ebit": ebit, "total_assets": ta})
            + ")"
        )

    # X4 = market_value_of_equity / total_liabilities
    if _pos(tl) and mve > 0:
        out["X4"] = mve / tl  # type: ignore[operator]
    else:
        out["X4"] = None
        missing.append(
            "X4: inputs missing ("
            + _label_missing({"total_liabilities": tl, "market_value_of_equity": mve})
            + ")"
        )

    # X5 = revenue / total_assets
    if _all_nonnull(rev) and _pos(ta):
        out["X5"] = rev / ta  # type: ignore[operator]
    else:
        out["X5"] = None
        missing.append(
            "X5: inputs missing ("
            + _label_missing({"revenue": rev, "total_assets": ta})
            + ")"
        )

    return out, missing


def _all_nonnull(*xs: Any) -> bool:
    return all(x is not None for x in xs)


def _pos(x: float | None) -> bool:
    return x is not None and x > 0


def _label_missing(named: dict[str, Any]) -> str:
    return ", ".join(k for k, val in named.items() if val is None or val == 0)


# ---------------------------------------------------------------------------
# Z composite + flag.
# ---------------------------------------------------------------------------


def _load_thresholds() -> dict[str, float]:
    with _RULE_TEMPLATE_PATH.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    zt = raw.get("z_score_thresholds", {}) if isinstance(raw, dict) else {}
    return {
        "distress_threshold": float(zt.get("distress_threshold", 1.81)),
        "grey_zone_upper_bound": float(zt.get("grey_zone_upper_bound", 2.99)),
        "safe_threshold": float(zt.get("safe_threshold", 2.99)),
    }


def _compute_z(
    components: dict[str, float | None],
    missing: list[str],
    thresholds: dict[str, float],
    warnings: list[str],
) -> tuple[float | None, str]:
    if any(v is None for v in components.values()):
        warnings.extend(missing)
        return (None, "indeterminate")
    # Paper-exact: X1-X4 coefficients are 0.012, 0.014, 0.033, 0.006 with
    # Xi expressed as percentages (×100); X5's coefficient is 0.999 with
    # X5 as a ratio (no ×100). This yields the standard 1.81 / 2.99
    # zone cut-offs.
    x1 = components["X1"] * 100  # type: ignore[operator]
    x2 = components["X2"] * 100  # type: ignore[operator]
    x3 = components["X3"] * 100  # type: ignore[operator]
    x4 = components["X4"] * 100  # type: ignore[operator]
    x5 = components["X5"]
    z = (
        _COEF["X1"] * x1
        + _COEF["X2"] * x2
        + _COEF["X3"] * x3
        + _COEF["X4"] * x4
        + _COEF["X5"] * x5
    )
    z_rounded = round(z, 6)
    if z_rounded > thresholds["safe_threshold"]:
        flag = "safe"
    elif z_rounded < thresholds["distress_threshold"]:
        flag = "distress"
    else:
        flag = "grey_zone"
    return (z_rounded, flag)


# ---------------------------------------------------------------------------
# Citations + confidence.
# ---------------------------------------------------------------------------


_USED_CANONICAL = (
    "current_assets",
    "current_liabilities",
    "total_assets",
    "retained_earnings",
    "ebit",
    "total_liabilities",
    "revenue",
)


def _collect_citations(
    stmts: list[CanonicalStatement],
    *,
    values_used: list[str],
) -> list[dict[str, Any]]:
    """Collect citations for every canonical line item feeding the Z score.

    We cite all seven balance-sheet / income-statement items regardless of
    whether a given component is null — each line item's excerpt_hash is
    a meaningful provenance record even for a null-valued line.
    """
    _ = values_used  # retained for future filtering; currently we cite all.
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    wanted = set(_USED_CANONICAL)
    for s in stmts:
        for li in s.line_items:
            if li.name not in wanted:
                continue
            key = (li.citation.doc_id, li.citation.locator)
            if key in seen:
                continue
            seen.add(key)
            out.append(li.citation.model_dump(mode="json"))
    return out


def _count_pre_ixbrl_items(stmts: list[CanonicalStatement]) -> int:
    n = 0
    wanted = set(_USED_CANONICAL)
    for s in stmts:
        if s.data_quality_flag != "pre_ixbrl_sgml_manual_extraction":
            continue
        for li in s.line_items:
            if li.name in wanted and li.value_usd is not None:
                n += 1
    return n


def _compute_confidence(
    *, pre_ixbrl_count: int, mve_flagged: bool, flag: str
) -> float:
    if flag == "indeterminate":
        return 0.0
    c = 1.0
    c -= 0.1 * pre_ixbrl_count
    if mve_flagged:
        c -= 0.15
    if c < 0.0:
        c = 0.0
    if c > 1.0:
        c = 1.0
    return round(c, 4)


# ---------------------------------------------------------------------------
# Typed errors.
# ---------------------------------------------------------------------------


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class _MissingMarketData(LibError):
    error_code = "missing_market_data"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


SKILL = ComputeAltmanZScore
