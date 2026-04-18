# 04 — Skills Catalogue (live as of 2026-04-18)

**12 skills shipped, all manifest-driven, all loadable as MCP tool specs and OpenAI tool-use specs from the same registry. Descriptions below are lifted verbatim from each skill's `description_for_llm` field (the same text an agent reads to decide whether to call the skill).**

To regenerate this file from the registry:

```bash
cd mvp && .venv/bin/python -m mvp.cli.main skills list
```

The catalog is the single source of truth — these descriptions, the MCP catalog, the OpenAI catalog, the CLI help text, and the OpenAPI doc all derive from one manifest per skill.

---

## Layer 1 — Fundamental skills (atomic extraction, no judgment)

### `extract_canonical_statements`
**Layer:** fundamental · **Version:** 0.1.0 · **Status:** alpha

Return the three canonical financial statements (income statement, balance sheet, cash flow statement) for a US public company's annual 10-K filing, with per-line-item citations back to the source XBRL facts or SGML extraction. Use this when an agent needs structured, standardized financial-statement data for an issuer at a specific fiscal-year-end; the output line items are named consistently across issuers and years. Do NOT call this to retrieve arbitrary 10-K narrative sections — use `extract_mdna` for that.

- **Example call:** `{"cik": "0001024401", "fiscal_year_end": "2000-12-31"}`
- **Output shape:** `{income_statement, balance_sheet, cash_flow_statement, citations[], data_quality_flags[]}` — 16 canonical line items per filing, each carrying `(filing_id, statement_role, line_item_name, value, sha256)`.
- **When NOT to call:** for narrative text (use `extract_mdna`); for ratios or scores (use the L3 paper-derived skills).

### `extract_mdna`
**Layer:** fundamental · **Version:** 0.1.0 · **Status:** alpha

Return the verbatim text of Part II, Item 7 "Management's Discussion and Analysis of Financial Condition and Results of Operations" from a US public company's 10-K filing. The returned text is the section body only (headings + paragraphs); inline HTML markup is stripped. Use this when an agent needs the narrative text an accounting expert would read to interpret the numbers; do NOT use it for structured financial-statement values (use `extract_canonical_statements` for that). For filings where the MD&A section cannot be identified, the skill returns `section_text=null` and a warning rather than guessing.

- **Example call:** `{"cik": "0000320193", "fiscal_year_end": "2023-09-30"}`
- **Output shape:** `{section_text, paragraph_count, warnings[]}`
- **When NOT to call:** for non-10-K filings; for sections other than MD&A.

---

## Layer 2 — Interpretation skills (judgment from declarative rules)

### `interpret_m_score_components`
**Layer:** interpretation · **Version:** 0.1.0 · **Status:** alpha

Interpret the eight Beneish (1999) ratio components (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA) for a specific US public-company 10-K filing. For each component, returns the severity band that the component value falls into (low / medium / high / critical, or `indeterminate_null` when the component could not be computed), the accounting-expert-authored interpretation text for that band, follow-up diligence questions, and citations back to the canonical line items that produced the component value. Also returns a 2-4 sentence overall narrative that names the filing and enumerates the flagged components. Use this after `compute_beneish_m_score` when an agent needs the "why" behind the M-score, not just the scalar.

- **Output shape:** `{components: {DSRI: {value, severity, interpretation_text, follow_up_questions[], citations[]}, …}, overall_narrative}`
- **When NOT to call:** if you only need the scalar (call `compute_beneish_m_score` directly).

### `interpret_z_score_components`
**Layer:** interpretation · **Version:** 0.1.0 · **Status:** alpha

