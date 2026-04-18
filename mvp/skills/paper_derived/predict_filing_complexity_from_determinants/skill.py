"""predict_filing_complexity_from_determinants — Bernard, Blankespoor,
de Kok & Toynbee (2025) Table 3 Column 2 determinants regression.

Paper: Bernard, D., Blankespoor, E., de Kok, T., & Toynbee, S. (December
2025). *Using GPT to measure business complexity.* Forthcoming, The
Accounting Review. SSRN 4480309. pdf_sha256
``a4e82cafd4d51cdf22ede47dd29a8294c2ecc38c7da337f7874061630a0a6564``.

The paper's **headline construct** is a fine-tuned Llama-3 8b model that
scores iXBRL footnote tags; filing-level ``Complexity = 1 − average
token confidence`` aggregated from fact level. Model weights +
pre-computed complexity scores are promised for a companion website
but were not yet available at paper-onboarding time. This skill does
NOT reproduce the Llama-3 measure.

What this skill DOES ship: **the paper's own deterministic determinants
regression from Table 3 Column 2** — the cross-sectional OLS that
predicts filing complexity from firm characteristics. The regression
is paper-exact with published coefficients:

    Complexity = α_it + 0.014·I[10K]
                + 0.012·decile_rank(Size)
                + 0.012·decile_rank(Leverage)
                + 0.005·decile_rank(BM)
                - 0.008·decile_rank(ROA)
                [+ 6 regressors dropped at MVP — see below]
                + industry_fe + yearqtr_fe + filer_status_fe

with N = 58,140 firm-quarters and R² = 0.225. α_it is absorbed by fixed
effects and not directly recoverable per filing; we anchor the output
level on the paper's Table 2 sample mean ``0.118`` so the
``predicted_complexity_level`` is interpretable as "what the paper's
regression predicts for a firm with these characteristics, relative to
the paper's sample-average filing."

Five regressors shipped (computable from MVP canonical + market fixture):

- ``10K`` — binary; every MVP sample filing is a 10-K so this always
  fires at MVP; kept so a future 10-Q ingest drops the contribution.
- ``Size`` — ``ln(total_assets)``.
- ``Leverage`` — ``long_term_debt / total_assets`` (LTD-only proxy;
  paper uses DLCQ + DLTTQ).
- ``BM`` — ``(total_assets − total_liabilities) / market_value_of_equity``.
  Market value from the ``data/market_data/equity_values.yaml`` fixture
  shared with Altman Z X4.
- ``ROA`` — ``ebit / total_assets`` (EBIT proxy for IBQ).

Six regressors DROPPED at MVP: Investment, FirmAge, Lifecycle (Intro /
Growth / Mature / Shakeout / Decline), ReturnVolatility, AnalystFollow,
Institutional. Each is documented in the rule template's
``dropped_regressors`` block with paper coefficient + t-stat + data
source requirement.

Decile ranks via piecewise-linear interpolation through the paper's
Table 2 published percentiles (P10 / P25 / Median / P75 / P90). Values
below P10 clamp to 0.0; values above P90 clamp to 1.0. The mapping is
paper-sample-anchored, not live-population; warning
``decile_estimated_from_paper_percentiles`` fires on every non-null
decile.

Indeterminate path: when ``total_assets`` is null OR
``total_liabilities`` is null, most of the 5 regressors become
unevaluable → return ``{predicted_complexity_level: null,
flag: indeterminate}``.

No LLM, no random component. Deterministic byte-identical output from
byte-identical input.
"""

from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.engine.rule_executor import build_market_data_citation
from mvp.ingestion.filings_ingest import find_filing
from mvp.ingestion.market_data_loader import load_equity_values
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement


# ---------------------------------------------------------------------------
# Paper-exact constants (Bernard et al. 2025 Table 3 Column 2 + Table 2).
# ---------------------------------------------------------------------------

