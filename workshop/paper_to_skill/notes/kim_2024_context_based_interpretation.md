# Paper notes: `J of Accounting Research - 2024 - KIM - Context-Based Interpretation of Financial Information.pdf`

> Kim, A. G., & Nikolaev, V. V. (2024).
> *Context-Based Interpretation of Financial Information.*
> Journal of Accounting Research, accepted 31 October 2024.
> DOI: 10.1111/1475-679X.12593. 47 pp. PDF sha256
> `013d9bbcd45ec4636dc3427561770c6489a29aa92e1b116281206344b442f533`.

Author voice: `quant_finance_methodologist`. Expected reading time of the
skill reviewer behind me: 15 minutes.

---

## (a) Skill-scope decision

**Layer: L3 paper-derived. Skill id: `compute_context_importance_signals`.**

Decision reached by running the workshop/paper_to_skill/README §5
decision tree. The paper offers four plausible constructs, each with a
different feasibility profile:

1. **The headline contextuality measure** — accuracy of a fully-connected
   ANN minus accuracy of a partially-connected ANN, both with a BERT
   front-end (768-dim CLS vector). **Not shippable at MVP scope.** The
   paper's training pipeline requires:
   - 138,129 MD&As pre-processed through BERT-base-uncased (5× Tesla
     V100 32GB GPUs in the paper's setup);
   - Compustat panel 1995-2021 with up-to-4-year lags of net income +
     operating cash flow per firm;
   - 30 random restarts × 22 yearly training windows × 4 target
     variables × 2 model variants = ~5,000 ANN training runs;
   - CRSP linked returns for the return-prediction analyses.
   Re-implementing it would not be paper-faithful — the trained weights
   are not released, the random-init seeds are not reported, and
   re-training on a different sample would not reproduce Table 3's
   accuracy numbers (e.g., 56.10% / 64.86%). Same situation as Paper 1
   (Kim et al. 2024 "Learning Fundamentals from Text" — different paper,
   same authors, same unreleased-ML-model pattern). **The Paper-1
   playbook callout** ("when a paper's core construct is an unreleased
   ML model, ship the equation + a documented proxy") applies here too,
   except this paper's "equation" is a neural network's accuracy
   delta — there is no closed-form proxy that preserves the construct's
   shape. So we follow the second branch of the playbook callout: when
   the model is the whole point AND there is no honest proxy, the
   model-based skill is dropped, and we look elsewhere in the paper for
   a shippable construct.

2. **Context-Based Earnings Persistence** (Section 6, Equation 2).
   Per-firm-year persistence parameter γ1 modeled as an ANN function
   of context vectors. Same unreleased-ML-model issue. **However**, the
   paper publishes (Table 9) the corresponding **OLS baseline**: yearly
   cross-sectional persistence regression `E_{t+1} = γ0 + γ1·E_t + ε`,
   reported per year 1998-2019 with average γ1 = 0.7738. The OLS
   baseline IS computable, and it is the paper's own benchmark for the
   ML version — so a skill that ships the OLS baseline + leaves a hook
   for the ML version is honest and useful. **However**, this requires
   a CROSS-SECTIONAL PANEL of firm-year observations to estimate γ1
   each year (paper uses ~3,000 firm-years per year). We have **5 firms
   × 2 years**. We can't run a meaningful cross-sectional regression on
   our MVP filing sample.

3. **Section 5.4 partition signals — "What contributes to contextuality?"**
   The paper partitions the sample on five economically-grounded
   signals to show WHEN narrative context is most valuable:
   (i) earnings volatility (Dichev-Tang 2009),
   (ii) extreme accruals (top 20% / bottom 20% per year, Sloan 1996),
   (iii) loss indicator (Hayn 1995),
   (iv) market-to-book ratio (Beaver-Ryan 2005),
   (v) firm-level political risk (Hassan et al. 2019).
   Table 7 Panel A establishes that contextuality is materially higher
   when each of (i)-(iii) signals "harder to value". Each signal is
   computable per firm-year from canonical line items + the existing
   market_data fixture. (v) requires a Hassan-et-al data source we
   don't have — drop. (i) needs ≥3 years for a defensible volatility
   estimate — degrade gracefully. (ii)-(iv) are computable on every
   MVP filing with prior-year data. **THIS IS THE SHIPPABLE CONSTRUCT.**

4. **Earnings-related-sentence extraction** (paper §IV / Kothari, Li,
   Short 2009 keyword list). Deterministic, easily computable. The
   paper uses this as a pre-processing step for the BERT model — it's
   not a standalone metric. As a standalone L1 fundamental skill it
   would be useful (an `extract_earnings_related_sentences` analog of
   `extract_mdna`), but it doesn't carry the paper's analytical
   contribution, only its pre-processing convention. **Defer to the
   future-candidates list** below.

**Decision: ship option 3 — `compute_context_importance_signals`.** It
emits the four firm-year signals from Table 7 Panel A that are
computable without an ML model, plus a composite **context_importance
score** (a 0-1 rating that aggregates the signals into a single number,
with explicit per-component weights derived from Table 7 Panel A's
reported t-statistics). Output flag: `context_critical`,
`context_helpful`, `context_marginal`, `indeterminate`. Citations back
to canonical line items + market data fixture. Per-component severity
bands governed by a rule template. Same per-paragraph trace shape as
the other paper-derived skills.

This is a NEW analytical layer in the catalogue. The other 8 skills
score firms on distress (Altman), manipulation (Beneish), narrative
structure (Upfrontedness). This skill scores firms on **how much the
narrative context should be expected to add to the numeric data** —
i.e. for a given filing, do we expect the MD&A to be especially
informative or not? It's a meta-signal that an agent might call BEFORE
deciding whether to invest in deep MD&A reading.

Options 1, 2, and 4 are deferred to the future-candidates list at the
bottom of this file.

## (b) What the paper/text offers that the current catalogue lacks

The current 8-skill catalogue (after Paper 1) has zero skills that
quantify **economic context** for a filing. Beneish/Altman/Upfrontedness
all describe the filing itself; none describes the *firm-circumstance*
in which the filing's narrative is being read. Kim & Nikolaev's §5.4
table is the cleanest published anchor for this concept: their five
partition variables collectively describe "is this firm's numeric
disclosure hard to interpret on its own?" Our skill ports four of the
five (drops political risk for data-source reasons) and bundles them
into a single callable metric.

Composability win: the score is a per-filing scalar plus a per-signal
trace, both of which downstream L4 composites can consume. A natural
composite would be: "if context_importance is high AND Upfrontedness
is low, the MD&A is being especially withheld in a setting where
context particularly matters" — a sharper red-flag than either signal
alone.

## (c) Formulas identified

**Section 5.4 partition signals (Table 7 Panel A descriptors)**:

The paper does NOT print closed-form formulas — these are conventional
operationalizations from the literature it cites. We adopt the standard
forms:

1. **Loss indicator** (Hayn 1995):
   `Loss_it = 1 if NetIncome_it < 0 else 0`
   Source: net_income canonical line item.

2. **Accruals magnitude** (Sloan 1996, "the difference between
   operating income and cash flows from operations"):
   `Accruals_it = (OperatingIncome_it − CashFromOps_it) / TotalAssets_it`
   We compute the absolute magnitude `|Accruals_it|` because the
   paper's "extreme accruals" partition takes top 20% AND bottom 20%
   (i.e. high magnitude in either direction).
   Source: ebit canonical line item, cash_flow_from_operations (NOT
   currently a canonical line item — see "implementation decisions"
   below for how we handle this).

3. **Earnings volatility proxy** (Dichev-Tang 2009 use std over a
   rolling window; we have only 2 years per firm):
   `EarningsVolatility_it = |NetIncome_it/Assets_it − NetIncome_{t-1}/Assets_{t-1}|`
   This is the absolute year-over-year change in ROA — a 2-period
   proxy for the multi-period volatility the paper uses. Documented as
   a proxy in `implementation_decisions`. Returns null when t-1 data
   are unavailable.

4. **Market-to-book ratio** (Beaver-Ryan 2005):
   `MTB_it = MarketValueOfEquity_it / BookValueOfEquity_it`
   where `BookValueOfEquity = TotalAssets − TotalLiabilities`.
   Source: market_data/equity_values.yaml (already used by Altman X4)
   + total_assets, total_liabilities canonical line items.

**Composite context_importance score:**

We aggregate the four signals into a single 0-1 score using fixed
weights derived from Table 7 Panel A's reported earnings-prediction
contextuality differences (column "Earnings", row "Diff"):

    Loss:                  Diff = 2.94, t-stat = 3.98
    Earnings Volatility:   Diff = 1.79, t-stat = 2.45
    Accruals (extreme):    Diff = 1.34, t-stat = 1.99
    Market-to-Book:        Diff = 1.50, t-stat = 2.13

These four are normalized into weights summing to 1.0:

    w_loss        = 2.94 / 7.57 = 0.388
    w_volatility  = 1.79 / 7.57 = 0.236
    w_accruals    = 1.34 / 7.57 = 0.177
    w_mtb         = 1.50 / 7.57 = 0.198

The score is a weighted sum of binary "signal is in top-quintile"
indicators against fixed paper-derived thresholds:

    context_importance = w_loss   · I[Loss = 1]
                       + w_vol    · I[EarningsVolatility ≥ paper_p80]
                       + w_accr   · I[|Accruals|         ≥ paper_p80]
                       + w_mtb    · I[MTB                ≥ paper_p80
                                  OR MTB                ≤ paper_p20]
                                  (M/B partitions on extremity, not direction)

The paper does not publish per-signal P80/P20 thresholds (the partitions
are computed within-year on the panel). For our MVP, we hard-code
plausible thresholds derived from common practitioner cutoffs:

    EarningsVolatility paper_p80 = 0.05  (a 5pp YoY ROA swing is "high")
    |Accruals|         paper_p80 = 0.10  (10% of assets is "extreme",
                                          consistent with Sloan 1996
                                          decile cutoffs)
    MTB                paper_p80 = 5.0   ("growth firm", per Beaver-
                                          Ryan 2005 conventions)
    MTB                paper_p20 = 0.8   ("value firm" / distressed)

These thresholds are documented in `implementation_decisions` and
made available in the rule template so an accounting expert can edit
without touching code.

## (d) Threshold values

**Per-component bands** (top-quintile indicator thresholds, see (c) above):

- Loss: binary (1 if net income < 0, else 0).
- Earnings volatility ≥ 0.05 ⇒ "high".
- |Accruals| ≥ 0.10 ⇒ "extreme".
- MTB ≥ 5.0 OR MTB ≤ 0.8 ⇒ "extreme valuation".

**Composite flag bands** (on context_importance score in [0, 1]):

- **context_critical** — score ≥ 0.60 (at least the loss signal + one
  other; or all three of vol/accruals/mtb on without loss).
- **context_helpful** — 0.30 ≤ score < 0.60 (one or two signals on).
- **context_marginal** — score < 0.30 (zero or one weakly-weighted
  signal on).
- **indeterminate** — when prior-year data unavailable AND market data
  unavailable (cannot compute volatility OR MTB).

The bands are paper-anchored in the sense that the WEIGHTS come from
Table 7 Panel A; the BANDS themselves are a presentation convention
(equally-spaced cuts at 0.30 and 0.60). Documented as a presentation
convention in the rule template, not represented as paper-exact.

## (e) Worked examples referenced in the text

The paper does not publish firm-year context_importance scores
(it publishes year-level averages in Table 7 Panel A — e.g. "Loss=1
firms have contextuality 7.95, Loss=0 firms have 5.01" for the
earnings target). These are aggregates over thousands of firm-years
per cell; they are not directly comparable to a single-firm score.

Replication strategy: the paper-replication test asserts
**signal-level paper-faithfulness** rather than score-mean matching:

1. **Loss-indicator faithfulness.** A net-income-negative fixture
   produces `loss = True`; a positive fixture produces `loss = False`.
   Trivial but explicit — guards against sign flips.
2. **Accruals-magnitude monotonicity.** A fixture with operating
   income > CFO produces positive accruals; reversed produces
   negative; zero difference produces ≈0.
3. **Volatility direction.** A constant-ROA fixture produces
   volatility ≈ 0. A ROA-swing fixture produces volatility = absolute
   delta. NULL when t-1 unavailable.
4. **MTB extremity** — a fixture with MTB = 6.0 hits the high band;
   MTB = 0.5 hits the low band; MTB = 2.0 sits typical.
5. **Composite-weight invariant.** When all four signals fire,
   score ≈ 1.0 (within float tolerance); when none fire, score = 0.0;
   when only Loss fires, score = w_loss = 0.388. This tests the
   weighted-sum implementation against the documented weights.
6. **Sample-firm sanity check (soft).** On the 5 MVP filings:
   - Apple FY2023: profitable, large, growth → expect
     `context_marginal` (Loss=0, MTB high but no other signals).
   - WorldCom FY2001: losses, distressed → expect
     `context_critical` (Loss=1 + extreme MTB likely).
   - Microsoft FY2023: profitable, large, growth → expect
     `context_marginal`.
   - Enron FY2000: profitable as reported, growth → expect
     `context_marginal` or `context_helpful`.
   - Carvana FY2022: losses → expect `context_critical` or
     `context_helpful`.
   The soft band is `score ∈ [0, 1]` and `flag != null` for all 5;
   no tighter expectations are encoded.

## (f) Implementation decisions

Documented in the manifest's `implementation_decisions[]`:

1. **The paper's headline ANN-based contextuality measure is NOT
   implemented.** The trained weights, hyperparameter seeds, and
   GPU-cluster setup needed to reproduce it are not released. The
   skill ships the four §5.4 partition signals (Table 7 Panel A) as
   the closest deterministically-computable proxy for "when does
   context matter?" An attention-model-backed variant is post-MVP
   future work.

2. **Two-period volatility proxy.** The paper uses Dichev-Tang
   (2009) earnings volatility, which is std(ROA) over a rolling
   window (typically 5 years). MVP has only 2 years per filing, so
   we use `|ROA_t − ROA_{t-1}|` as a documented 2-period proxy.
   Returns null when t-1 unavailable. Warning
   `volatility_two_period_proxy` on every non-null call.

3. **Cash flow from operations is NOT a canonical line item.** The
   accruals signal needs CFO; we currently have no canonical
   `cash_flow_from_operations` slot. Two options: (i) add a 17th
   canonical line item (out of MVP scope; needs mapping additions and
   manual-extraction-fixture updates for SGML filings), (ii) use a
   documented 16-canonical proxy. We pick (ii): use **EBIT − ΔWC** as
   a CFO proxy (where ΔWC = ΔCurrentAssets − ΔCurrentLiabilities).
   This is the standard "indirect method" reconstruction. Warning
   `accruals_cfo_proxy_used` on every non-null call. The full CFO line
   is filed as a future canonical-line-item expansion.

4. **Political risk signal (Hassan et al. 2019) is dropped.** The
   underlying data set is not in our store and is not freely
   reproducible from 10-K text alone. The paper's §5.4 reports
   Diff = 2.08 for Earnings on this signal — comparable to MTB and
   higher than vol/accruals. Dropping it changes the weight
   normalization (we re-normalize across the four kept signals), which
   we document explicitly.

5. **Per-component thresholds are practitioner-derived, not
   paper-published.** The paper's partitions are computed within-year
   on the panel; we use fixed thresholds that approximate the
   conventional 80th/20th percentile cutoffs in the literature
   (Sloan 1996; Beaver-Ryan 2005). Documented in the rule template,
   editable by an accounting expert.

6. **Indeterminate when both volatility AND MTB cannot be computed.**
   If a filing has no prior year data AND no market data, the score is
   underdetermined — we return score=null, flag=indeterminate. If only
   one is missing, we still produce a score by assuming the missing
   signal is "off" (conservative — under-counts context importance);
   this is documented.

7. **Composes existing skills via canonical statements.** Reads
   canonical statements via `build_canonical_statements` (same as
   Beneish/Altman) and market data via `equity_values.yaml`. Does NOT
   delegate to any sub-skill via the registry — there is no
   sub-skill that returns the four partition signals separately.

## (g) Limitations (goes into manifest `limitations[]`)

- The paper's headline contextuality measure (BERT + ANN accuracy
  delta) is post-MVP. The four §5.4 partition signals are paper-
  grounded but are NOT the same construct — they tell you WHEN
  context tends to matter, not how much it actually adds in this
  specific filing.
- Two-period volatility is a coarse proxy for the paper's multi-year
  Dichev-Tang volatility. The proxy systematically under-reports
  volatility for firms whose ROA happens to be similar in t and t-1
  but variable over a longer horizon.
- Accruals uses an indirect-method CFO reconstruction (EBIT −ΔWC)
  rather than the reported CFO line. Drift versus the reported value
  is typically <2% of assets but can be material for firms with large
  non-cash items (deferred tax, stock comp, asset impairments).
- Pre-iXBRL filings (Enron, WorldCom) carry the standard
  `pre_ixbrl_manual_extraction` confidence penalty (−0.15) per the
  established skill convention.
- Per-component thresholds (P80/P20) are practitioner-derived
  defaults, not paper-published. They are editable in the rule
  template, but a population-anchored alternative would be cleaner.
- Not a context-quality verdict. A `context_critical` flag means the
  paper predicts CONTEXT WOULD HELP for this firm, not that the
  firm's actual MD&A succeeds at providing it. Pair with
  `compute_mdna_upfrontedness` for the structure-of-narrative axis.

## (h) What I leveraged from Paper 1's workshop deliverables, and what I improved

**What I used:**
- `workshop/paper_to_skill/extract_paper.py` — ran on Paper 2 first.
  Returned page_count=47, an excellent TOC parse, and the PDF
  sha256 (`013d9bb…`). Saved ~5 minutes of manual paging.
- `workshop/paper_to_skill/notes/fundamentals_text.md` shape — same
  (a)..(g) section structure.
- `workshop/docs/paper_onboarding_playbook.md` "unreleased ML model"
  callout — this paper hit exactly that branch, and the callout
  saved me from re-litigating "do we re-train BERT?" for the Nth
  time. I extended it with a NEW callout (see below) about what to
  do when there's no honest proxy AT ALL (the deeper case).
- `mvp/skills/paper_derived/compute_mdna_upfrontedness/manifest.yaml`
  shape and `skill.py` patterns — adopted the indeterminate-output,
  warnings, confidence, and provenance dict shapes.
- `mvp/ingestion/papers_ingest.py:ingest_local_paper` — used
  unchanged. The `LocalPaperRef` registration pattern Paper 1 set up
  is now the standard for every `paper_examples/` paper.

**What I improved (workshop deltas, Paper 2):**
- `workshop/paper_to_skill/extract_paper.py` — extended the formula
  detector. Paper 1 only needed `Equation N` and basic linear-
  combination patterns. This paper has Equations (1), (2), (3), (4)
  in **parenthesized** form (Wiley J of Accounting Research style)
  and references like "ﬁgure 1(a)" / "table 7, panel A" / "online
  appendix table OA-2". Added two new patterns: `equation_paren`
  (`(\d+)` style) and `numbered_table_or_figure` (caught the dozens
  of table/figure references this paper uses for cross-referencing).
  Paper 1 produced 0 hits — the new patterns get us to ~50 hits on
  this paper, a useful spot-check for "did the methodologist read
  the right tables?"
- `workshop/paper_to_skill/extract_paper.py` — added a
  `--journal-format` heuristic that detects the Wiley
  "Downloaded from https://onlinelibrary.wiley.com/" footer signature
  and automatically strips it from snippets, so detected formulas in
  journal-format PDFs don't carry 200 chars of legal-notice noise.
  Paper 1 was a working paper with no journal footer — this gap
  appeared the moment Paper 2 landed.
- `workshop/paper_to_skill/extract_paper.py` — added a small
  `top_toc_sections()` helper that returns just the level-2 TOC
  entries. This paper's TOC is rich enough (8 main sections, 18
  subsections) that the methodologist needs to scan it
  programmatically, not by eyeball.
- `workshop/docs/paper_onboarding_playbook.md` — added a NEW callout
  titled **"When the unreleased ML model has NO honest proxy: drop
  the model-based skill and look elsewhere in the paper."** Paper 1
  found a defensible length-share proxy for the BERT attention
  weights. Paper 2 has NO defensible proxy (an ANN's accuracy delta
  has no closed-form approximation), so the lesson is: in that case,
  scan the paper for other constructs that ARE deterministically
  computable. §5.4 partition signals were the right find here.
- `mvp/ingestion/papers_ingest.py` — added a `LocalPaperRef` entry
  for `kim_2024_context_based_interpretation` (the second
  `paper_examples/` corpus paper to land). Used the same Paper 1
  pattern; now we have two examples of how to register a
  `paper_examples/` paper, which makes Paper 3's job easier.

## Candidates for future papers

This paper yields three plausible deferred skills, each its own
paper-to-skill cycle:

1. **`compute_earnings_persistence_ols`** — L3 paper-derived. Implements
   the OLS baseline of Section 6 (Table 9 column 1) — yearly
   cross-sectional regression `E_{t+1} = γ0 + γ1·E_t + ε`. Requires
   a panel of firm-year observations, which we don't have at MVP
   scope (5 firms × 2 years). When the MVP issuer set expands to a
   wider panel (year 2 roadmap), this becomes shippable.
2. **`extract_earnings_related_sentences`** — L1 fundamental. Applies
   the Kothari-Li-Short (2009) keyword list (net income, profit,
   earnings, etc.) to MD&A text; returns the matched sentences plus
   one sentence of context on each side (per paper §IV). Useful as
   pre-processing for any narrative-analytics skill (including the
   future ML version of contextuality). Ships small, useful, and
   composable.
3. **`compute_contextuality_ml`** — L3 paper-derived (post-MVP).
   The full BERT+ANN contextuality measure. Requires GPU
   infrastructure, a trained model checkpoint, and a Compustat
   panel. Filed as a year-2 candidate for when we have a model
   training pipeline.

All three deferred because: (a) the four §5.4 signals are the
sharpest single per-firm-year construct this paper offers without
ML infrastructure, (b) the playbook's "ship ONE per iteration" rule
holds, (c) the 8→9 skill increment plus the new context-importance
axis is dual-growth-sufficient for this iteration.
