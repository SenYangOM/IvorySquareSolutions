# 10 — Roadmap and Coverage Plan

**Coverage scales by orders of magnitude on a documented quality-bar curve. Skill library scales by the documented paper-onboarding playbook (5 papers / 5 days proven). Multi-jurisdiction and adjacent-domain expansion are explicit Year 2-3 commitments, not Year 1 promises.**

---

## Coverage universe — by tier and quality bar

| Horizon | Issuer count | Quality bar | Notes |
|---|---:|---|---|
| MVP today | 5 | Audit-grade — every claim cited, eval gates green | Manually curated 5-issuer corpus to span positives, negatives, ambiguous; canonical demo run on Enron 2000. |
| Near-term (3 months post-MVP) | 50 | Audit-grade for iXBRL-era filings; pre-iXBRL flagged | All 5-issuer skills run against 50 large-cap US issuers; gold-standard expansion to 50+ cases unlocks confidence calibration. |
| 12-month | 500 | Audit-grade for iXBRL-era; data-quality flags for edge cases | S&P 500 coverage with daily refresh on new filings; design-partner usage shapes which constructs to add. |
| 24-month | 2,000+ | Audit-grade for iXBRL-era; documented approximation paths for edge cases | US large/mid-cap full coverage. |

**Caveats at each tier:** Pre-iXBRL filings (Enron, WorldCom era) require manual SGML extraction; this scales for tens of issuers, not thousands. Foreign filers using 20-F / 40-F have different statement structures. Some industries (banks, insurance, REITs) have specialized statement schemas that need their own canonical mapping. Each of these is a known gotcha with a documented path; none are surprises.

---

## Skill library roadmap

The post-MVP paper-onboarding loop (see §08) shipped 5 new skills in 5 days at a 50% wall-clock reduction across the corpus. Continuing at the *steady-state* end of that curve (~105 minutes per paper):

- **Next 6 months:** 15-25 additional paper-derived skills. Likely areas, drawing from the deferred-candidates lists in `workshop/paper_to_skill/notes/<paper>.md`:
  - **Revenue quality.** Modified Jones discretionary accruals; Sloan accruals anomaly; revenue-recognition policy-change diffing.
  - **Accruals quality.** Dechow-Dichev accruals quality; abnormal working-capital accruals.
  - **Disclosure quality.** Loughran-McDonald (2011) tone dictionaries on 10-K text; Bonsall-Leone-Miller readability; risk-factor diff-and-categorize.
  - **Textual-analysis.** MD&A topic distribution (Kim et al. 2024 Appendix E taxonomy); item-importance ranking; earnings-related sentence extraction.
  - **Factor loadings.** Fama-French exposure estimation from filings + market data.
- **12-month targets:**
  - First multi-jurisdiction skill: an IFRS canonical-statement extractor for a small set of large-cap European filers.
  - First transcript-consuming skill (requires earnings-call transcript ingestion).
  - First 8-K-watcher skill (requires 8-K real-time monitoring with structured event classification).

---

## Long-term skill domains (Year 2-3, explicitly deferred)

The same architecture — declarative rule set + interpretation engine + agent-callable skill endpoints — generalizes naturally beyond accounting interpretation. These are roadmap, not near-term promises:

- **Corporate finance and capital markets.** Capital-structure analysis, payout policy, M&A accretion/dilution mechanics, valuation construct implementations from the academic literature (implied cost of capital, residual income models, abnormal-returns frameworks).
- **Quantitative finance.** Risk decomposition, factor-exposure analysis, signal construction from filings and transcripts (text-based factors), regime detection — implementations of published methodologies, callable as skills.
- **Economics.** Industry-level analysis, macroeconomic exposure mapping, policy-impact analysis using published econ frameworks (trade exposure indices, economic policy uncertainty indices, supply-chain pass-through).
- **Operations research.** Supply-chain risk decomposition, working-capital optimization frameworks, capacity / utilization modeling — operational interpretation rather than purely financial.
- **Quantitative marketing.** Customer-base disclosures, ARR / cohort decomposition where disclosed, brand-asset and customer-asset analysis from published marketing-academic methodologies.

Each vector is its own vertical slice and its own domain-expert hire (a quant-finance PhD, an economist, an OR researcher, a quant-marketing PhD). Premature expansion before the accounting wedge is established would fragment the team and dilute the brand. The discipline mirrors the GPT-Rosalind precedent: even at frontier-lab scale, OpenAI shipped life sciences only — not "all of science" — and earned the right to broaden by first doing one domain visibly well.

The strategic prize, if executed: a complete library of paper-derived analytical skills callable by any AI agent, becoming the **interpretation infrastructure** for finance, economics, and adjacent domains — analogous to what Intex Solutions is for structured-credit analytics, but spanning every quantifiable lens an academic literature has produced. Each skill implemented once, versioned, reused at scale; users (and their AI assistants) compose them rather than re-implementing methodologies in-house.

---

## Gotchas already priced in

The MVP build process surfaced several real-world frictions, each with a documented mitigation path:

- **Restatement-aware versioning** is logged today (`data/standardize_restatement_log.jsonl`), but auto-rerun of upstream skills on restatement is post-MVP. The L1/L2 separation makes this addable without breaking existing outputs.
- **Pre-iXBRL filings** (anything before ~2009 in our corpus, including Enron 2000 and WorldCom 2001) require manual SGML extraction. The `data/manual_extractions/<cik>/<accession>.yaml` fixtures handle the MVP corpus; a tooling investment is needed before this scales past a few dozen historical filings.
- **Confidence calibration** is documented but uncalibrated at MVP — it requires ≥50 gold cases per skill. With current 5-issuer × 12-skill coverage we have 15 gold cases total. Calibration unlocks at the 50-issuer tier.
- **Industry-specific statement structures** (banks, insurance, REITs) need additional canonical mappings beyond the 16 line items the MVP supports. Each industry adds ~5-8 line items and some statement-role-naming aliases.
- **Transcript ingestion** is out of MVP scope and a real moat to add (transcript licensing economics differ from EDGAR's free-public-data substrate). One transcript-consuming skill is on the 12-month plan.
- **Foreign filers (20-F / 40-F).** Different statement structures than 10-K; broader IFRS rule set. The first IFRS canonical extractor is a 12-month milestone gating multi-jurisdiction work.

None of these gotchas are existential. All are known-known. Each has a sequencing discussion in `mvp_build_goal.md` §14 (out-of-scope) and a path to addressability that does not require re-architecting the L0-L4 substrate.

---

## What we are *not* doing

To avoid scope drift, three categories of feature requests are explicitly off the Year 1 roadmap:

- **No buy/sell signal product.** The skills surface judgment, not alpha. Quant funds compose the skills into signals on their own.
- **No retail / consumer chatbot.** The user is an agent (P3); the consumer surface, if it ever ships, is downstream of agents that integrate our catalog.
- **No proprietary research publication.** We are infrastructure for analysts, not a competitor to analysts. Sell-side research and AlphaSense-style insight feeds are out of scope.

The discipline pays off in two ways: it keeps the team small and focused; it keeps the buyer conversation simple ("we are the substrate, not the conclusion-maker").