Interpret the five Altman (1968) Z-score components (X1 working-capital / total-assets, X2 retained-earnings / total-assets, X3 EBIT / total-assets, X4 market-value-of-equity / total-liabilities, X5 sales / total-assets) for a specific US public-company 10-K filing. For each component, returns the severity band, the accounting-expert-authored interpretation text, follow-up diligence questions, and citations back to the canonical line items (X4's numerator citation resolves against the engineering-owned market-data fixture). Also returns a deterministic 2-4 sentence overall narrative that names the Altman zone (safe / grey / distress / indeterminate) when a composite Z score and flag are supplied. Use this after `compute_altman_z_score` when an agent needs the "why" behind the Z zone, not just the scalar.

- **When NOT to call:** for filings outside the supported issuer set with no market-cap fixture entry.

---

## Layer 3 — Paper-derived skills (faithful implementations of published constructs)

### `compute_beneish_m_score`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Beneish, M. D. (1999). *The Detection of Earnings Manipulation*. Financial Analysts Journal 55(5), 24–36.

Compute the Beneish (1999) M-score — an eight-component earnings-manipulation discriminant — for a US public company's 10-K filing. Returns the scalar M-score, the eight component values (DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA), a categorical flag (`manipulator_likely / manipulator_unlikely / indeterminate`), and citations back to the canonical line items. Use this to screen a filing for earnings-manipulation red flags; do NOT treat the output as a fraud verdict — the model is a classifier and its paper-reported Type I error rate is ~50%. When inputs are missing, the skill returns `flag=indeterminate` and `m_score=null` with a warning listing the gaps.

- **Threshold pinned to the 1999 paper's value of -1.78** (not the popular -2.22 from Beneish et al. 2013). Documented in the manifest's `implementation_decisions`.
- **Example call:** `{"cik": "0001024401", "fiscal_year_end": "2000-12-31"}`
- **Live Enron output:** `m_score = -0.2422, flag = manipulator_likely`.
- **When NOT to call:** for non-10-K filings; for filings where the prior-year statements are unavailable.

### `compute_altman_z_score`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Altman, E. I. (1968). *Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy*. Journal of Finance 23(4), 589–609.

Compute the Altman (1968) Z-score — a five-variable bankruptcy-prediction discriminant — for a US public company's 10-K filing. Returns the scalar Z-score, the five component values (X1 working-capital-to-total-assets, X2 retained-earnings-to-total-assets, X3 EBIT-to-total-assets, X4 market-value-of-equity-to-total-liabilities, X5 sales-to-total-assets), a categorical zone flag (`safe` when Z > 2.99, `grey_zone` when 1.81 ≤ Z ≤ 2.99, `distress` when Z < 1.81, `indeterminate` when any component cannot be computed), and citations back to the canonical line items and the market-data fixture. X4's numerator (market value of equity) comes from the engineering-owned fixture at `data/market_data/equity_values.yaml` and is NOT parsed from the filing. Use this to screen a filing for bankruptcy-probability signal; do not treat the output as a verdict — Altman's 1968 sample was manufacturers 1946-1965 and coefficients may not generalize cleanly to modern issuers or to service-sector firms.

- **X5 coefficient pinned to the paper-exact 0.999** (not the rounded 1.0 commonly seen in textbooks).
- **Live Enron output:** `z_score = 2.51, flag = grey_zone` (Enron filed this 10-K ~11 months before its November 2001 collapse).
- **When NOT to call:** for issuers without a market-cap fixture entry; for service-sector firms where the manufacturer-trained coefficients are weakest.

### `compute_mdna_upfrontedness`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Kim, A. G., Muhn, M., Nikolaev, V. V., & Zhang, Y. (Nov 2024). *Learning Fundamentals from Text*. University of Chicago Booth working paper.

Compute the Kim, Muhn, Nikolaev & Zhang (2024) MD&A "Upfrontedness" / firm-level Information Positioning score for a US public company's 10-K filing. Returns the scalar score in [0, 1] (≈0.5 for a typical firm, per the paper's Appendix D distribution), a categorical flag (`forthcoming / typical / obfuscating_likely / indeterminate`) computed from the paper's reported P25/P75 cut-offs, per-paragraph position and importance traces, and citations back to the MD&A source passage. Use this as a textual-structure red-flag screen; a low score (<0.50) means the firm has placed long, information-dense paragraphs toward the end of MD&A rather than up front — a pattern the paper associates with negative sentiment, low profitability, and high earnings volatility. Do NOT treat the score as an obfuscation verdict; the paper's construct is descriptive, and our implementation uses a length-share proxy for the attention-weighted importance used in the original paper.

### `compute_context_importance_signals`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Kim, A. G., & Nikolaev, V. V. (2024). *Context-Based Interpretation of Financial Information*. Journal of Accounting Research, accepted Oct 2024.

