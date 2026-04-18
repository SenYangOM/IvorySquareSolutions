# `compute_context_importance_signals`

L3 paper-derived skill that computes Kim & Nikolaev (2024)'s
[Context-Based Interpretation of Financial Information](https://doi.org/10.1111/1475-679X.12593)
§5.4 partition signals for one US-public-company 10-K filing,
bundled into a single firm-year score in `[0, 1]` and a
four-category flag (`context_critical` /`context_helpful` /
`context_marginal` / `indeterminate`).

**Quick read.** The paper asks "when does narrative MD&A context
matter most for interpreting reported numbers?" Section 5.4
partitions the sample on five economic signals (loss indicator,
earnings volatility, extreme accruals, market-to-book extremity,
political risk) and shows that the headline ANN-based contextuality
measure is materially higher whenever the firm-year is in the
"hard-to-value" cell of a partition. We ship four of those five
signals — political risk requires Hassan-et-al-2019 data we don't
have — bundled with the paper-derived weights from Table 7 Panel A
column "Earnings" Diff statistics:

```
context_importance =
      0.3884 * I[EBIT_t < 0]                                          # loss
    + 0.2365 * I[|EBIT_t/TA_t − EBIT_{t-1}/TA_{t-1}| ≥ 0.05]         # volatility
    + 0.1770 * I[|EBIT_t − CFO_t| / TA_t ≥ 0.10]                      # accruals
    + 0.1982 * I[MTB ≥ 5.0  OR  MTB ≤ 0.8]                            # MTB extremity
```

The composite is a **meta-signal**: a high `context_importance`
score means the paper predicts the MD&A SHOULD be especially
informative for this firm — not that the firm's actual MD&A
delivers. Pair with `compute_mdna_upfrontedness` for the
structure-of-narrative axis.

## Usage

CLI:

```bash
mvp run compute_context_importance_signals --cik 0000320193 --year 2023
```

Python:

```python
from mvp.skills.registry import default_registry

skill = default_registry().get("compute_context_importance_signals")
result = skill.run({
    "cik": "0001690820",  # Carvana
    "fiscal_year_end": "2022-12-31",
})
print(result["context_importance_score"], result["flag"])
```

## Inputs

| field             | type   | format                  | description                                  |
| ---               | ---    | ---                     | ---                                          |
| `cik`             | string | `^[0-9]{10}$`           | 10-digit zero-padded SEC CIK                 |
| `fiscal_year_end` | string | ISO `yyyy-mm-dd`        | Must match an ingested filing under `data/filings/` |

## Outputs

```jsonc
{
  "context_importance_score": 0.1982,        // null when flag=indeterminate
  "flag": "context_marginal",
  "signals": {
    "loss": 0,
    "earnings_volatility": 0.014402,
    "abs_accruals_to_assets": 0.010658,
    "mtb": 42.847612
  },
  "components": {                            // I[·] indicators
    "loss_fired": 0,
    "volatility_fired": 0,
    "accruals_fired": 0,
    "mtb_fired": 1
  },
  "weights": {                                // paper-derived, shown for auditability
    "loss": 0.3884, "volatility": 0.2365,
    "accruals": 0.1770, "mtb": 0.1982
  },
  "citations": [...],
  "confidence": 0.7,
  "warnings": ["loss_indicator_uses_ebit_proxy: ...", ...],
  "provenance": {...}
}
```

## What the proxies are doing

This skill is a **proxy-with-documentation** implementation, in the
same lineage as `compute_mdna_upfrontedness`. The paper's headline
construct (BERT-encoded MD&A → ANN accuracy delta) is not
reproducible — see `workshop/docs/paper_onboarding_playbook.md`
"When the unreleased ML model has NO honest proxy" callout for the
deeper lesson here.

The §5.4 partition signals ARE deterministic, but each requires
small adaptations to MVP's 16-line canonical schema:

| signal               | paper construct                                            | our implementation                                  | warning emitted                              |
| ---                  | ---                                                        | ---                                                 | ---                                          |
| Loss indicator       | `I[NetIncome_t < 0]` (Hayn 1995)                           | `I[EBIT_t < 0]` (operating-loss proxy)              | `loss_indicator_uses_ebit_proxy`             |
| Earnings volatility  | `std(NetIncome/Assets)` over 5-year rolling (Dichev-Tang)  | `|EBIT_t/TA_t − EBIT_{t-1}/TA_{t-1}|` (2-period)    | `volatility_two_period_proxy`                |
| Accruals             | `OperatingIncome_t − CashFromOps_t` (Sloan 1996)           | Reported `EBIT_t − CFO_t` (paper-faithful shape)    | (none — uses reported data)                  |
| Market-to-book       | `MVE / BookEquity` (Beaver-Ryan 2005)                      | Same; negative book equity → MTB encoded as 0.0     | `mtb_negative_book_equity` (Carvana case)    |
| Political risk       | Hassan-et-al-2019 firm-year index                          | DROPPED — data not in store                         | (documented in manifest decisions[4])        |

Confidence is capped at 0.7 while the loss-EBIT and 2-period-volatility
proxies are active. A future expansion to 17 canonical line items
(adding `net_income`) and multi-year canonical history would let us
remove both proxies and raise the cap.

## How the flag bands relate to the paper

The paper does NOT publish a composite score. Each of the five
partition signals is reported as a stand-alone "Diff" (the percentage-
point gap in contextuality between the high and low partitions). We
adopt those Diffs as relative weights in our composite, then bucket
the resulting [0, 1] score with equally-spaced cuts at 0.30 and 0.60.
The cuts are a **presentation convention**, NOT a paper threshold —
documented in `mvp/rules/templates/context_importance_signals_components.yaml`
`context_importance_bands.notes`.

A future post-MVP calibration on a wider issuer panel could replace
the presentation cuts with population-anchored quantiles (analogous
to how `compute_mdna_upfrontedness` uses Appendix D Panel A's
P25/P75 directly).

## Composability

- Pair with `compute_mdna_upfrontedness` for "should context help?"
  + "is the narrative front-loaded?" — a high context-importance +
  low Upfrontedness firm is a sharper red-flag than either alone.
- Pair with `compute_altman_z_score` for "the paper says context
  matters here, AND the firm is in the distress zone" — the
  conjunction is the natural L4 composite shape.

## See also

- `mvp/rules/templates/context_importance_signals_components.yaml` — the
  rule template (per-signal thresholds, composite bands, paper-
  weight derivation table).
- `workshop/paper_to_skill/notes/kim_2024_context_based_interpretation.md` —
  the methodologist's full notes (skill-scope decision, formulas
  identified, implementation choices, candidates for future papers).
- `workshop/docs/paper_onboarding_playbook.md` "When the unreleased
  ML model has NO honest proxy" — the new playbook callout this paper
  prompted.
