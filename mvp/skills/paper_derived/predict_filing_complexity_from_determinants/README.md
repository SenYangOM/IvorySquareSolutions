# `predict_filing_complexity_from_determinants`

Paper-derived L3 skill that ports **Bernard, Blankespoor, de Kok &
Toynbee (2025)** *"Using GPT to measure business complexity"* (SSRN
4480309; forthcoming *The Accounting Review*) **Section 4.3 / Table 3
Column 2 OLS determinants regression** to MVP canonical statements + the
existing market-data fixture. Output: a firm-year
`predicted_complexity_level` anchored on the paper's Table 2 sample
mean (`0.118`), plus a three-band flag
(`predicted_elevated_complexity` / `predicted_typical_complexity` /
`predicted_reduced_complexity` / `indeterminate`).

**Paper.** Bernard, D., Blankespoor, E., de Kok, T., & Toynbee, S.
(December 2025). *Using GPT to measure business complexity.*
Forthcoming, The Accounting Review. SSRN 4480309. PDF sha256
`a4e82cafd4d51cdf22ede47dd29a8294c2ecc38c7da337f7874061630a0a6564`.

## What the paper publishes

The paper's **headline construct** is a fine-tuned Llama-3 8b model
that scores iXBRL footnote tags on every 10-K / 10-Q filing in its
~58k-filing panel: `Complexity = 1 − average_token_confidence` at
fact level, aggregated to filing level. **Model weights + pre-computed
scores are promised for a companion website but were not yet
available at paper-onboarding time.**

The paper's **Section 4.3 / Table 3** reports an OLS regression of
this filing-level Complexity on eleven firm characteristics (10K
indicator, Size, Leverage, BM, ROA, Investment, FirmAge, four
Lifecycle indicators, ReturnVolatility, AnalystFollow, Institutional)
with industry + filer-status + year-quarter fixed effects. Column 2
(the industry-FE specification used throughout the descriptive
sections) reports N=58,140, R² = 0.225.

## What this skill ships

This skill ports **Table 3 Column 2** — the deterministic determinants
regression — to the subset of **five regressors computable from MVP
canonical + market fixture**:

| Paper regressor  | Paper coef | Paper t | MVP analog                                                                    |
| ---              | ---:       | ---:    | ---                                                                           |
| `10K` indicator  | +0.014     | 30.15   | `1` (all MVP filings are 10-Ks)                                               |
| `Size`           | +0.012     | 5.74    | `ln(total_assets)`                                                            |
| `Leverage`       | +0.012     | 8.10    | `long_term_debt / total_assets` *(LTD-only proxy)*                            |
| `BM`             | +0.005     | 3.20    | `(total_assets − total_liabilities) / market_value_of_equity`                 |
| `ROA`            | −0.008     | −6.55   | `ebit / total_assets` *(EBIT proxy for IBQ)*                                  |

Six regressors are **dropped at MVP** because the underlying data is
not ingested: Investment (needs R&D + CapEx), FirmAge (needs
Compustat panel), Lifecycle Intro/Growth/Mature/Shakeout/Decline
(needs Dickinson 2011 CFO/CFI/CFF partition), ReturnVolatility (needs
CRSP monthly returns), AnalystFollow (needs IBES), Institutional
(needs Thomson 13F). Each dropped regressor is recorded in
`mvp/rules/templates/predict_filing_complexity_from_determinants_components.yaml`
with its paper coefficient + t-statistic + required data source so a
future expansion has a drop-in roadmap.

## Decision-tree branch

