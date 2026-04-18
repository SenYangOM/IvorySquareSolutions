# compute_beneish_m_score

**Layer:** `paper_derived` (L3)
**Maintainer persona:** `quant_finance_methodologist`
**Status:** `alpha` at MVP

Beneish (1999) eight-component earnings-manipulation discriminant,
applied to a single US public 10-K filing.

## Paper summary

Beneish, M. D. (1999). "The Detection of Earnings Manipulation." *Financial Analysts Journal*, 55(5), 24–36. DOI: `10.2469/faj.v55.n5.2296`.

Beneish estimates a probit model separating 74 AAER-identified
earnings manipulators (sample period 1982–1992) from 2,332 industry-
matched Compustat controls. Inputs are eight financial-statement
ratios, each constructed from year-t and year-(t–1) values: DSRI
(days sales in receivables index), GMI (gross margin index), AQI
(asset quality index), SGI (sales growth index), DEPI (depreciation
index), SGAI (SG&A index), LVGI (leverage index), and TATA (total
accruals to total assets).

## Coefficient derivation

Beneish's Table 3 Panel A (unweighted probit, right column) reports:

| Variable  | Coefficient | t-statistic |
|-----------|------------:|------------:|
| intercept |      -4.840 |      -11.01 |
| DSRI      |       0.920 |        6.02 |
| GMI       |       0.528 |        2.20 |
| AQI       |       0.404 |        3.20 |
| SGI       |       0.892 |        5.39 |
| DEPI      |       0.115 |        0.70 |
| SGAI      |      -0.172 |       -0.71 |
| TATA      |       4.679 |        3.73 |
| LVGI      |      -0.327 |       -1.22 |

Pseudo-R² = 0.371; χ² = 129.20. Intercept and five of the eight
variables (DSRI, GMI, AQI, SGI, TATA) are significant at
conventional levels; DEPI / SGAI / LVGI are not. TATA carries the
largest absolute coefficient and produces the most variance in M.

The skill's coefficients are hard-coded in `skill.py` as
`_COEF = {...}` and `_INTERCEPT = -4.840`. The threshold `-1.78` is
read at skill-manifest time from the rule template
`rules/templates/m_score_components.yaml` — not hard-coded in Python
— per operating principle P1.

## Implementation decisions

1. **Threshold -1.78** (not -2.22). Beneish 1999 p. 16, 20:1 to 30:1
   relative-error-cost regime. The -2.22 threshold commonly cited
   (including in an early draft of `mvp_build_goal.md`) comes from
   Beneish, Lee & Nichols (2013), a later paper with a different
   estimation sample. The MVP uses the 1999 value to keep
   "paper-derived" honest.
2. **TATA approximation**. The paper's full definition subtracts
   ΔCash, ΔCurrent Maturities of LTD, and ΔIncome Tax Payable from
   the working-capital delta. None of those three are canonical line
   items at MVP, so TATA is computed from `(ΔCA − ΔCL) − D&A_t)` /
   `TA_t`. The skill emits `warning=tata_approximation` on every
   call that completes, so the ±0.10 paper-replication tolerance
   becomes explicit rather than silent.
3. **Receivables concept**. DSRI uses `trade_receivables_net` only
   (mapped to `AccountsReceivableNetCurrent` in the iXBRL
   path), excluding other receivables. Beneish's paper uses
   Compustat item RECT (trade receivables net of allowance).
4. **Pre-iXBRL handling**. Enron FY1999/FY2000 and WorldCom
   FY2000/FY2001 filings predate iXBRL; values come from
   hand-authored manual-extraction YAMLs. Confidence is reduced by
   0.1 per pre-iXBRL line item consumed (clamped at 0).

## MVP eval coverage

5 sample filings, one per issuer:

| Issuer   | FYE        | Expected flag        | Expected M range |
|----------|------------|----------------------|------------------|
| Enron    | 2000-12-31 | manipulator_likely   | [-1.0, 2.5]      |
| Apple    | 2023-09-30 | manipulator_unlikely | [-3.5, -2.0]     |
| Microsoft| 2023-06-30 | manipulator_unlikely | [-3.5, -2.0]     |
| Carvana  | 2022-12-31 | indeterminate        | n/a (TATA null)  |
| WorldCom | 2001-12-31 | manipulator_unlikely | [-3.5, -1.5]     |

The gold file lives at `eval/gold/beneish/` and is authored in Phase 5.
The paper-replication test in `tests/integration/test_beneish_paper_replication.py`
uses a hand-constructed canonical-statements fixture matched to one
of Beneish's worked examples, asserting M-score within ±0.05 of the
paper-reported value.

## Known limitations

- Beneish's sample (1982–1992) predates ASC 606. Coefficients may not
  generalize cleanly to post-ASC-606 filings; the skill does not
  re-estimate.
- Service-economy firms with low PP&E produce noisy DEPI readings
  (the paper's own DEPI coefficient is insignificant).
- WorldCom's manipulation was capitalization of line costs as
  capex — a pattern the eight Beneish ratios capture weakly.
  WorldCom's M tends to land near -1.5 to -1.3, close to but often
  not above the threshold.
- TATA uses the 16-canonical approximation; the exact paper
  definition would require three additional line items that are not
  broken out at MVP.
- LLM-refined natural-language interpretation is post-MVP. The L2
  `interpret_m_score_components` skill provides deterministic,
  template-substituted per-component interpretations.