Compute Kim & Nikolaev (2024) §5.4 firm-year context-importance signals for a US public company's 10-K filing. Returns a composite `context_importance` score in [0, 1] (≈0 for steady-state, numerically-easy-to-interpret firms; ≈1 for distressed, volatile, extreme-valuation firms whose numeric disclosures benefit most from narrative context), a categorical flag (`context_critical / context_helpful / context_marginal / indeterminate`) computed from the paper-derived weights in Table 7 Panel A, four per-signal diagnostics (loss indicator, earnings volatility proxy, accruals magnitude, market-to-book extremity), and citations back to the source line items + market-data fixture. Use this as a meta-signal BEFORE deciding how much weight to put on a filing's MD&A: a `context_critical` flag means the paper predicts the narrative WOULD be especially informative for this firm, not that the firm's disclosure actually delivers. Pair with `compute_mdna_upfrontedness` for the structure-of-narrative axis.

### `compute_business_complexity_signals`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Bernard, D., Cade, N. L., Connors, E. H., & de Kok, T. (2025). *Descriptive evidence on small business managers' information choices*. Review of Accounting Studies 30, 3254–3294.

Compute Bernard, Cade, Connors & de Kok (2025) Section 4 / Table 3 Panel a firm-year business-complexity signals for a US public company's 10-K filing. Returns a composite `business_complexity_score` in [0, 1] (≈0 for small, volatile, low-overhead single-segment firms; ≈1 for large, stable, corporate-overhead-heavy firms whose profile predicts intense managerial monitoring demand), a categorical flag (`complex_monitoring_intensive / moderate_monitoring_intensity / simple_monitoring_light / indeterminate`) computed from the paper-derived weights in Table 3 Panel a column 1, three per-signal diagnostics (size by revenue, revenue stability year-over-year, corporate-overhead intensity via SG&A / revenue), and citations back to the source line items. Use this as a structural-complexity meta-signal BEFORE deciding how much scrutiny to put on a filing's governance or disclosure practices: a `complex_monitoring_intensive` flag means the paper's model predicts this firm's managers would demand intense monitoring tools, not that the firm's actual disclosures are high-quality. Pair with `compute_mdna_upfrontedness` or `compute_context_importance_signals` for complementary lenses.

### `compute_nonanswer_hedging_density`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** de Kok, T. (June 2024). *ChatGPT for Textual Analysis? How to use Generative LLMs in Accounting Research*. SSRN 4429658.

Compute the hedging-language density in a US public company's 10-K MD&A, applying de Kok (2024) Online Appendix OA 3's 78-token non-answer keyword filter (7 trigrams + 23 bigrams + 45 unigrams, verbatim from the paper). Returns `hedging_density` in [0, 1] (fraction of MD&A sentences containing at least one keyword hit), a three-band flag (`low_hedging / typical_hedging / high_hedging / indeterminate`), per-category hit counts (trigram / bigram / unigram), matches per 1,000 words, and a citation pointing at the MD&A passage. Use this as a disclosure-language red-flag screen complementary to `compute_mdna_upfrontedness` (which scores positional structure). Do NOT treat the score as a disclosure-quality verdict; hedging is often legitimate (material uncertainty, safe-harbor language). The paper's dataset is earnings-call Q&A, not MD&A — every call carries `warning=substrate_port_mdna_vs_earnings_call`.

### `predict_filing_complexity_from_determinants`
**Layer:** paper_derived · **Version:** 0.1.0 · **Paper:** Bernard, D., Blankespoor, E., de Kok, T., & Toynbee, S. (Dec 2025). *Using GPT to measure business complexity*. Forthcoming, The Accounting Review. SSRN 4480309.