This paper sits cleanly in **playbook branch 3** ("ML without proxy;
scan for a deterministic construct elsewhere in the paper"), but with
a new sub-pattern distinct from Paper 2 (Kim & Nikolaev 2024) and
Paper 3 (Bernard et al. 2025 Review of Accounting Studies):

- **Paper 2** ported the partition variables from a section-5.4 signal
  panel; |t-stats| became relative weights in a composite.
- **Paper 3** ported a private-data determinants regression; proxies
  + sign-reversal + |t-stats| as weights.
- **Paper 5** ports a public-data determinants regression with
  **published coefficients on public-firm inputs** — no
  weight-normalisation, no sign-reversal. The coefficients carry
  paper-exact magnitudes because the RHS variables genuinely overlap
  MVP's canonical substrate.

The workshop playbook gains a nested callout under branch 3
documenting this Paper-5-specific sub-pattern; see
`workshop/docs/paper_onboarding_playbook.md`.

## Skill arithmetic

Decile-rank each raw continuous characteristic via piecewise-linear
interpolation through the paper's Table 2 percentiles (`P10 / P25 /
Median / P75 / P90`). Clamp below P10 to 0.0 and above P90 to 1.0.
Apply Table 3 Column 2 coefficients centred on a median-firm
baseline:

```
delta = 0.014 * (I[10K] - 0.273)              # 10K contribution (0.273 = paper sample 10-K ratio)
      + 0.012 * (decile_size - 0.5)
      + 0.012 * (decile_leverage - 0.5)
      + 0.005 * (decile_bm - 0.5)
      - 0.008 * (decile_roa - 0.5)

predicted_complexity_level = paper_sample_mean_complexity (0.118) + delta
```

**No LLM. No random component.** Deterministic byte-identical output
from byte-identical input.

## Flag bands

| Band                               | Condition                        | Anchor (Table 2 mean 0.118, SD 0.038) |
| ---                                | ---                              | ---                                   |
| `predicted_elevated_complexity`    | `level >= 0.150`                 | ~+0.84 SD above mean                  |
| `predicted_typical_complexity`     | `0.100 <= level < 0.150`         | within ~0.5 SD of mean                |
| `predicted_reduced_complexity`     | `level < 0.100`                  | below mean                            |
| `indeterminate`                    | `total_assets` null              | no anchor for Size / Leverage / ROA   |

**Bands are presentation conventions**, not paper-published
thresholds — the paper publishes a continuous scalar. Editable by an
accounting expert without Python (P1) in
`mvp/rules/templates/predict_filing_complexity_from_determinants_components.yaml`.

## Implementation choices (summary; see manifest for full list)

| # | Decision                                                                              | Rationale (one-line)                                                |
| - | ---                                                                                   | ---                                                                 |
| 1 | Headline Llama-3 8b model NOT shipped                                                 | Companion website weights not yet available; R²=0.225 disclosed      |
| 2 | 5 of 11 regressors shipped; 6 dropped with paper coefs in rule template               | P2: no fake-data stubs                                               |
| 3 | Decile rank via piecewise-linear interpolation through Table 2 percentiles            | Five anchors support a reasonable interpolant; clamping is safe     |
| 4 | ROA = EBIT / TA (proxy for paper's IBQ / ATQ)                                         | Canonical doesn't have IBQ; EBIT differs by non-operating + tax     |
| 5 | Leverage = LTD / TA (lower-bound proxy for paper's (DLCQ+DLTTQ) / ATQ)                | Canonical doesn't separate short-term debt from current_liabilities |
| 6 | Flag bands 0.100 / 0.150 = presentation conventions anchored to Table 2 moments        | Paper has no bands; practitioner partitioning for interpretation   |
| 7 | Baseline = paper_sample_mean_complexity (0.118), not firm-specific intercept         | Paper's FEs absorb intercepts; we can't recover per-firm            |
| 8 | 10K contribution centred on paper sample 10-K ratio (15865/58148 = 0.273)             | Standard econometric interpretation of an indicator partial effect  |
| 9 | Indeterminate when total_assets null; single-signal nulls zero with targeted warning | Matches Paper 3 pattern; conservative under-count                   |
| 10 | Composes via canonical + market fixture only (no sub-skill delegation)              | Mirrors Altman Z and Paper 3 architecture                           |
| 11 | Confidence capped at 0.7 while 4 approximations active; pre-iXBRL + MVE-flag -0.15 each | Each approximation has a concrete roadmap to a higher-confidence variant |

## Confidence

Starts at **0.7** while the four structural approximations are active
(headline-ML deferral, ROA-EBIT proxy, LTD-only Leverage proxy,
Table-2-percentile decile-rank). Additional penalties:

- **`−0.15`** when at least one consumed line item is from a pre-iXBRL
  manual-extraction fixture (Enron FY2000, WorldCom FY2001).
- **`−0.15`** when the MVE fixture entry is flagged
  (`estimated_from_aggregated_market_cap` or `shares_source_flag`)
  AND BM was actually consumed in the level sum.
- **Clamped to `0.0`** when flag is `indeterminate`.

Stacked penalties can take confidence to 0.40 (WorldCom FY2001:
pre-iXBRL + MVE-flagged).

## MVP eval coverage

| Filing                 | Level   | Flag                            | Confidence | Notes                                                     |
| ---                    | ---:    | ---                             | ---:       | ---                                                       |
| Apple FY2023           | 0.1276  | `predicted_typical_complexity`  | 0.70       | Size clamp 1.0; BM below P10 → 0.0; ROA clamp 1.0          |
| Microsoft FY2023       | 0.1256  | `predicted_typical_complexity`  | 0.70       | Similar profile to Apple                                  |
| Carvana FY2022         | 0.1402  | `predicted_typical_complexity`  | 0.70       | BM null (negative book equity); ROA null (missing EBIT)   |
| Enron FY2000           | 0.1269  | `predicted_typical_complexity`  | 0.55       | Pre-iXBRL penalty; as-originally-filed numbers            |
| WorldCom FY2001        | 0.1329  | `predicted_typical_complexity`  | 0.40       | Pre-iXBRL + MVE-flagged; as-originally-filed numbers       |

All five MVP issuers cluster in the `predicted_typical_complexity`
band, which is what the paper's regression predicts for firms within
the R²=0.225 explanatory envelope. Discrimination emerges on a wider
issuer panel.

## Composability

- **Pair with `compute_business_complexity_signals` (Paper 3).**
  Orthogonal complexity axes: Paper 5 predicts *reporting complexity*
  (how hard would the paper's Llama-3 model find this firm's
  footnotes?); Paper 3 predicts *monitoring-service demand* (how
  much would the firm's managers demand internal BI tools?). A
  firm high on both is the compound profile where rich internal
  reporting + hard-to-parse external disclosure coexist. A future
  L4 composite could combine the two.
- **Pair with `compute_altman_z_score`.** High
  predicted-reporting-complexity + distress-zone Altman Z is the
  "dense footnotes on a firm that's in trouble" pattern — a
  priority target for deep disclosure reading.
- **Pair with `compute_beneish_m_score`.** High predicted complexity
  + manipulator-likely Beneish is the "opaque disclosure on a firm
  flagged for earnings management" pattern — the highest-priority
  diligence target.

## See also

- Paper: `mvp/data/papers/bernard_2025_gpt_complexity.pdf`
- Methodologist notes:
  `workshop/paper_to_skill/notes/bernard_2025_gpt_complexity.md`
- Manifest: `manifest.yaml` (strict-validates via
  `SkillManifest.load_from_yaml`)
- Rule template:
  `mvp/rules/templates/predict_filing_complexity_from_determinants_components.yaml`
- Paper-replication test:
  `mvp/tests/integration/test_predict_filing_complexity_from_determinants_paper_replication.py`
- Gold case:
  `mvp/eval/gold/predict_filing_complexity_from_determinants/worldcom_2001.yaml`
- Workshop playbook callout (branch-3 sub-pattern):
  `workshop/docs/paper_onboarding_playbook.md`