# Table 3 Column 2 coefficients on the five shipped regressors (paper pp.
# 47 — numerical precision is the paper's three-decimal rounding; the
# paper prints 0.014 / 0.012 / 0.012 / 0.005 / -0.008).
COEF_10K: float = 0.014
COEF_SIZE: float = 0.012
COEF_LEVERAGE: float = 0.012
COEF_BM: float = 0.005
COEF_ROA: float = -0.008

# Table 2 sample-wide mean Complexity. Used as the baseline level anchor
# because the regression's intercept α_it is absorbed by fixed effects
# and not per-filing recoverable.
PAPER_SAMPLE_MEAN_COMPLEXITY: float = 0.118

# Table 1 Panel B: 15,865 of 58,148 filings are 10-Ks; the rest 10-Qs.
# Computed at import time so the provenance block can expose it.
PAPER_10K_RATIO: float = 15865 / 58148  # 0.2728995...

# Table 2 percentiles (P10 / P25 / Median / P75 / P90) for the four
# continuous regressors we ship. Values verbatim from the paper p. 46.
PAPER_TABLE_2_PERCENTILES: dict[str, tuple[float, float, float, float, float]] = {
    "size":     (5.002, 6.267, 7.636, 8.906, 10.128),  # ln(Total Assets)
    "leverage": (0.020, 0.081, 0.275, 0.453,  0.633),   # (DLCQ+DLTTQ)/ATQ
    "bm":       (0.055, 0.193, 0.434, 0.823,  1.264),   # book / market
    "roa":      (-0.086, -0.014, 0.003, 0.016, 0.033),  # IBQ / ATQ
}

# The decile-rank anchor values that correspond to P10 / P25 / Median /
# P75 / P90 in a panel that is decile-ranked and scaled to [0, 1].
_DECILE_ANCHORS: tuple[float, float, float, float, float] = (0.10, 0.25, 0.50, 0.75, 0.90)

# Flag-band thresholds on predicted_complexity_level — presentation
# convention anchored to Table 2's mean (0.118) and SD (0.038).
_FLAG_ELEVATED_THRESHOLD: float = 0.150
_FLAG_TYPICAL_LOWER_THRESHOLD: float = 0.100

# Confidence model.
_BASE_CONFIDENCE: float = 0.7  # Capped while the four approximations below are active.
_PRE_IXBRL_CONFIDENCE_PENALTY: float = 0.15
_MVE_ESTIMATED_PENALTY: float = 0.15

_PAPER_PDF_SHA256: str = (
    "a4e82cafd4d51cdf22ede47dd29a8294c2ecc38c7da337f7874061630a0a6564"
)


# ---------------------------------------------------------------------------
# Skill class.
# ---------------------------------------------------------------------------