Predict Bernard, Blankespoor, de Kok & Toynbee (2025) filing-level business-complexity for one US public company 10-K filing via the paper's OWN Table 3 Column 2 determinants regression — NOT the paper's headline Llama-3 8b model. Given canonical total_assets, total_liabilities, long_term_debt, ebit (for ROA), and the existing market-value-of-equity fixture entry (for BM), returns `predicted_complexity_level` in [0.0, ~0.2] anchored on the paper's Table 2 sample mean (0.118), plus a three-band flag (`predicted_elevated_complexity / predicted_typical_complexity / predicted_reduced_complexity / indeterminate`). Also returns the four decile ranks estimated via piecewise-linear interpolation through the paper's Table 2 percentiles, the five-regressor contribution trace, the paper-exact coefficients (10K=+0.014, Size=+0.012, Leverage=+0.012, BM=+0.005, ROA=-0.008), and citations back to the canonical line items. The paper's headline Llama-3 complexity measure is NOT implemented — the score is a PREDICTION of what that measure would be for a firm with the given characteristics. Pair with `compute_business_complexity_signals` (monitoring-demand signal) for an orthogonal complexity axis.

---

## Layer 4 — Composite skills (orchestrations)

### `analyze_for_red_flags`
**Layer:** composite · **Version:** 0.1.0 · **Status:** alpha

Run a combined earnings-manipulation + bankruptcy-risk screen on a US public company's 10-K filing. Returns two result blocks — `m_score_result` (Beneish 1999 M-score, 8 components, per-component interpretations, citations, flag) and `z_score_result` (Altman 1968 Z-score, 5 components, per-component interpretations, citations, flag) — plus a provenance block that names the composite version, the rule-set version, and the sub-skill versions that produced each result. Use this as the one-call entry point when an agent wants both red-flag screens for a given issuer; do NOT call this to retrieve either score in isolation (call the paper-derived skills directly for those). Both scores are deterministic functions of the canonical statements and the market-data fixture — identical inputs produce identical outputs modulo the provenance timestamps.

- **The headline demo.** A single call returns the full Enron 2000 analysis with both scores, both flags, both per-component interpretations, all 32 + 8 = 40 citations resolving 100%, and a complete provenance trace.

---

## Coming next (deferred candidates from the post-MVP paper-onboarding loop)

The five papers onboarded post-MVP each surfaced 2-3 additional candidate skills that were deliberately deferred (one-skill-per-paper discipline). They are tracked in `workshop/paper_to_skill/notes/<paper>.md` under "Candidates for future papers":

| Skill ID (planned) | Paper | Layer | Why deferred today |
|---|---|---|---|
| `compute_mdna_topic_distribution` | Kim et al. 2024 (Fundamentals from Text) | L1 / L2 | Requires LLM classifier on Appendix E 13-topic taxonomy; depends on training-sample build-out. |
| `compute_item_importance_ranking` | Kim et al. 2024 | L2 | Requires per-paragraph importance signal (attention-model proxy or alternative). |
| `compute_earnings_persistence_ols` | Kim & Nikolaev 2024 | L3 | Needs a wider issuer panel than 5×2 firm-years. |
| `extract_earnings_related_sentences` | Kim & Nikolaev 2024 | L1 | Small, useful, composable; ships when narrative-analytics work picks up. |
| `compute_contextuality_ml` | Kim & Nikolaev 2024 | L3 | Full BERT+ANN measure; needs GPU + Compustat panel. |
| `compute_monitoring_asymmetry_signals` | Bernard et al. 2025 (RAST) | L3 | Needs 8-K timing data + earnings-surprise fixture. |
| `compute_information_acquisition_score` | Bernard et al. 2025 (RAST) | L3 | Needs Form 4 attention proxies + insider-trading data. |
| `classify_nonanswers_in_earnings_calls` | de Kok 2024 | L3 | Needs earnings-call transcripts + fine-tuning budget. |
| `measure_gllm_construct_validity` | de Kok 2024 | L2 | Meta-skill; needs a second classifier-shaped L3 to be useful. |
| `fetch_gpt_complexity_from_companion_website` | Bernard, Blankespoor, de Kok, Toynbee 2025 | L3 | Ships when paper's companion-website weights go live. |
| `classify_debt_features_from_keywords` | Bernard et al. 2025 | L3 | Needs iXBRL at the tag level with ASC-topic segmentation. |
| `compute_within_filing_complexity_variance` | Bernard et al. 2025 | L3 | Builds on companion-website fetcher above. |

The discipline: ship one new skill per paper-onboarding cycle, document the deferred candidates, queue them for the next iteration. The paper-onboarding loop itself averaged **149 minutes per paper across the 5-paper post-MVP corpus** (down from 210 to 105 over five iterations — see §08 Traction).
