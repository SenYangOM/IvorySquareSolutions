# compute_altman_z_score

**Layer:** `paper_derived` (L3)
**Maintainer persona:** `quant_finance_methodologist`
**Status:** `alpha` at MVP

Altman (1968) five-variable bankruptcy-prediction discriminant,
applied to a single US public 10-K filing.

## Paper summary

Altman, E. I. (1968). "Financial Ratios, Discriminant Analysis and the
Prediction of Corporate Bankruptcy." *Journal of Finance*, 23(4),
589–609. DOI: `10.1111/j.1540-6261.1968.tb00843.x`.

Altman builds a multiple-discriminant-analysis model separating 33
bankrupt US manufacturers (bankruptcies 1946–1965, asset range
$1M–$25M) from 33 paired non-bankrupt firms matched by SIC and
asset size. Twenty-two candidate ratios are reduced to five via
stepwise inclusion, producing the now-canonical Z function:

    Z = 0.012·X1 + 0.014·X2 + 0.033·X3 + 0.006·X4 + 0.999·X5

with X1–X4 entered as **percentages** and X5 as a decimal ratio
(Equation I, paper p. 597).

Zone cut-offs (paper §V):

- Z > 2.99 — **safe**. In Altman's estimation sample, 100% of
  non-bankrupt firms land above 2.99.
- Z < 1.81 — **distress**. In Altman's estimation sample, 100% of
  firms that filed bankruptcy within two years of the sampled
  financials land below 1.81.
- 1.81 ≤ Z ≤ 2.99 — **grey zone** (Altman's "zone of ignorance").

## Coefficient derivation

| Variable | Formula                                            | Coefficient |
|----------|----------------------------------------------------|------------:|
| X1       | (current_assets − current_liabilities) / total_assets |      0.012 |
| X2       | retained_earnings / total_assets                   |       0.014 |
| X3       | EBIT / total_assets                                |       0.033 |
| X4       | market_value_of_equity / total_liabilities         |       0.006 |
| X5       | revenue / total_assets                             |       0.999 |

The practitioner form (X1–X4 as decimal ratios with coefficients
1.2, 1.4, 3.3, 0.6 and X5 × 0.999) is mathematically equivalent.
The MVP uses the paper-exact printed form.

Altman's §III ranks the variables by their univariate F-tests: X3
(EBIT/TA) is the single strongest discriminator, followed by X5,
X1, X4, and X2. The MVP does not use the univariate rankings — the
whole point of the discriminant is that the multivariate
combination outperforms any single ratio.

## Implementation decisions

1. **X5 coefficient is 0.999**, not the rounded 1.0 seen in several
   textbook references. Altman (1968) Equation I prints the
   coefficient explicitly as 0.999. Z drift from using 1.0 would be
   0.001 × X5 (typically < 0.003), negligible against the ±0.10
   paper-replication tolerance but carried through faithfully per
   principle P2.
2. **Original 1968 Z**, not the 1983 Z'-prime. Altman's 1983
   revision drops X5 and re-estimates coefficients for
   non-manufacturers. The MVP scope decision (`BUILD_REFS.md` §5.1)
   picked 1968 original for all 5 issuers; the skill's
   `limitations` block surfaces that services-heavy issuers (Apple,
   Microsoft) produce inflated Z via X4 dominance.
3. **Market value of equity** is sourced from the engineering-owned
   fixture `data/market_data/equity_values.yaml`, NOT from any
   filing line item. The fixture entries are loaded via
   `mvp.ingestion.market_data_loader.load_equity_values`, which
   validates each row against a 1%-tolerance consistency check
   (shares × price ≈ MVE). A missing fixture row raises
   `missing_market_data` rather than synthesizing a value.
4. **WorldCom FYE-2001 MVE is an estimated aggregate** from
   companiesmarketcap.com, because the two tracking stocks (WCOM,
   MCIT) dropped from Yahoo Finance after delisting. The fixture
   flags the row with
   `market_cap_source: estimated_from_aggregated_market_cap`; at
   call time the skill emits `warning=market_value_estimated` and
   reduces confidence by 0.15.
5. **Pre-iXBRL handling**. Enron FY2000 and WorldCom FY2001 use
   the hand-authored manual-extraction YAMLs for their canonical
   statements. Confidence is reduced by 0.1 per pre-iXBRL line
   item consumed.

## MVP eval coverage

5 sample filings, one per issuer:

| Issuer   | FYE        | Expected flag   | Expected Z range |
|----------|------------|-----------------|------------------|
| Enron    | 2000-12-31 | grey_zone       | [1.8, 3.2]       |
| Apple    | 2023-09-30 | safe            | [5.0, 10.0]      |
| Microsoft| 2023-06-30 | safe            | [5.0, 10.0]      |
| Carvana  | 2022-12-31 | indeterminate   | n/a (EBIT null)  |
| WorldCom | 2001-12-31 | distress        | [0.5, 1.8]       |

The gold file lives at `eval/gold/altman/` and is authored in Phase 5.
The paper-replication test in
`tests/integration/test_altman_paper_replication.py` uses a
hand-constructed canonical-statements fixture matched to Altman's
public gray-area Table-6 firm, asserting Z within ±0.05 of the
paper-reported value.

## Known limitations

- Altman's 1968 sample is US manufacturers 1946–1965. Coefficients
  are known to mis-fit services and technology firms (Apple,
  Microsoft produce Z values above 7 due to X4 dominance), and
  asset-light distributors (Carvana's X5 would dominate in a
  well-formed case; at MVP Carvana's X3 is null so the score is
  indeterminate).
- The 1968 Z assumes a traded market for common equity (for X4's
  numerator). Private firms and firms in trading halts cannot be
  scored.
- EBIT, Altman's X3 numerator, can be null in the canonical
  statements (Carvana FY2022 is the MVP example; no
  `OperatingIncomeLoss` tag in the filing). When that happens the
  skill returns `flag=indeterminate`.
- MVE is an exogenous fixture input; if the fixture has no row for
  `(cik, fiscal_year_end)` the skill raises `missing_market_data`.
- LLM-refined natural-language interpretation is post-MVP. The L2
  `interpret_z_score_components` skill provides deterministic,
  template-substituted per-component interpretations.