class PredictFilingComplexityFromDeterminants(Skill):
    id = "predict_filing_complexity_from_determinants"
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

        # Filing type: every MVP sample filing is a 10-K. The paper's
        # determinants regression was run on 10-Ks + 10-Qs; we keep the
        # indicator explicit so a future 10-Q ingest flips to 0.
        is_10k = _detect_is_10k(cur_ref.accession)

        # Market value of equity is ONE input (BM); without it we still
        # publish a level from Size + Leverage + ROA + 10K. Missing-MVE
        # is documented in warnings below, not raised as an error.
        mve_entry = _load_mve_for(cik=cik, fiscal_year_end=fye)

        raw = _compute_raw_characteristics(
            values=values,
            mve=(mve_entry.mve if mve_entry is not None else None),
        )
        deciles = _compute_decile_ranks(raw)
        contributions = _compute_contributions(deciles, is_10k=is_10k)

        level, delta, flag = _compute_level_and_flag(
            contributions=contributions,
            raw=raw,
        )

        warnings = _build_warnings(
            raw=raw,
            mve_entry=mve_entry,
            stmts=stmts,
            is_10k=is_10k,
            indeterminate=(flag == "indeterminate"),
        )

        pre_ixbrl_count = _count_pre_ixbrl_items(stmts)
        # Only apply the MVE penalty when BM was actually consumed —
        # otherwise a fixture-flag on an unused market value doesn't
        # speak to this call's output quality.
        mve_flagged_and_used = (
            raw["bm"] is not None
            and mve_entry is not None
            and bool(mve_entry.market_cap_source or mve_entry.shares_source_flag)
        )
        confidence = _compute_confidence(
            pre_ixbrl_count=pre_ixbrl_count,
            mve_flagged=mve_flagged_and_used,
            indeterminate=(flag == "indeterminate"),
        )

        citations = _collect_citations(stmts, raw)
        if mve_entry is not None and raw["bm"] is not None:
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

        return {
            "predicted_complexity_level": (
                round(level, 6) if level is not None else None
            ),
            "predicted_complexity_delta": (
                round(delta, 6) if delta is not None else None
            ),
            "flag": flag,
            "decile_ranks": {
                "size": _round_or_none(deciles["size"], 6),
                "leverage": _round_or_none(deciles["leverage"], 6),
                "bm": _round_or_none(deciles["bm"], 6),
                "roa": _round_or_none(deciles["roa"], 6),
            },
            "raw_characteristics": {
                "is_10k": int(is_10k),
                "size_ln_total_assets": _round_or_none(raw["size"], 6),
                "leverage_debt_to_assets": _round_or_none(raw["leverage"], 6),
                "book_to_market": _round_or_none(raw["bm"], 6),
                "roa_ebit_to_assets": _round_or_none(raw["roa"], 6),
            },
            "regressor_contributions": {
                name: _round_or_none(v, 6) for name, v in contributions.items()
            },
            "paper_coefficients": {
                "10K": COEF_10K,
                "size": COEF_SIZE,
                "leverage": COEF_LEVERAGE,
                "bm": COEF_BM,
                "roa": COEF_ROA,
            },
            "paper_baseline_mean": PAPER_SAMPLE_MEAN_COMPLEXITY,
            "citations": citations,
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "paper_pdf_sha256": _PAPER_PDF_SHA256,
                "filing_id": filing_id,
                "market_data_fixture": (
                    "data/market_data/equity_values.yaml"
                    if mve_entry is not None
                    else None
                ),
                "paper_10k_ratio": round(PAPER_10K_RATIO, 6),
                "paper_sample_mean_complexity": PAPER_SAMPLE_MEAN_COMPLEXITY,
                "table_2_percentiles": {
                    name: list(pcts)
                    for name, pcts in PAPER_TABLE_2_PERCENTILES.items()
                },
                "flag_thresholds": {
                    "elevated_floor": _FLAG_ELEVATED_THRESHOLD,
                    "typical_lower": _FLAG_TYPICAL_LOWER_THRESHOLD,
                },
            },
        }


# ---------------------------------------------------------------------------
# Inputs ↦ canonical statement values.
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


def _detect_is_10k(accession: str) -> bool:
    """All MVP sample filings are 10-Ks. This helper exists so the
    ``is_10k`` attribute is not a hard-coded ``True`` in the call
    chain — a future 10-Q ingest will flip it via the filing registry
    metadata. For MVP we hard-return ``True`` because every
    ``find_filing(...)`` result in the sample corpus is a 10-K (see
    ``mvp.ingestion.filings_ingest`` catalogue), and the test suite
    pins this expectation in the paper-replication test.
    """
    _ = accession  # retained for a future 10-Q-aware dispatch.
    return True


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
# Raw characteristics + decile ranks.
# ---------------------------------------------------------------------------


