# `compute_business_complexity_signals`

L3 paper-derived skill that computes Bernard, Cade, Connors & de Kok
(2025)'s
[Descriptive evidence on small business managers' information choices](https://doi.org/10.1007/s11142-025-09885-5)
(Review of Accounting Studies) Section 4 / Table 3 Panel a
**determinants framework** for one US-public-company 10-K filing,
bundled into a single firm-year score in `[0, 1]` and a
four-category flag (`complex_monitoring_intensive` /
`moderate_monitoring_intensity` / `simple_monitoring_light` /
`indeterminate`).

**Quick read.** The paper asks "what firm characteristics predict
managerial demand for business-intelligence monitoring tools?"
Section 4 / Table 3 Panel a column 1 reports the extensive-margin
(email-opened-at-all) regression with three statistically-significant
generalisable determinants:

| Paper variable      | Paper coef | Paper \|t\| | Our analog signal                                     |
| ---                 | ---:       | ---:        | ---                                                   |
| `Average sales`     | +0.003***  | 3.0         | `I[revenue_t >= $1,000,000,000]`                      |
| `Sales volatility`  | −0.098***  | 2.8         | `I[|Revenue_t − Revenue_{t-1}|/Revenue_{t-1} <= 0.10]` |
| `Single store`      | −0.100***  | 3.7         | `I[SG&A_t / Revenue_t >= 0.15]`                       |

We port the three determinants to public-company analog signals,
bundled with the paper-derived weights from the normalised
|t-statistics|:

```
business_complexity =
      0.3158 * I[revenue_t >= $1B]                                   # size
    + 0.2947 * I[|dRevenue/Revenue_{t-1}| <= 0.10]                   # stability (sign-reversed)
    + 0.3895 * I[SG&A_t / Revenue_t >= 0.15]                         # complexity (sign-reversed via proxy)
```

The composite is a **structural-complexity meta-signal**: a high
`business_complexity` score means the paper predicts managers at this
firm's profile would exhibit the strongest demand for monitoring
tools. It is NOT a governance verdict about disclosure quality. Pair
with `compute_mdna_upfrontedness` for narrative-structure or
`compute_context_importance_signals` for narrative-context-need.

## Usage

CLI:

```bash
mvp run compute_business_complexity_signals --cik 0000320193 --year 2023
```

Python:

```python
from mvp.skills.registry import default_registry

skill = default_registry().get("compute_business_complexity_signals")
result = skill.run({
    "cik": "0001690820",  # Carvana
    "fiscal_year_end": "2022-12-31",
})
print(result["business_complexity_score"], result["flag"])
```

## Inputs

| field             | type   | format                  | description                                  |
| ---               | ---    | ---                     | ---                                          |
| `cik`             | string | `^[0-9]{10}$`           | 10-digit zero-padded SEC CIK                 |
| `fiscal_year_end` | string | ISO `yyyy-mm-dd`        | Must match an ingested filing under `data/filings/` |

## Outputs

```jsonc
{
  "business_complexity_score": 0.6105,       // null when flag=indeterminate
  "flag": "complex_monitoring_intensive",
  "signals": {
    "revenue_usd": 383285000000.0,
    "yoy_revenue_change": 0.028005,
    "sga_to_revenue_ratio": 0.065048
  },
  "components": {                            // I[·] indicators
    "size_fired": 1,
    "stability_fired": 1,
    "complexity_fired": 0
  },
  "weights": {                               // paper-derived, shown for auditability
    "size": 0.3158, "stability": 0.2947, "complexity": 0.3895
  },
  "citations": [...],
  "confidence": 0.7,
  "warnings": ["stability_two_period_proxy: ...", "complexity_sga_proxy: ...", ...],
  "provenance": {...}
}
```

## Sign-reversal semantics

Two of the three paper coefficients are NEGATIVE. To keep the
composite uniformly positive ("higher score = more monitoring
demand"), we flip the indicator definitions rather than negating
the weights:

| Paper sign             | Our indicator                              | Fires when...                     |
| ---                    | ---                                        | ---                               |
| Average sales **+**    | `I[revenue_t >= $1B]`                       | firm is LARGE                     |
| Sales volatility **−** | `I[|dRevenue/Revenue| <= 0.10]`            | firm is STABLE (low volatility)   |
| Single store **−**     | `I[SG&A / Revenue >= 0.15]`                | firm has HIGH overhead (not chain) |

The economic direction is preserved; the algebra is equivalent up to
a constant. Signed explicitly in the manifest so a reviewer doesn't
mistake this for a coefficient-sign bug. See manifest
`implementation_decisions[3]` and `[4]` for the signed-reversal
documentation.

## What the proxies are doing

This skill is a **proxy-with-documentation** implementation, in the
same lineage as `compute_mdna_upfrontedness` and
`compute_context_importance_signals`. The paper's headline test is
the Section-5 hedonic-asymmetry finding — which we explicitly do NOT
implement because it requires daily email-open tracking logs that
have no public-company analog. The Section-4 determinants framework
IS deterministic, but each determinant requires adaptations to
public-firm scale:

| Signal         | Paper construct                                            | Our implementation                                   | Warning emitted                  |
| ---            | ---                                                        | ---                                                  | ---                              |
| Size           | log(Average daily sales), continuous linear                | `I[revenue_t >= $1B]`, binary                        | (none — proxy is a discretisation) |
| Stability      | std(daily_sales) / mean(daily_sales) within-store CV       | `I[|dRev/Rev_{t-1}| <= 0.10]`, 2-period YoY proxy    | `stability_two_period_proxy`     |
| Complexity     | `I[Single store = 1]` (chain vs singleton)                 | `I[SG&A_t / Revenue_t >= 0.15]`, overhead proxy      | `complexity_sga_proxy`           |
| Sells medical  | Industry-specific control                                  | DROPPED — no analog                                  | (documented in manifest decisions[1]) |
| Late joiner    | Sample-period-specific control                             | DROPPED — no analog                                  | (documented in manifest decisions[1]) |
| HHI            | Product-mix concentration                                  | DROPPED — not significant in paper                   | (documented in manifest decisions[1]) |
| # of states    | Multi-state parent                                         | DROPPED — not significant in paper's email extensive | (documented in manifest decisions[1]) |

Confidence is capped at 0.7 while the stability-2-period-YoY and
complexity-SGA-intensity proxies are active. A future expansion to
quarterly filings (10-Q time-series, letting us compute a closer
within-year stability analog) and a segments-count canonical line
item (letting us replace the SG&A proxy for the Single-store concept)
would let us remove both proxies and raise the cap.

## How the flag bands relate to the paper

The paper does NOT publish a composite score. Each regressor is
reported as a stand-alone coefficient (Table 3 Panel a). We adopt
the |t-statistics| as relative weights in our composite, then bucket
the resulting [0, 1] score with equally-spaced cuts at 0.30 and 0.60
(matching the compute_context_importance_signals convention). The
cuts are a **presentation convention**, NOT a paper threshold —
documented in `mvp/rules/templates/business_complexity_signals_components.yaml`
`business_complexity_bands.notes`.

A future post-MVP calibration on a wider issuer panel could replace
the presentation cuts with population-anchored quantiles (analogous
to how `compute_mdna_upfrontedness` uses Appendix D Panel A's
P25/P75 directly).

## Why this paper, this skill

The paper is a **behavioural descriptive study on private retail
cannabis dispensaries** using proprietary Headset, Inc. email-open
tracking logs. Its headline Section-5 hedonic-asymmetry finding
("managers open the email more after high-sales days than after
low-sales days") has no public-company analog — the daily tracking
data simply doesn't exist for 10-K filers. Per the workshop playbook
callout **"When the paper's setting is worlds-away from public
companies: port the determinants framework, not the behavioural
finding"**, we looked elsewhere in the paper and found the Section-4
/ Table 3 determinants regression, whose coefficients are
cross-sectional firm-characteristic predictors that generalise
directionally to public-company scale.

This is a different shape of deferral than Papers 1 and 2's
unreleased-ML-model situation: there, the obstacle was a
non-reproducible model; here, the obstacle is a non-existent dataset
on the public-company side. The playbook now covers both patterns.

## Composability

- Pair with `compute_mdna_upfrontedness` for "would managers demand
  monitoring?" + "is the narrative front-loaded?" — a high
  business-complexity + low Upfrontedness firm is a sharper
  reporting-mismatch concern than either alone.
- Pair with `compute_context_importance_signals` for "would
  managers demand monitoring?" + "does the paper predict context
  would help?" — the conjunction identifies firms where the paper's
  evidence collectively says "this firm needs rich reporting AND
  its numeric disclosures alone are insufficient."
- Pair with `compute_altman_z_score` for "would managers demand
  monitoring?" + "is the firm in the distress zone?" — the
  combination of high monitoring demand and high distress risk is
  the natural governance-review-priority pattern.

## See also

- `mvp/rules/templates/business_complexity_signals_components.yaml` —
  the rule template (per-signal thresholds, composite bands, paper-
  weight derivation table, sign-reversal notes).
- `workshop/paper_to_skill/notes/bernard_2025_information_acquisition.md` —
  the methodologist's full notes (skill-scope decision, formulas
  identified, implementation choices, candidates for future papers).
- `workshop/docs/paper_onboarding_playbook.md` "When the paper's
  setting is worlds-away from public companies" — the new playbook
  callout this paper prompted.
