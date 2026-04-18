# compute_mdna_upfrontedness

**Layer:** `paper_derived` (L3)
**Maintainer persona:** `quant_finance_methodologist`
**Status:** `alpha` at MVP

Kim, Muhn, Nikolaev & Zhang (2024) firm-level Information Positioning
score over a 10-K MD&A. Descriptive textual-structure signal: does the
firm place informationally-heavier paragraphs up front, or does it push
them toward the tail?

## Paper summary

Kim, A. G., Muhn, M., Nikolaev, V. V., & Zhang, Y. (November 2024).
*Learning Fundamentals from Text.* University of Chicago Booth School
of Business Working Paper. PDF sha256:
`0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5`.

The paper's headline contribution is an attention-based ML model over
10-K paragraphs that explains stock-return reactions. Applied to
76,929 filings and 20M+ paragraphs, the attention weights reveal (a)
which 10-K *items* matter (MD&A > Financial Statements > Business >
Risk Factors, all others distantly trailing), (b) which *topics*
matter (segment performance, profitability, liquidity, goodwill), and
(c) how managers **position** the information within MD&A.

The positioning analysis (§VI) is where this skill draws its signal:

- **Equation 8** (p. 25) — per-paragraph position score:

      Paragraph_Position_k = 1 − rank_k / N

  First paragraph scores close to 1; last scores 0.

- **Equation 9** (p. 25) — firm-level Information Positioning
  (also called "Upfrontedness" in Appendix D):

      Upfrontedness = Σ_k [(1 − rank_k / N) × Paragraph_Importance_k]

  The paper's `Paragraph_Importance_k` comes from its attention model.
  Appendix D Panel A reports the firm-level distribution: N=66,757,
  mean=0.5161, std=0.0243, P25=0.5012, P50=0.5143, P75=0.5283.

Appendix D Panel B further shows that low Upfrontedness correlates
(within-firm and cross-sectionally) with operating losses, low ROA,
high earnings volatility, negative MD&A sentiment, and lower
readability — managers strategically push negative news toward the
end of the section.

## Flag bands

| Band                | Upfrontedness range   | Paper anchor                      |
|---------------------|-----------------------|-----------------------------------|
| `forthcoming`       | score ≥ 0.5283        | Appendix D P75                    |
| `typical`           | 0.5012 ≤ score < 0.5283 | P25 .. P75                       |
| `obfuscating_likely`| score < 0.5012        | Appendix D P25                    |
| `indeterminate`    | score = null          | MD&A < 10 valid paragraphs        |

The quartile thresholds are **paper-reported population anchors**,
not model-derived cutoffs. A score of 0.501 is economically
indistinguishable from 0.502; the three-band flag is a quick-look
presentation aid.

## Implementation decisions

1. **Paragraph-importance proxy: length-share.** The paper's attention
   model is not publicly released. We ship
   `Paragraph_Importance_k = length_k / Σ_k length_k` as a documented
   proxy — the minimum non-trivial choice (uniform importance makes
   Equation 9 collapse to the constant `(N-1)/(2N)`). Long paragraphs
   in our implementation carry more weight; the paper's attention
   model weights based on contribution to explaining returns. These
   can disagree — notably on dense tabular content at the end of
   modern MD&As, where length-share up-weights what the paper's
   attention model apparently down-weights. The skill emits
   `warning=paragraph_importance_proxy_used` on every non-null call.
2. **Paragraph split rule.** Two or more consecutive newlines in the
   `extract_mdna` output text delimit a paragraph; paragraphs whose
   stripped length is below 20 characters are dropped (eliminates
   surviving section headers and list fragments).
3. **N < 10 returns indeterminate.** The paper's regression sample
   requires ≥ 10 MD&A paragraphs. Below that we return `score=null`,
   `flag=indeterminate`, `warning=mdna_too_short`.
4. **Pre-iXBRL confidence penalty.** Enron FY2000 and WorldCom FY2001
   are SGML-era filings with noisier paragraph breaks; confidence
   drops from 0.70 to 0.55, warning=`pre_ixbrl_paragraph_structure`.
5. **MD&A extraction is delegated to `extract_mdna` through the
   registry** (no direct import). Required by §5 modularity contract
   and P3 composability.
6. **Confidence capped at 0.70** while the length-share proxy is
   active. A future attention-model-backed variant could raise the
   cap; see the candidates list at the bottom of
   `workshop/paper_to_skill/notes/fundamentals_text.md`.

## MVP eval coverage

| Issuer   | FYE        | Expected score (proxy) | Expected flag (proxy)  | Confidence | Notes                                     |
|----------|------------|-----------------------:|------------------------|-----------:|-------------------------------------------|
| Apple    | 2023-09-30 |                  ~0.435|   obfuscating_likely   |       0.70 | Dense late-MD&A tables, proxy pulls low   |
| Microsoft| 2023-06-30 |                    null|   indeterminate        |       0.00 | `extract_mdna` finder truncates — known   |
| Carvana  | 2022-12-31 |                  ~0.495|   obfuscating_likely   |       0.70 | Close to P25, ambiguous                   |
| Enron    | 2000-12-31 |                  ~0.443|   obfuscating_likely   |       0.55 | SGML-era, pre-iXBRL penalty active        |
| WorldCom | 2001-12-31 |                  ~0.514|   typical              |       0.55 | SGML-era, pre-iXBRL penalty active        |

Gold cases are authored at `mvp/eval/gold/mdna_upfrontedness/` and
score correctness is verified by the eval runner. The
paper-replication test at
`mvp/tests/integration/test_compute_mdna_upfrontedness_paper_replication.py`
asserts Equations 8 and 9 reproduce correctly on synthetic
constructions (uniform, monotone-decreasing, monotone-increasing,
degenerate) — the appropriate bar for a proxy-based implementation
whose population mean is not expected to match the paper's
attention-weighted mean.

## Known limitations

- The length-share proxy is NOT equivalent to the paper's attention-
  derived importance. Scores systematically bias lower than the
  paper's 0.5161 mean on modern filings with dense late-MD&A content.
  Treat as a screening signal.
- Microsoft FY2023 returns indeterminate because the `extract_mdna`
  Item-7/Item-8 finder truncates the MS MD&A to essentially nothing.
  This is an `extract_mdna` limitation upstream of this skill.
- The paper's sample is 1996–2023 US public 10-K filings. Applying
  the quartile thresholds to other filing types (10-Q, proxy
  statements, foreign filings) is out of scope.
- A low Upfrontedness score alone is not evidence of obfuscation.
  The paper's Appendix D Panel B finds the correlation with
  obfuscation covariates (loss, low ROA, earnings volatility,
  negative sentiment, low readability); cross-check those before
  reading the flag as a red signal.

## Future work (tracked in workshop notes)

See `workshop/paper_to_skill/notes/fundamentals_text.md` for the
longer list. Summary:

- Swap in an attention-model-derived paragraph-importance weight once
  such a model is available. This would let us tighten the eval
  tolerance to the paper's ±0.05 on the 0.5161 population mean.
- Build `compute_mdna_topic_distribution` (L1/L2) applying the
  paper's 13-topic / ~150-subtopic taxonomy (Appendix E) to MD&A
  paragraphs. Would consume an LLM classifier + OpenAI embeddings.
- Build `compute_item_importance_ranking` (L2) reproducing Table IV's
  item-level ordering for a given filing. Requires per-paragraph
  importance as upstream signal.