def _compute_raw_characteristics(
    *, values: dict[str, float | None], mve: float | None
) -> dict[str, float | None]:
    """Return the four raw continuous characteristics needed by the regression.

    Mirrors paper Appendix A for each regressor:

    - Size = ln(ATQ).
    - Leverage = (DLCQ + DLTTQ) / ATQ; MVP uses LTD / TA only (LTD-only
      proxy, documented in manifest implementation_decisions[4]).
    - BM = book_value_equity / market_value_equity. Book equity =
      TA − TL (paper's default when preferred-equity breakouts aren't
      available). Negative book equity → returns None so decile-rank
      doesn't extrapolate a signed value.
    - ROA = IBQ / ATQ; MVP uses EBIT / TA (EBIT-proxy documented in
      manifest implementation_decisions[3]).
    """
    ta = values.get("total_assets")
    tl = values.get("total_liabilities")
    ltd = values.get("long_term_debt")
    ebit = values.get("ebit")

    out: dict[str, float | None] = {
        "size": None,
        "leverage": None,
        "bm": None,
        "roa": None,
    }

    if ta is not None and ta > 0:
        out["size"] = math.log(ta)
        if ltd is not None and ltd >= 0:
            out["leverage"] = ltd / ta
        if ebit is not None:
            out["roa"] = ebit / ta
        if tl is not None and mve is not None and mve > 0:
            book = ta - tl
            if book > 0:
                # Negative book equity (Carvana FY2022 — total_liabilities >
                # total_assets) is a degenerate input to BM = book/market;
                # we return None rather than feed a negative value into
                # the paper's positive-domain percentile interpolation.
                out["bm"] = book / mve

    return out


def _compute_decile_ranks(
    raw: dict[str, float | None],
) -> dict[str, float | None]:
    """Decile-rank each raw characteristic via piecewise-linear
    interpolation through the paper's Table 2 percentiles."""
    out: dict[str, float | None] = {}
    for name in ("size", "leverage", "bm", "roa"):
        v = raw[name]
        if v is None:
            out[name] = None
            continue
        out[name] = _interpolate_decile(v, PAPER_TABLE_2_PERCENTILES[name])
    return out


def _interpolate_decile(
    v: float, pcts: tuple[float, float, float, float, float]
) -> float:
    """Piecewise-linear interpolation through the five P10..P90 anchors.

    Below P10 clamps to 0.0; above P90 clamps to 1.0. Strictly
    monotonic-non-decreasing across the five anchors per Table 2.
    """
    if v <= pcts[0]:
        return 0.0
    if v >= pcts[-1]:
        return 1.0
    for i in range(len(pcts) - 1):
        lo, hi = pcts[i], pcts[i + 1]
        if lo <= v <= hi:
            frac = (v - lo) / (hi - lo) if hi > lo else 0.0
            return _DECILE_ANCHORS[i] + frac * (
                _DECILE_ANCHORS[i + 1] - _DECILE_ANCHORS[i]
            )
    return 1.0  # unreachable given the monotone anchors + clamps.


# ---------------------------------------------------------------------------
# Regressor contributions + composite level.
# ---------------------------------------------------------------------------


def _compute_contributions(
    deciles: dict[str, float | None], *, is_10k: bool
) -> dict[str, float | None]:
    """Compute each regressor's additive contribution to the
    predicted-complexity delta.

    Contributions are CENTERED on sample-mean values:
        c_10K       = 0.014 * (I[10K] - PAPER_10K_RATIO)
        c_size      = 0.012 * (decile_size - 0.5)
        c_leverage  = 0.012 * (decile_leverage - 0.5)
        c_bm        = 0.005 * (decile_bm - 0.5)
        c_roa       = -0.008 * (decile_roa - 0.5)

    Null-decile contributions are null (treated as 0.0 in the delta
    sum but surfaced in the output trace so the caller can see which
    signals did not contribute).
    """
    out: dict[str, float | None] = {}

    out["10K"] = COEF_10K * (int(is_10k) - PAPER_10K_RATIO)

    for name, coef in (
        ("size", COEF_SIZE),
        ("leverage", COEF_LEVERAGE),
        ("bm", COEF_BM),
        ("roa", COEF_ROA),
    ):
        d = deciles[name]
        out[name] = None if d is None else coef * (d - 0.5)

    return out


