"""compute_context_importance_signals — Kim & Nikolaev (2024) §5.4 partition signals.

Pure arithmetic over canonical statements (year t and year t-1) plus
the existing ``data/market_data/equity_values.yaml`` fixture. Returns
four firm-year signals (operating-loss indicator, EBIT-volatility
proxy, accruals magnitude, market-to-book extremity) plus a composite
score in [0, 1] using paper-derived weights from Table 7 Panel A
column "Earnings". NO LLM, NO stochasticity: identical inputs produce
identical outputs.

Why these four signals (and not five — the paper has five)
-----------------------------------------------------------
Kim & Nikolaev (2024) §5.4 / Table 7 Panel A partitions the sample
on five economic signals to show WHEN narrative context matters
most for interpreting numeric data:

    Loss indicator        — Hayn (1995)
    Earnings volatility   — Dichev-Tang (2009)
    Extreme accruals      — Sloan (1996)
    Market-to-book        — Beaver-Ryan (2005)
    Political risk        — Hassan et al. (2019)

We ship the first four. The fifth (political risk) requires the
Hassan-et-al firm-year text-based political risk index, which is not
in our store and is not freely reproducible from 10-K text. The
weights of the four kept signals are re-normalised from the paper's
Table 7 Panel A "Earnings" Diff column statistics so they sum to 1.0.
See manifest implementation_decisions[3] for the dropped-signal
documentation.

Composite shape
---------------

    context_importance =
          w_loss   · I[EBIT_t < 0]                                         (loss-as-EBIT proxy)
        + w_vol    · I[|EBIT_t/TA_t − EBIT_{t-1}/TA_{t-1}| ≥ 0.05]         (vol)
        + w_accr   · I[|EBIT_t − CFO_t| / TA_t ≥ 0.10]                     (Sloan accrual)
        + w_mtb    · I[MTB ≥ 5.0  OR  MTB ≤ 0.8]                           (extremity)

with weights:

    w_loss = 2.94 / 7.57 = 0.3884
    w_vol  = 1.79 / 7.57 = 0.2365
    w_accr = 1.34 / 7.57 = 0.1770
    w_mtb  = 1.50 / 7.57 = 0.1982

Numerator values come from Table 7 Panel A row "Earnings" column
"Diff" for each signal; the denominator is their sum.

The paper's Hayn-style loss indicator uses bottom-line net income,
which is NOT a canonical line item in the MVP's 16-line set. We
substitute ``EBIT < 0`` as the operating-loss proxy. Drift versus
NetIncome-loss is one-sided (EBIT-loss is a strict subset of NetIncome-
loss; firms with positive operating income but negative net income
because of non-operating items will be missed). Documented in
manifest implementation_decisions[1].

Indeterminate semantics
-----------------------
- When BOTH volatility AND mtb signals can't be computed (no prior-
  year data AND no fixture entry), the score is null and the flag is
  ``indeterminate`` — too few signals to support the composite.
- When only ONE of vol/mtb is missing, the missing signal is treated
  as ``not fired`` (a conservative under-count of context importance);
  the score still publishes, with a warning enumerating which signals
  were not evaluable.
- Loss + accruals need year-t data only (loss = EBIT_t, accruals =
  EBIT_t − CFO_t). They are computable for every filing whose EBIT
  and CFO line items are populated.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from mvp.engine.rule_executor import build_market_data_citation
from mvp.ingestion.filings_ingest import find_filing, find_prior_year_filing
from mvp.ingestion.market_data_loader import load_equity_values
from mvp.lib.errors import ErrorCategory, LibError
from mvp.skills._base import Skill
from mvp.standardize.statements import build_canonical_statements
from mvp.store.schema import CanonicalStatement


# ---------------------------------------------------------------------------
# Paper-derived weights (Kim & Nikolaev 2024 Table 7 Panel A, column
# "Earnings", row "Diff"). Re-normalised across the four kept signals
# (political risk dropped per implementation_decisions[3]).
# ---------------------------------------------------------------------------

_PAPER_DIFFS: dict[str, float] = {
    "loss": 2.94,
    "volatility": 1.79,
    "accruals": 1.34,
    "mtb": 1.50,
}

# Sum 7.57; weights computed at module-import time so they are visible
# in the output and reproducible by a caller eyeballing the manifest.
_WEIGHT_DENOMINATOR: float = sum(_PAPER_DIFFS.values())
WEIGHTS: dict[str, float] = {
    name: round(diff / _WEIGHT_DENOMINATOR, 4)
    for name, diff in _PAPER_DIFFS.items()
}

# Per-signal binary thresholds (practitioner defaults, see manifest
# implementation_decisions[4]). Editable in the rule template.
_VOLATILITY_THRESHOLD: float = 0.05  # 5pp YoY ROA swing.
_ACCRUALS_THRESHOLD: float = 0.10    # 10% of assets, Sloan 1996 decile cutoff.
_MTB_HIGH_THRESHOLD: float = 5.0     # "growth firm".
_MTB_LOW_THRESHOLD: float = 0.8      # "value / distressed".

# Composite flag bands.
_FLAG_CRITICAL_THRESHOLD: float = 0.60
_FLAG_HELPFUL_THRESHOLD: float = 0.30

# Confidence model.
_BASE_CONFIDENCE: float = 0.7  # Capped while the two proxies are active.
_PRE_IXBRL_CONFIDENCE_PENALTY: float = 0.15

_PAPER_PDF_SHA256: str = (
    "013d9bbcd45ec4636dc3427561770c6489a29aa92e1b116281206344b442f533"
)


class ComputeContextImportanceSignals(Skill):
    id = "compute_context_importance_signals"
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

        mve_entry = _load_mve_for(cik=cik, fiscal_year_end=fye)

        signals = _compute_signals(
            cur_values=cur_values,
            prior_values=prior_values,
            mve_entry=mve_entry,
        )
        components = _compute_fired_components(signals)
        score, flag = _compute_score_and_flag(components)

        warnings: list[str] = _build_warnings(
            signals=signals,
            mve_entry=mve_entry,
            cur_stmts=cur_stmts,
            prior_stmts=prior_stmts,
            indeterminate=(flag == "indeterminate"),
        )

        citations = _collect_citations(cur_stmts, prior_stmts)
        if mve_entry is not None and signals["mtb"] is not None:
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

        pre_ixbrl_count = _count_pre_ixbrl_items(cur_stmts)
        if prior_stmts is not None:
            pre_ixbrl_count += _count_pre_ixbrl_items(prior_stmts)
        confidence = _compute_confidence(
            pre_ixbrl_count=pre_ixbrl_count,
            indeterminate=(flag == "indeterminate"),
        )

        return {
            "context_importance_score": (
                round(score, 6) if score is not None else None
            ),
            "flag": flag,
            "signals": {
                "loss": signals["loss"],
                "earnings_volatility": _round_or_none(signals["volatility"], 6),
                "abs_accruals_to_assets": _round_or_none(signals["accruals"], 6),
                "mtb": _round_or_none(signals["mtb"], 6),
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
                    "Kim & Nikolaev (2024) Table 7 Panel A column "
                    "'Earnings', row 'Diff', re-normalised across 4 "
                    "kept signals (political risk dropped — see manifest "
                    "implementation_decisions[3])"
                ),
                "thresholds": {
                    "volatility": _VOLATILITY_THRESHOLD,
                    "accruals": _ACCRUALS_THRESHOLD,
                    "mtb_high": _MTB_HIGH_THRESHOLD,
                    "mtb_low": _MTB_LOW_THRESHOLD,
                    "flag_critical": _FLAG_CRITICAL_THRESHOLD,
                    "flag_helpful": _FLAG_HELPFUL_THRESHOLD,
                },
            },
        }


# ---------------------------------------------------------------------------
# Market data fixture lookup.
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
    mve_entry: _MveEntry | None,
) -> dict[str, float | int | None]:
    """Compute the four raw §5.4 signals.

    Each signal is independently nullable. The composite logic decides
    what to do with nulls (treat as 'not fired' if at least one of
    vol/mtb computes; emit indeterminate only when both fail).

    The paper's Hayn-style loss indicator uses bottom-line net income;
    we substitute EBIT (which is a canonical line item in the MVP's
    16-line set; net income is not). See manifest
    implementation_decisions[1].
    """
    signals: dict[str, float | int | None] = {
        "loss": None,
        "volatility": None,
        "accruals": None,
        "mtb": None,
    }

    # (1) Operating-loss indicator — proxy for the paper's Hayn (1995)
    # net-income-loss using EBIT. Needs year-t EBIT only.
    ebit_t = cur_values.get("ebit")
    if ebit_t is not None:
        signals["loss"] = 1 if ebit_t < 0 else 0

    # (2) ROA volatility (EBIT-based proxy for the paper's net-income
    # ROA). Needs ROA_t and ROA_{t-1}.
    if prior_values is not None:
        ta_t = cur_values.get("total_assets")
        ebit_p = prior_values.get("ebit")
        ta_p = prior_values.get("total_assets")
        if (
            ebit_t is not None
            and ta_t is not None
            and ta_t > 0
            and ebit_p is not None
            and ta_p is not None
            and ta_p > 0
        ):
            roa_t = ebit_t / ta_t
            roa_p = ebit_p / ta_p
            signals["volatility"] = abs(roa_t - roa_p)

    # (3) Accruals — Sloan (1996) shape: |EBIT − CFO| / TotalAssets.
    # Uses the reported cash_flow_from_operating_activities canonical
    # line item, NOT an indirect-method reconstruction.
    cfo_t = cur_values.get("cash_flow_from_operating_activities")
    ta_t = cur_values.get("total_assets")
    if (
        ebit_t is not None
        and cfo_t is not None
        and ta_t is not None
        and ta_t > 0
    ):
        signals["accruals"] = abs(ebit_t - cfo_t) / ta_t

    # (4) Market-to-book — needs MVE fixture entry + book equity.
    if mve_entry is not None:
        ta_t = cur_values.get("total_assets")
        tl_t = cur_values.get("total_liabilities")
        if (
            ta_t is not None
            and tl_t is not None
        ):
            book_equity = ta_t - tl_t
            if book_equity > 0:
                signals["mtb"] = mve_entry.mve / book_equity
            else:
                # Negative or zero book equity — the MTB ratio is
                # mathematically undefined / sign-flipped. We encode it
                # as the most extreme "value-destroying" case the
                # paper's MTB partition could capture: a sentinel value
                # of 0.0 fires the low-extremity band (≤ 0.8). The
                # mtb_negative_book_equity warning surfaces the
                # encoding so the caller can see the substitution.
                signals["mtb"] = 0.0

    return signals


def _compute_fired_components(
    signals: dict[str, float | int | None],
) -> dict[str, int | None]:
    """Convert raw signals to binary fired-or-not indicators."""
    components: dict[str, int | None] = {}

    components["loss_fired"] = (
        signals["loss"] if signals["loss"] is not None else None
    )

    if signals["volatility"] is None:
        components["volatility_fired"] = None
    else:
        components["volatility_fired"] = (
            1 if signals["volatility"] >= _VOLATILITY_THRESHOLD else 0
        )

    if signals["accruals"] is None:
        components["accruals_fired"] = None
    else:
        components["accruals_fired"] = (
            1 if signals["accruals"] >= _ACCRUALS_THRESHOLD else 0
        )

    if signals["mtb"] is None:
        components["mtb_fired"] = None
    else:
        mtb = signals["mtb"]
        components["mtb_fired"] = (
            1 if (mtb >= _MTB_HIGH_THRESHOLD or mtb <= _MTB_LOW_THRESHOLD) else 0
        )

    return components


def _compute_score_and_flag(
    components: dict[str, int | None],
) -> tuple[float | None, str]:
    """Compute the weighted composite + flag.

    Indeterminate semantics: when BOTH vol_fired and mtb_fired are
    null (i.e. neither could be evaluated), there is too little signal
    to support the composite — return (None, "indeterminate"). When
    only one of the two is null, treat it as not-fired (conservative)
    and proceed.
    """
    if components["volatility_fired"] is None and components["mtb_fired"] is None:
        return (None, "indeterminate")

    # Loss/accruals: if either is null we can still produce a score
    # by treating it as not-fired (same conservative direction). The
    # warning system surfaces the missing signal.
    contribution_loss = (
        WEIGHTS["loss"] * components["loss_fired"]
        if components["loss_fired"] is not None
        else 0.0
    )
    contribution_vol = (
        WEIGHTS["volatility"] * components["volatility_fired"]
        if components["volatility_fired"] is not None
        else 0.0
    )
    contribution_accr = (
        WEIGHTS["accruals"] * components["accruals_fired"]
        if components["accruals_fired"] is not None
        else 0.0
    )
    contribution_mtb = (
        WEIGHTS["mtb"] * components["mtb_fired"]
        if components["mtb_fired"] is not None
        else 0.0
    )
    score = (
        contribution_loss + contribution_vol + contribution_accr + contribution_mtb
    )

    if score >= _FLAG_CRITICAL_THRESHOLD:
        flag = "context_critical"
    elif score >= _FLAG_HELPFUL_THRESHOLD:
        flag = "context_helpful"
    else:
        flag = "context_marginal"
    return (score, flag)


# ---------------------------------------------------------------------------
# Warnings + citations + confidence.
# ---------------------------------------------------------------------------


def _build_warnings(
    *,
    signals: dict[str, float | int | None],
    mve_entry: _MveEntry | None,
    cur_stmts: list[CanonicalStatement],
    prior_stmts: list[CanonicalStatement] | None,
    indeterminate: bool,
) -> list[str]:
    warnings: list[str] = []

    if signals["loss"] is not None:
        warnings.append(
            "loss_indicator_uses_ebit_proxy: the paper's Hayn (1995) "
            "loss indicator uses bottom-line net income, which is not a "
            "canonical line item at MVP. We substitute EBIT < 0 (operating "
            "loss). Drift is one-sided — firms with positive EBIT but "
            "negative net income (large non-operating losses, write-downs) "
            "will be missed. See manifest implementation_decisions[1]."
        )

    if signals["volatility"] is not None:
        warnings.append(
            "volatility_two_period_proxy: earnings volatility is computed "
            "as |ROA_t − ROA_{t-1}| using EBIT in the numerator, a 2-period "
            "proxy for the paper's Dichev-Tang (2009) multi-year std(ROA). "
            "Coarser and noisier than the paper's construct; see manifest "
            "implementation_decisions[2]."
        )

    if signals["volatility"] is None and prior_stmts is None:
        warnings.append(
            "missing_prior_year: no prior-year filing in the sample; "
            "earnings volatility could not be evaluated."
        )

    if signals["mtb"] is None and mve_entry is None:
        warnings.append(
            "missing_market_data: no market_value_of_equity fixture entry "
            "for this issuer; MTB signal could not be evaluated."
        )

    if mve_entry is not None and signals["mtb"] == 0.0:
        # Fixture exists but book equity was non-positive — encoded as
        # 0.0 (extreme low) to surface the distress signal. The
        # warning explains the encoding so a caller doesn't read a
        # literal MTB of 0.0 as the firm being market-priced at zero.
        warnings.append(
            "mtb_negative_book_equity: book equity (TotalAssets − "
            "TotalLiabilities) is non-positive; the MTB ratio is not "
            "mathematically meaningful so we encode it as 0.0 to fire "
            "the low-extremity band. The fixture's market value of "
            "equity is non-zero — the firm is just balance-sheet-"
            "insolvent in book terms."
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
            "indeterminate_score: neither earnings volatility nor MTB "
            "could be evaluated; too few signals available to support "
            "the composite."
        )

    return warnings


_USED_CANONICAL = (
    "ebit",
    "total_assets",
    "total_liabilities",
    "cash_flow_from_operating_activities",
)


def _collect_citations(
    cur_stmts: list[CanonicalStatement],
    prior_stmts: list[CanonicalStatement] | None,
) -> list[dict[str, Any]]:
    """Collect citations for every canonical line item feeding the score.

    Both year-t and year-(t-1) line items are cited when prior_stmts is
    available — the volatility and accruals signals consume both years.
    """
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    wanted = set(_USED_CANONICAL)
    for s in cur_stmts:
        for li in s.line_items:
            if li.name not in wanted:
                continue
            key = (li.citation.doc_id, li.citation.locator)
            if key in seen:
                continue
            seen.add(key)
            out.append(li.citation.model_dump(mode="json"))
    if prior_stmts is not None:
        for s in prior_stmts:
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
    for s in stmts:
        if s.data_quality_flag == "pre_ixbrl_sgml_manual_extraction":
            count += sum(
                1 for li in s.line_items if li.name in _USED_CANONICAL
            )
    return count


def _compute_confidence(*, pre_ixbrl_count: int, indeterminate: bool) -> float:
    """Compute the skill's confidence score.

    Starts at :data:`_BASE_CONFIDENCE` (0.7, capped while the volatility
    and accruals proxies are active), reduced by
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


SKILL = ComputeContextImportanceSignals