def _compute_level_and_flag(
    *,
    contributions: dict[str, float | None],
    raw: dict[str, float | None],
) -> tuple[float | None, float | None, str]:
    """Sum contributions and derive the flag.

    Indeterminate semantics: when Size decile is null (i.e.
    ``total_assets`` missing), all five regressors degrade — the
    10K indicator alone is not enough signal to publish a level.
    Single-regressor nulls (BM when MVE unavailable, ROA when EBIT
    null) zero that contribution and emit a targeted warning.
    """
    if raw["size"] is None:
        return (None, None, "indeterminate")

    delta = 0.0
    for _, v in contributions.items():
        if v is not None:
            delta += v

    level = PAPER_SAMPLE_MEAN_COMPLEXITY + delta
    flag = _derive_flag(level)
    return (level, delta, flag)


def _derive_flag(level: float) -> str:
    if level >= _FLAG_ELEVATED_THRESHOLD:
        return "predicted_elevated_complexity"
    if level >= _FLAG_TYPICAL_LOWER_THRESHOLD:
        return "predicted_typical_complexity"
    return "predicted_reduced_complexity"


# ---------------------------------------------------------------------------
# Warnings + citations + confidence.
# ---------------------------------------------------------------------------


_USED_CANONICAL = (
    "total_assets",
    "total_liabilities",
    "long_term_debt",
    "ebit",
)


def _build_warnings(
    *,
    raw: dict[str, float | None],
    mve_entry: _MveEntry | None,
    stmts: list[CanonicalStatement],
    is_10k: bool,
    indeterminate: bool,
) -> list[str]:
    warnings: list[str] = []

    # ALWAYS emit this on every non-null call — makes the headline-ML
    # deferral explicit per manifest implementation_decisions[0].
    if not indeterminate:
        warnings.append(
            "headline_ml_measure_not_implemented: the paper's headline "
            "Llama-3 8b complexity measure is not reproduced. We ship the "
            "paper's own Table 3 Column 2 determinants regression, which "
            "predicts the Llama-3 complexity score from firm characteristics. "
            "Bernard et al. (2025) Table 3 Col 2 reports R² = 0.225, so the "
            "regression explains ~23% of Llama-3-complexity variance — "
            "per-firm residuals can be substantial. See manifest "
            "implementation_decisions[0] and limitations[0]."
        )
        warnings.append(
            "decile_estimated_from_paper_percentiles: decile ranks are "
            "estimated via piecewise-linear interpolation through the "
            "paper's Table 2 percentiles (P10/P25/Median/P75/P90), not "
            "computed on a live panel. Values outside the P10..P90 band "
            "clamp to 0.0 / 1.0. See manifest implementation_decisions[2]."
        )
        if raw["roa"] is not None:
            warnings.append(
                "roa_ebit_proxy: ROA is computed as EBIT / total_assets. "
                "The paper's ROA uses IBQ (Compustat income before "
                "extraordinary items) / ATQ. Difference is non-operating "
                "items + taxes; typically small but non-zero. See manifest "
                "implementation_decisions[3]."
            )
        if raw["leverage"] is not None:
            warnings.append(
                "leverage_long_term_only: Leverage is computed as "
                "long_term_debt / total_assets. The paper's Leverage is "
                "(DLCQ + DLTTQ) / ATQ; MVP canonical does not cleanly "
                "separate short-term debt from current_liabilities. See "
                "manifest implementation_decisions[4]."
            )

    if not is_10k:
        # Defensive — MVP corpus is 10-K-only at Paper 5 onboarding time,
        # but the skill would run if an operator ingested a 10-Q.
        warnings.append(
            "filing_is_not_10k: 10K indicator set to 0; the 0.014 "
            "coefficient contribution flips from positive to negative."
        )

    if raw["bm"] is None and mve_entry is not None and not indeterminate:
        warnings.append(
            "bm_negative_book_equity_or_missing_total_liabilities: BM "
            "could not be computed (book value of equity non-positive, OR "
            "total_liabilities not populated). BM's contribution is "
            "treated as 0.0 in the level sum. Carvana FY2022 is the "
            "canonical example — total_liabilities > total_assets."
        )

    if mve_entry is None and not indeterminate:
        warnings.append(
            "missing_market_data: no market_value_of_equity fixture entry "
            "for this (cik, fiscal_year_end); BM cannot be computed. BM "
            "contribution treated as 0.0."
        )

    if raw["roa"] is None and not indeterminate:
        warnings.append(
            "missing_roa: ebit canonical line item is null; ROA cannot be "
            "computed. ROA contribution treated as 0.0. Carvana FY2022 "
            "is the canonical example."
        )

    if raw["leverage"] is None and not indeterminate:
        warnings.append(
            "missing_leverage: long_term_debt canonical line item is "
            "null; Leverage cannot be computed. Leverage contribution "
            "treated as 0.0."
        )

    if mve_entry is not None and mve_entry.market_cap_source == (
        "estimated_from_aggregated_market_cap"
    ):
        warnings.append(
            "market_value_estimated: market_value_of_equity_usd is an "
            "estimated aggregate (source="
            f"{mve_entry.market_cap_source!r}) rather than a closing-price "
            "× share-count product. BM should be treated as a noisier "
            "input for this filing (same flag applied by Altman Z X4)."
        )
    if mve_entry is not None and mve_entry.shares_source_flag:
        warnings.append(
            f"shares_source_flag: {mve_entry.shares_source_flag} — the "
            "share count is not dated exactly on the fiscal-year-end "
            "(cover-page post-FYE or similar). BM is approximate."
        )

    pre_ixbrl_count = _count_pre_ixbrl_items(stmts)
    if pre_ixbrl_count > 0:
        warnings.append(
            f"pre_ixbrl_manual_extraction: {pre_ixbrl_count} of the line "
            "items feeding this score were sourced from a hand-authored "
            "YAML fixture rather than iXBRL facts. Confidence is reduced "
            "accordingly."
        )

    if indeterminate:
        warnings.append(
            "indeterminate_level: total_assets is missing; Size, "
            "Leverage, ROA, and BM all depend on it. The regression "
            "cannot be evaluated."
        )

    return warnings


def _collect_citations(
    stmts: list[CanonicalStatement],
    raw: dict[str, float | None],
) -> list[dict[str, Any]]:
    """Collect citations for every canonical line item feeding the
    level. Cite eagerly — the excerpt_hash is a meaningful provenance
    record even for a null-valued line item (e.g. Carvana's missing
    EBIT)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    wanted = set(_USED_CANONICAL)

    # Total-liabilities is only load-bearing for BM; skip citing it if
    # BM couldn't compute to keep the citation set minimal.
    if raw["bm"] is None:
        wanted = wanted - {"total_liabilities"}

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
    count = 0
    wanted = set(_USED_CANONICAL)
    for s in stmts:
        if s.data_quality_flag != "pre_ixbrl_sgml_manual_extraction":
            continue
        for li in s.line_items:
            if li.name in wanted and li.value_usd is not None:
                count += 1
    return count


def _compute_confidence(
    *,
    pre_ixbrl_count: int,
    mve_flagged: bool,
    indeterminate: bool,
) -> float:
    """Compute the skill's confidence score.

    Cap at :data:`_BASE_CONFIDENCE` (0.7) while the headline-ML
    deferral, ROA-EBIT proxy, LTD-only leverage proxy, and
    decile-from-Table-2-percentiles approximations are all active.
    Additional penalties:

    - ``−0.15`` when at least one consumed line item came from a
      pre-iXBRL manual-extraction fixture.
    - ``−0.15`` when the market-value-of-equity fixture entry is
      flagged (``estimated_from_aggregated_market_cap`` or
      ``shares_source_flag`` non-null — matches Altman Z's
      confidence model).
    - Clamped to 0.0 when the flag is ``indeterminate``.
    """
    if indeterminate:
        return 0.0
    c = _BASE_CONFIDENCE
    if pre_ixbrl_count > 0:
        c -= _PRE_IXBRL_CONFIDENCE_PENALTY
    if mve_flagged:
        c -= _MVE_ESTIMATED_PENALTY
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


SKILL = PredictFilingComplexityFromDeterminants
