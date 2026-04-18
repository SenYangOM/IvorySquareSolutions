# Paper-onboarding playbook

This is the long-form companion to
[`../paper_to_skill/README.md`](../paper_to_skill/README.md). The README
there is the compact checklist; this document is the war-story version. Read
both — the checklist tells you what to do, the playbook tells you what
happens if you do it wrong.

Audience: the `quant_finance_methodologist` persona, or the human taking
that role. Expected reading time: <20 minutes.

---

## Overview

At MVP we onboarded two papers end-to-end — Beneish (1999) and Altman (1968)
— as part of Phase 3 (rule-template authoring) and Phase 4 (skill
implementation). The process produced eight lessons the next five papers
(under `paper_examples/`) will run into. This document records them so a
future contributor — or a future Claude subagent resuming the work — doesn't
re-discover each lesson from scratch.

The playbook assumes you've already read:

- `mvp_build_goal.md` §3 (why Beneish + Altman), §6 (skill-manifest schema),
  §7 (skill layering), §15 (the workshop vs mvp contract).
- `success_criteria.md` §4 (quality acceptance), §13 (workshop scope).
- `CLAUDE.md` §"Operating principles" (P1 / P2 / P3).
- `mvp/human_layer/rule_authoring_guide.md` and
  `mvp/human_layer/gold_authoring_guide.md`.
- `../paper_to_skill/README.md` (the compact checklist).

---

## The playbook in prose

### The paper is the source of truth. Secondary references are not.

Every paper-derived skill has exactly ONE authoritative source: the paper
itself. Textbooks, teaching notes, Wikipedia, and "what everyone knows about
the Beneish M-score" are secondary. When they disagree with the paper, the
paper wins. When they appear to agree with the paper but round a
coefficient, the paper still wins — the rounding is usually where the
disagreement started.

We learned this the hard way on Beneish. The 1999 paper prints -1.78 as the
optimal classification threshold at the 20:1 / 30:1 relative-error-cost
regimes reported in Table 5. Secondary sources (including an early draft of
`mvp_build_goal.md` §3/§6) say -2.22. The -2.22 comes from Beneish, Lee &
Nichols (2013) — a follow-on paper with a different estimation sample. For
a while we had -2.22 wired into both the skill and the rule template,
because "everyone says -2.22." When a Phase 3 research pass sent someone
back to the original PDF, -1.78 turned up on page 16. We corrected it,
wrote a focused regression test
(`tests/unit/rules/test_beneish_threshold_is_1978.py`), and documented the
deviation in the rule template's `m_score_threshold.notes` block.

**The rule now is: implement what your paper says. If you read -2.22 in a
textbook, open the paper and check the page. If the paper says -1.78, ship
-1.78. Secondary sources become an audit trail, not a ground truth.**

### Round coefficients only when the paper rounds.

Altman's 1968 paper, Equation I, p. 597: `0.012·X1 + 0.014·X2 + 0.033·X3 +
0.006·X4 + 0.999·X5`. Every textbook reference you will find rounds X5 to
1.0. Most of them round the others to their practitioner form (1.2·X1 +
1.4·X2 + 3.3·X3 + 0.6·X4 + X5). The practitioner form is algebraically
equivalent when X1–X4 are entered as percentages and X5 as a decimal — but
the rounding of 0.999 to 1.0 is **not** algebraic; it is a textbook
convention that has drifted across editions.

We ship 0.999. The drift from using 1.0 would be 0.001 × X5, typically
<0.003, and would have no observable effect on the §4.2 ±0.10 eval
tolerance. We still ship 0.999 because:

1. It's what the paper says.
2. The discipline of matching the paper exactly is what lets a reviewer
   spot-check our implementation against the PDF in <30 minutes
   (`success_criteria.md` §6).
3. If we round one coefficient because "it's close enough," we will round
   the next one for the same reason, and we will eventually ship a skill
   whose error isn't "close enough" and not notice why.

A focused regression test (`test_altman_x5_is_0999.py`) guards the
coefficient.

### Approximation is acceptable; hiding approximation is not.

Beneish's TATA component ("total accruals to total assets") is defined in
the paper as the full working-capital accrual formula that subtracts
ΔCash, ΔCurrent Maturities of LTD, and ΔIncome Tax Payable from the
current-asset / current-liability delta. Two of those three line items (Δ
CMLTD and ΔITP) are NOT in the 16 canonical line items we standardize at
MVP. We had three options:

1. **Expand the canonical line-item set.** Good long-term answer;
   infeasible at MVP because it would have ripple-effected the mappings,
   the standardize tests, and the manual extractions for Enron and
   WorldCom.
2. **Zero-impute.** Silently substitute 0 for the missing deltas. Tempting
   because it's one line of code. Forbidden because P2 rules out silent
   imputation: a downstream analyst reading M=−1.89 cannot tell whether
   TATA used the paper-exact formula or dropped two terms.
3. **Ship the 16-canonical approximation with a warning.** This is what we
   did. Every call to `compute_beneish_m_score` emits
   `warning=tata_approximation` in the output. The manifest's
   `implementation_decisions` block documents the decision. The rule
   template's TATA `contextual_caveats` explain the consequence.

WorldCom paid the visible price. WorldCom's fraud (capitalizing line costs
as capex) inflates accruals materially, and the dropped Δ CMLTD term is
correlated with that fraud signal. Our TATA approximation shifts WorldCom's
M-score by about 0.23, moving it from `manipulator_likely` (paper-exact) to
`manipulator_unlikely` (our approximation). The eval encodes the gold
against the paper-exact expected value; the runner flags the case as an
`explainable_failure`. We did NOT rescue the failure by loosening gold —
that would hide the approximation. We surface it honestly.

**The rule is: if you must approximate, document it in
`implementation_decisions`, surface it as a runtime warning, and let the
eval fail honestly on cases where the approximation matters.**

### Null is a first-class output, not an exception to handle.

Carvana's FY2022 10-K does not tag an `OperatingIncomeLoss` concept in its
iXBRL. Our `standardize.build_canonical_statements` returns
`ebit: null`. Altman's X3 is `EBIT / total_assets`. `null / anything` is
null. Z is `0.033 × X3 + ...`; `null` propagates through.

The wrong response: raise an exception, log an error, or impute EBIT from
revenue. All three hide the gap.

The right response: return `z_score: null`, `flag: "indeterminate"`, a
warning `ebit_not_available`, and a confidence of 0.0. The downstream
caller (agent or human) knows we couldn't score it and why. Interpretation
skills (`interpret_z_score_components`) produce interpretations only for
the components that are populated; the X3 slot reads "component not
available — EBIT concept not tagged in the filing." The composite returns
`flag: indeterminate` at the top level.

This behavior is encoded in gold: `carvana_2022_altman.yaml` expects
`expected.score.value: null` + `expected.flag.value: "indeterminate"`; the
runner has null-matches-null semantics. The case counts as passing because
the skill honestly reported what the data supports.

**The rule is: plumbed-through null is always preferable to a silently
imputed value or a crash. Every skill's `indeterminate` path is as
well-tested as its happy path.**

### Citations for fixture data use an extended locator scheme.

Altman's X4 requires market value of equity, which is not in any 10-K line
item. MVE comes from the engineering-owned fixture at
`data/market_data/equity_values.yaml`. The fixture has 5 entries (one per
MVP issuer) with columns for shares outstanding, price per share at
fiscal-year-end, and the implied MVE, plus a `market_cap_source` field
with free-text provenance.

The citation locator for a fixture-sourced value extends the standard
`<cik>/<accession>::<role>::<line_item>` scheme to
`market_data::<cik>::<fye>`. The `engine.citation_validator.resolve_citation`
function knows both schemes; `POST /v1/resolve_citation` and
`mvp resolve-citation` route to the same resolver.

Any future paper that requires exogenous inputs will follow the same
pattern: the fixture lives under `data/<kind>/`, the locator prefix names
the fixture, the resolver knows both the filing scheme and the fixture
scheme. Don't invent a new citation shape per paper — extend the existing
locator vocabulary.

### SGML-era filings take an extraction fallback.

Enron FY1999, Enron FY2000, WorldCom FY2000, WorldCom FY2001 are all
pre-iXBRL SGML filings (the `.txt` submission format that predates iXBRL
adoption ca. 2009). The companyfacts JSON pipeline that handles our three
iXBRL issuers (Apple, Microsoft, Carvana) does not work for these four
filings — the facts simply don't exist in EDGAR's structured-data store.

We ship a manual-extraction fallback: YAML files at
`data/manual_extractions/<cik>/<accession>.yaml`, one per SGML filing.
Each file is a hand-authored table of 16 canonical line items with
`source_excerpt` strings (verbatim from the SGML text) and
`excerpt_hash = sha256(normalize_excerpt_for_hash(excerpt))`. The
`facts_store.get_facts()` function routes pre-iXBRL accessions to the
manual-extraction reader; every other filing goes through companyfacts.

The data-quality tax shows up everywhere downstream: every line item
consumed from a manual-extraction YAML drops the skill's confidence by
0.1 (clamped at 0). The `data_quality_flag: pre_ixbrl_sgml` surfaces in
the filing's `meta.json` and in every output's `warnings` block.

**The rule is: for any filing predating iXBRL, authorizing a manual
extraction is part of the onboarding cost. Don't try to auto-parse the
SGML — the format is too variable. Write the YAML, pin the excerpt hashes,
and flag confidence accordingly.**

### Idempotence is a contract, not a nice-to-have.

Every ingester (`ingest_filing`, `ingest_paper`) rehashes its on-disk
target on every call. A cache hit appends a
`filing_ingested_skipped_already_ingested` (or `paper_ingested_skipped_...`)
event to `data/manifest.jsonl` and returns the existing record. A hash
mismatch raises `IngestionError(reason="hash_mismatch")` — never silently
re-downloads.

Why this matters for paper onboarding: you will `ingest_paper` a dozen
times during a paper-onboarding session. Some of those times the PDF will
silently change on the mirror (calctopia.com has done this at least once).
We want a loud `expected_hash_mismatch` on those occasions, not a silent
update. The sha256 pin is recorded in the manifest's provenance block at
first ingestion; subsequent calls verify against it.

**The rule is: treat idempotence and hash-pinning as a trust contract with
the future maintainer. They should be able to `rm -rf data/papers &&
ingest_paper` and know that the re-ingested bytes are identical to what the
skill was built against.**

### Registry auto-discovery means the skill is self-registering.

`mvp/skills/registry.py` walks `mvp/skills/**/manifest.yaml` on first
access, loads each manifest via `SkillManifest.load_from_yaml()`, validates
it in strict mode, and caches the result. A new skill appears in the
catalog the moment its `manifest.yaml` is a valid, strict-validating
instance of the schema.

Corollary 1: a skill with a broken manifest is invisible to the CLI, the
API, the MCP catalog, the OpenAI catalog, and every composite. No error
message — just "this skill doesn't exist." The remedy is to load the
manifest directly in a REPL and read the pydantic error.

Corollary 2: you never register a skill manually. There is no
`register_skill(...)` call. If you find yourself wanting one, something is
wrong — the skill either isn't in `mvp/skills/<layer>/<id>/manifest.yaml`
or the manifest doesn't validate.

Corollary 3: the registry is the single seam. Composite skills
(`analyze_for_red_flags`) call sub-skills via
`default_registry().get(skill_id).run(inputs)`, not via direct Python
imports of `ComputeBeneishMScore`. That indirection is what lets CLI and
API share exactly one dispatch path.

### Determinism via templated substitution (no LLM in shipped skills).

The MVP's L2 interpretation skills (`interpret_m_score_components`,
`interpret_z_score_components`) are **deterministic**, not LLM-powered.
They look up the component's severity band in the rule template's
`interpretation_rules[]`, substitute the component's numeric value into
the template's `interpretation` string, and return the result. No
anthropic API call, no temperature, no non-determinism.

This was a scope choice. A naive implementation would pass the component
values + the rule-template's interpretation text to Claude and ask for a
more natural rewrite. We didn't, because:

1. Determinism is contract (`success_criteria.md` §4.4). Two runs with
   identical inputs produce byte-identical outputs modulo timestamps —
   `test_cli_api_parity.py` enforces this on all 7 skills.
2. The rule template's interpretation strings ARE the accountant's voice.
   Re-writing them through an LLM would dilute the voice, not refine it.
3. LLM calls introduce cost, latency, and API-key dependencies at the
   skill layer. Those belong behind the subagent persona boundary, not
   inside a shipped skill.

A future skill that legitimately needs LLM reasoning (e.g., extracting a
specific disclosure from free-form MD&A text) can consume an LLM via
`mvp.lib.llm.call_cached`, which provides caching + retries. But don't
reach for it by default — determinism through the rule template is the
more valuable property.

### When the unreleased ML model has NO honest proxy: drop the model-based skill and look elsewhere in the paper.

*Added during paper 2 onboarding (`paper_examples/J of Accounting
Research - 2024 - KIM - Context-Based Interpretation of Financial
Information.pdf`: Kim & Nikolaev 2024).*

This is the deeper, more uncomfortable cousin of the previous
callout. Paper 1 (Kim et al. 2024 "Learning Fundamentals from Text")
landed on the lucky end of the "unreleased ML model" spectrum —
its Equation 9 had a defensible length-share proxy that preserved
the paper's economic signal. The proxy-with-documentation route
worked.

Paper 2 sits on the other end. Kim & Nikolaev (2024)'s headline
construct is the **accuracy delta between a fully-connected and a
partially-connected ANN**, both fed BERT-encoded MD&As + numeric
inputs. That's a full deep-learning training pipeline:

- 138,129 BERT-encoded MD&As (5× Tesla V100 32GB GPUs in the paper);
- 30 random restarts × 22 yearly training windows × 4 target
  variables × 2 model variants ≈ 5,000 ANN training runs;
- A trained-model checkpoint that the authors did not release;
- Compustat panel + CRSP returns + 4-year lags per firm-year.

There is **no closed-form proxy that approximates an ANN's accuracy
delta**. Length-share doesn't work here — the paper's construct is
not a weighted average of position scores or any other arithmetic
shape. The "ship the equation + a documented proxy" lesson does NOT
generalise to this case.

**The rule that generalises: when the unreleased ML model is the
whole point AND no honest proxy exists, drop the model-based skill
and scan the paper for a different deterministically-computable
construct that captures a related economic question.** Don't dress
up a low-power workaround as the paper's headline metric — that
fails the reviewability bar (`success_criteria.md` §6) on first
reading and is a P2 violation by construction.

For Kim & Nikolaev (2024) the alternative was Section 5.4 / Table 7
Panel A — the **partition signals** the paper uses to show WHEN
context matters most (loss indicator, earnings volatility, extreme
accruals, market-to-book extremity, political risk). Each signal is
deterministically computable from canonical line items + the
existing market-data fixture, and the paper publishes per-signal
contextuality differences (column "Earnings", row "Diff": 2.94 /
1.79 / 1.34 / 1.50 / 2.08) that we adopt as relative weights in a
composite. The skill (`compute_context_importance_signals`) ships as
a meta-signal — "for this firm-year, does the paper predict context
should especially help?" — rather than as a stand-in for the paper's
unreproducible ANN delta.

The shipped skill is honest about what it is and is not:

- **Manifest's `description_for_llm` and `interpretation_guide`
  explicitly say** the score is NOT the paper's ANN accuracy delta
  and that the paper's headline measure is not implemented.
- **Per-signal warnings** (`loss_indicator_uses_ebit_proxy`,
  `volatility_two_period_proxy`) surface every place we substituted
  a canonical-line-item proxy for the paper's exact construct.
- **The dropped political-risk signal** is documented in
  `implementation_decisions[3]` with the original Diff (2.08) and
  the re-normalisation arithmetic, so a future expansion knows
  where to put the weight back.
- **Confidence is capped at 0.7** while the loss-EBIT and
  2-period-volatility proxies are active.
- **The composite-score bands (0.30, 0.60) are explicitly labelled
  a presentation convention, NOT paper thresholds.** A future
  paper-specific calibration on a wider issuer panel would replace
  the presentation cuts with population-anchored quantiles.

The decision-tree generalisation for future papers:

1. Is the paper's headline a closed-form formula? → Ship it
   (Beneish, Altman pattern).
2. Is the headline an ML model with a defensible closed-form proxy?
   → Ship the equation with the documented proxy + warning + confidence
   ceiling (Kim et al. 2024 Equation 9 / Upfrontedness pattern).
3. Is the headline an ML model with NO closed-form proxy? → **Don't
   ship a fake-equation surrogate.** Scan for a deterministic
   construct elsewhere in the paper (the partition variables, an
   appendix descriptive statistic, an OLS baseline) and ship THAT
   with explicit "not the headline measure" framing. Kim & Nikolaev
   2024 is the prototype for branch 3.

If a paper has nothing in branch 1, 2, or 3 — escalate to the user.
"This paper doesn't yield a skill" violates the dual-growth
directive's mvp-must-grow rule by construction.

*Operational side-note (paper 2).* Two workshop-tooling
improvements landed on this iteration:

- **`workshop/paper_to_skill/extract_paper.py` hardening for
  journal PDFs.** Paper 1 was a working paper with no Wiley footer
  and no parenthesized equation labels. Paper 2 has both — the
  J. Accounting Research style displays equations as `equation,  (3)`
  at end-of-line and decorates every page with a "Downloaded from
  https://onlinelibrary.wiley.com/..." footer. We added a new
  `equation_paren_label` formula pattern (matches the EOL-anchored
  `(N)` form), a `numbered_table_or_figure` cross-reference pattern
  (matches "table 7", "ﬁgure 1(a)", "appendix table OA-2"), a
  `_strip_journal_footers` page-text preprocessor (no-op for working
  papers, removes the Wiley signature on journal copies), and a
  `top_toc_sections` helper that filters TOC entries to the top N
  levels (paper 2's TOC has 26 entries across 4 levels — eyeballing
  it all is wasteful). Paper-2 hit-counts for the new patterns:
  ~57 paren-equation + ~57 table/figure references; paper 1 hit 0
  on both (and was unaffected by the hardening — verified by a
  regression test in `workshop/tests/test_extract_paper.py`).

- **The methodologist notes section `(h)` template addition.** Paper
  2's notes file added a new section `(h) What I leveraged from
  Paper 1's workshop deliverables, and what I improved` — explicitly
  bookkeeping the workshop-tooling delta against the prior paper.
  Paper 3 should follow the same shape: every paper's notes file
  records what carried over from the previous paper and what
  Paper N hardened. By Paper 5 this trail should make it obvious
  that the workshop tooling matured.

### When the paper's core construct is an unreleased ML model, ship the equation + a documented proxy.

*Added during paper 1 onboarding (`paper_examples/fundamentals_text.pdf`:
Kim, Muhn, Nikolaev & Zhang 2024, "Learning Fundamentals from Text").*

Some papers' headline contribution is a trained model that the authors
did not release publicly. Kim et al. (2024) is the prototype case —
the paper's attention-based paragraph-importance ML model was trained
over 20 million 10-K paragraphs with OpenAI `text-embedding-3-large`
features + a two-layer Transformer + 19 years of CRSP/Compustat
supervision. Re-training it is flatly infeasible at MVP scope, and
even at non-MVP scope would not reproduce the paper's specific
outputs — the training data is proprietary.

We faced this choice for the paper's firm-level Upfrontedness
measure (Equation 9). The equation itself is
`Σ_k [(1 − rank_k/N) × Paragraph_Importance_k]` — a weighted average of
position scores. The question was: what do we use for
`Paragraph_Importance_k`?

Three options:

1. **Drop the skill.** The paper's core contribution is the attention
   model we can't replicate; ship nothing. Rejected — the paper still
   offers a measurable textual-structure construct even without the
   model. And the dual-growth directive requires at least one shipped
   skill per paper.
2. **Re-train the attention model at reduced scope.** The training
   budget alone is beyond MVP's envelope. Rejected. The more subtle
   problem: a 5-filing-sample re-trained model would produce
   statistically meaningless weights that we would then dress up as
   "paper-faithful." That is dishonest and would fail the
   reviewability bar (§6) on first reading.
3. **Ship Equation 9 with a documented proxy for
   `Paragraph_Importance_k`** and surface the approximation at every
   layer. This is what we did. The proxy is length-share
   (`length_k / total_length`), which is a defensible stand-in
   (Bushee-Gow-Taylor 2018; Cohen-Malloy-Nguyen 2020) — longer
   paragraphs carry more information on average — and it's the
   minimum non-trivial choice (uniform importance makes the equation
   collapse to a constant).

The proxy-with-documentation approach succeeded because we applied
the SAME rigour that applies to a paper-exact implementation:

- **The manifest's `implementation_decisions[0]` is the longest one
  in the skill** — 8 sentences explaining why the proxy exists, what
  it preserves (the paper's economic signal: long paragraphs at the
  front raise the score), what it does NOT preserve (the paper's
  attention-model-derived importance distribution), and where the
  future work to replace it is tracked.
- **Every non-null call emits
  `warning=paragraph_importance_proxy_used`**. An agent consuming
  the skill output cannot miss the approximation.
- **The paper-replication test asserts equation-level faithfulness**,
  not distribution-mean matching. It has six assertions covering the
  closed-form uniform-length baseline (`(N-1)/(2N)` to within 1e-10),
  the directionality of monotone-decreasing vs monotone-increasing
  constructions, the [0, 1] range coverage on degenerate cases, and
  a generous [0.40, 0.55] soft band on the 4 scorable MVP filings.
  The ±0.05 paper-replication tolerance from `success_criteria.md`
  §4.1 cannot apply directly — the proxy's mean legitimately differs
  from the paper's model mean — so the tolerance shape is replaced
  honestly rather than loosened silently.
- **The skill's confidence is capped at 0.7** while the proxy is
  active. A future attention-model-backed variant can raise the cap;
  until then, callers see that 0.3 of the confidence budget is held
  back because of the approximation.
- **The candidates list in
  `workshop/paper_to_skill/notes/fundamentals_text.md` §"Candidates
  for future papers"** tracks two additional skills (topic
  distribution, item importance ranking) this paper can yield, so
  the deferred work has a home.

The rule that generalises: when a paper's construct depends on a
non-public model, document the dependency as a proxy, surface it at
every layer (warning, confidence ceiling, manifest decisions,
limitations), and cap your replication tolerance to what the proxy
actually supports. Don't reach for the model-free version of the
construct if the model is the whole point of the paper — that is
where option 1 (drop the skill) would have been the right answer.
Kim et al. (2024) is the rare case where the equation is meaningful
on its own and the proxy preserves the economic signal.

### When the paper's headline construct uses a dataset MVP doesn't cover BUT the paper publishes a reproducible deterministic sub-construct (prompt, keyword list, regex): ship the sub-construct applied to a matched-substrate MVP data source.

*Added during paper 4 onboarding (`paper_examples/ssrn-4429658.pdf`:
de Kok 2024, "ChatGPT for Textual Analysis? How to use Generative
LLMs in Accounting Research").*

This is the fifth variant of the "paper's headline measure is not
directly shippable" pattern — and the first one where the obstacle
is **substrate**, not **model** or **data privacy**. Paper 1
handled the case where the headline was an unreleased ML model with
a defensible closed-form proxy (branch 2). Paper 2 handled the case
where the headline was an ML model with NO honest proxy and the
shippable construct was elsewhere in the paper (branch 3). Paper 3
handled the case where the paper's dataset was proprietary and the
shippable construct was a determinants regression (branch 4). Paper 4
introduces **branch 5**: the paper's dataset (earnings-call Q&A
transcripts) is not part of the MVP corpus, but the paper **publishes
a reproducible deterministic sub-construct** (Online Appendix OA 3's
78-token non-answer keyword filter, Gow-et-al.-2021 plus manual
extensions) that we can apply verbatim to a **matched-substrate MVP
data source** (MD&A text — extracted via the pre-existing
`extract_mdna` skill).

de Kok (2024)'s headline Table 1 Column 6 result (96% accuracy / 87%
F1 / 70% error-rate reduction on the 500-Q&A-pair evaluation set) is
NOT shippable — it requires earnings-call transcripts MVP does not
ingest, and the 4-step GPT method it describes requires an OpenAI API
key and a fine-tuning budget. But **Step 1 of the funnel method, the
keyword filter, IS shippable — paper-exact, deterministic, and
publishable verbatim**. The published list is 7 trigrams + 23 bigrams
+ 48 unigrams = 78 tokens. The linguistic phenomenon those keywords
detect (hedging, non-disclosure, forward-looking caveat) generalises
across narrative accounting disclosures; MD&A is the canonical
substrate analog within MVP's 10-K corpus.

**The rule that generalises: when the paper's headline construct
uses a dataset MVP doesn't cover AND the paper publishes a
reproducible deterministic sub-construct (a keyword list, a regex, a
published prompt, a thresholded scoring rule), ship the sub-construct
applied to the closest MVP-substrate analog. The port is honest if:
(a) the sub-construct is reproduced verbatim from the paper (not
mutated to fit the new substrate), (b) a warning fires on every
non-null call making the port visible (e.g.
`substrate_port_mdna_vs_earnings_call`), (c) confidence is capped to
reflect the port approximation, (d) the manifest's
`implementation_decisions[0]` explicitly says the paper's headline
metric is NOT reproduced on the new substrate.**

For de Kok (2024) the port is:
- **Keyword list verbatim from OA 3 p. ix.** 78 tokens, frozen as
  module constants, regression-tested for exact count.
- **Applied to MD&A sentences (30-char floor tokenisation) from
  `extract_mdna`.** Density = (hedging sentences) / (total sentences).
- **Flag bands are presentation conventions** (low <0.15, typical
  0.15-0.35, high ≥0.35) because the paper has no MD&A-specific
  cutoffs — the paper's 13.9% Q&A-pair non-answer rate does NOT
  translate to MD&A's substantially higher boilerplate base rate.
- **Confidence capped at 0.7** while the substrate-port
  approximation is active.

The shipped skill is honest about what it is and is not:

- **Manifest's `description_for_llm` and
  `implementation_decisions[0]`** explicitly say the paper's
  classifier performance statistics do NOT apply to MD&A and the
  MD&A port is the MVP-scoped approximation.
- **Every non-null call emits
  `warning=substrate_port_mdna_vs_earnings_call`.** An agent cannot
  miss the port.
- **The paper's OA 4 overlap-area example sentences are encoded as
  fixture tests** — the ones whose bolded phrase maps to an OA 3
  keyword must fire the filter (paper-faithfulness check); the ones
  whose bolded phrase does NOT map to an OA 3 token (e.g. "not
  expect us to be given a volume") are documented as legitimately
  missed by Step 1 (they're caught by Steps 2-4 in the paper's
  method, which we don't ship).

The decision-tree generalisation for future papers, now covering
FIVE branches:

1. Is the paper's headline a closed-form formula? → Ship it
   (Beneish, Altman pattern).
2. Is the headline an ML model with a defensible closed-form
   proxy? → Ship the equation with the documented proxy + warning
   + confidence ceiling (Kim et al. 2024 Equation 9 / Upfrontedness
   pattern).
3. Is the headline an ML model with NO closed-form proxy? → Don't
   ship a fake-equation surrogate. Scan for a deterministic
   construct elsewhere in the paper (the partition variables, an
   appendix descriptive statistic, an OLS baseline) and ship THAT
   with explicit "not the headline measure" framing (Kim &
   Nikolaev 2024 §5.4 signals pattern).
4. Is the paper's setting worlds-away from public companies
   (private firms, behavioural data, proprietary tracking)? →
   Don't try to port the behavioural finding. Look for a
   **determinants regression** whose firm-characteristic inputs
   DO generalise (size, volatility, complexity, etc.) and ship
   the regressor framework with explicit "not the headline
   finding" framing (Bernard et al. 2025 Section 4 Table 3
   pattern).
5. Does the paper's headline construct use a dataset MVP doesn't
   cover BUT the paper publishes a reproducible deterministic
   sub-construct (keyword list, regex, prompt, thresholded rule)? →
   Ship the sub-construct verbatim applied to the closest MVP-
   substrate analog, with substrate-port warning, confidence cap,
   and explicit "the paper's performance statistics are substrate-
   specific and do NOT apply to our port" framing. (de Kok 2024
   Online Appendix OA 3 keyword filter applied to MD&A pattern.)

If a paper has nothing in branches 1, 2, 3, 4, or 5 — escalate to
the user.

*Operational side-note (paper 4).* Three workshop-tooling
deliverables landed on this iteration:

- **`workshop/paper_to_skill/replication_harness.py` (NEW — first
  version).** Given a shipped skill's manifest path, the harness
  runs each example in the `examples[]` block through the shipped
  skill via the registry and produces a pass/fail report. Optional
  typed expectations (`expected_flag`, `expected_score_range`,
  `expected_score_tolerance`) drive the per-example checks; in
  their absence the harness does a loose liveness check (skill
  returned a non-error envelope). Tested as a library unit (16
  assertions covering pure-function logic on `_check_expectations`
  and `_format_expected_score` plus `HarnessReport.summary_line`)
  plus a regression run against Paper 4's own manifest (3/3
  examples pass as liveness). Papers 1-3's manifests predate the
  harness's typed-expectation shape; back-fill is filed in
  `workshop/maintenance/README.md` as a follow-up. CLI entry
  point: `python -m workshop.paper_to_skill.replication_harness
  --manifest <path> [--verbose]`; exits non-zero on any
  pass/fail failure.

- **`workshop/paper_to_skill/draft_manifest.py` used, not
  improved.** Paper 4's skill needed a text-consuming input shape
  (cik + fiscal_year_end; same as Paper 1's Upfrontedness) rather
  than the L3 composite shape Paper 3 scaffolded around. The
  scaffold generator's current L3 paper_derived template fit the
  provenance / limitations / examples blocks well (the engineer's
  hand-fill was ~25% on those blocks; below Paper 3's ~30%
  baseline). The inputs/outputs block needed the heaviest hand
  adaptation because the scaffold templates a generic score/
  flag/signals shape; Paper 4's outputs have `hedging_density`
  + `sentence_count` + `hedging_sentence_count` + a structured
  `hits_by_category` + `keyword_counts` trace. Gap filed in
  `workshop/maintenance/README.md`: `draft_manifest.py` could
  accept a `--output-shape` hint (score/flag/signals vs
  density/hit-trace vs probability-classifier) to reduce the
  outputs-block hand-fill on future iterations. Not shipped this
  iteration — one-paper-ahead scoping.

- **Playbook callout (NEW — Paper-4-specific, branch 5).**
  Added this section ("When the paper's headline construct uses a
  dataset MVP doesn't cover BUT the paper publishes a reproducible
  deterministic sub-construct"). The decision-tree callouts now
  cover five branches.

### When the paper's setting is worlds-away from public companies (private firms, behavioural field study, proprietary tracking data): port the determinants framework, not the headline behavioural finding.

*Added during paper 3 onboarding (`paper_examples/s11142-025-09885-5.pdf`:
Bernard, Cade, Connors & de Kok 2025, Review of Accounting
Studies).*

This is the third variant of the "paper's headline measure is
not directly shippable" pattern. Paper 1 (Kim et al. 2024
fundamentals-text) handled the case where the headline was an
**unreleased ML model with a defensible closed-form proxy**.
Paper 2 (Kim & Nikolaev 2024 context-based interpretation) handled
the case where the headline was an **unreleased ML model with NO
honest closed-form proxy**. Paper 3 breaks new ground: the
obstacle isn't a model, it's the **data itself** — the paper's
empirical strategy uses proprietary Headset, Inc. daily
email-open tracking logs and point-of-sale data from 946 private
retail-cannabis dispensary stores, none of which has any analog
whatsoever in SEC 10-K filings.

Bernard et al. (2025)'s headline Section 5 finding — managers open
the daily email more often after high-sales days than after
low-sales days, a hedonic good-news-consumption asymmetry — simply
cannot be ported. No public-company dataset exists that tracks
daily attention-to-internal-reporting behaviour at the manager-
day level. We explicitly do NOT try to port the finding via
indirect proxies (8-K timing, insider-trading patterns): each of
those is a DIFFERENT research construct, not a faithful port. The
playbook rule here is:

**When the paper's dataset is proprietary AND the headline
construct depends on that dataset AND no public-company analog
dataset exists, don't try to port the headline finding through
an indirect-proxy chain. Instead, scan the paper for a
**determinants regression** or **cross-sectional descriptive
analysis** that uses firm-characteristic variables as inputs —
those CAN be ported, because the inputs are the kinds of firm
characteristics that DO generalise.**

For Bernard et al. (2025), the shippable construct was
Section 4 / Table 3 Panel a — the determinants regression
estimating which firm-level store characteristics predict
monitoring-service-use intensity. The three statistically-
significant generalisable determinants were Average sales
(size), Sales volatility (stability, sign-reversed), and
Single store (complexity, proxied via SG&A/Revenue). Each maps
to a canonical 10-K line item or to the existing market-data
fixture, and the paper's |t-statistics| become the relative
weights in our composite. The paper's regressor **direction** is
generalisable even when the raw **variable values** are not —
that's the key insight that unlocks branch 4 (below).

The shipped skill is honest about what it is and is not:

- **Manifest's `description_for_llm` and
  `implementation_decisions[0]`** explicitly say the
  hedonic-asymmetry finding is NOT implemented and that the
  skill ports only Section 4's determinants framework.
- **Two of the three signals are sign-reversed** via indicator-
  definition reversal (paper's volatility → our stability;
  paper's single-store → our high-SG&A-intensity). Documented
  in `implementation_decisions[3]` and `[4]` with explicit
  "this is not a coefficient-sign bug" framing.
- **Proxy warnings fire on every non-null call**
  (`stability_two_period_proxy`, `complexity_sga_proxy`) so an
  agent consuming the output cannot miss the adaptations.
- **Confidence is capped at 0.7** while the two proxies are
  active. A future expansion to quarterly filings (for a
  within-year stability proxy) and a segments-count canonical
  line item (for a direct Single-store analog) would let us
  remove both proxies and raise the cap.

The decision-tree generalisation for future papers, now covering
FOUR branches:

1. Is the paper's headline a closed-form formula? → Ship it
   (Beneish, Altman pattern).
2. Is the headline an ML model with a defensible closed-form
   proxy? → Ship the equation with the documented proxy + warning
   + confidence ceiling (Kim et al. 2024 Equation 9 / Upfrontedness
   pattern).
3. Is the headline an ML model with NO closed-form proxy? → Don't
   ship a fake-equation surrogate. Scan for a deterministic
   construct elsewhere in the paper (the partition variables, an
   appendix descriptive statistic, an OLS baseline) and ship THAT
   with explicit "not the headline measure" framing (Kim &
   Nikolaev 2024 §5.4 signals pattern).
4. Is the paper's setting worlds-away from public companies
   (private firms, behavioural data, proprietary tracking)? →
   Don't try to port the behavioural finding. Look for a
   **determinants regression** whose firm-characteristic inputs
   DO generalise (size, volatility, complexity, etc.) and ship
   the regressor framework with explicit "not the headline
   finding" framing. (Bernard et al. 2025 Section 4 Table 3
   pattern.)

If a paper has nothing in branches 1, 2, 3, or 4 — escalate to
the user.

*Operational side-note (paper 3).* Two workshop-tooling
deliverables landed on this iteration:

- **`workshop/paper_to_skill/draft_manifest.py` (NEW).** First
  version. Paper 1 and Paper 2 used copy-the-nearest-template-
  and-adapt; by Paper 3 the variation across templates (L3
  paper-derived, different proxy shapes, different confidence
  models, different dropped-signal rationales) had saturated
  enough that a scaffold generator paid for itself. The script
  reads a methodologist-notes file and emits a skeleton
  `manifest.yaml` with ~70% of the final line count (full
  provenance block populated from §(a), implementation_decisions
  stubs keyed off §(f)'s numbered bullets, limitations
  populated from §(g), examples populated from §(e),
  inputs/outputs skeletons shaped by the chosen layer). The
  engineer's hand-fill is the remaining ~30% — the math, the
  citation contract, the confidence model. Tested against
  Paper 3's own notes as the first regression case; the emitted
  scaffold's top-level keys are a strict subset of what a real
  L3 paper-derived manifest has, and the full-path sha256 /
  citation / DOI auto-population works for both Springer and
  Wiley styles.

- **The methodologist notes `(h)` template now specifies a
  three-paper chain.** Paper 2 introduced the "(h) What I
  leveraged from Paper 1's workshop deliverables" pattern.
  Paper 3's (h) section extends it into a two-paper leverage
  plus delta-over-Paper-2 inventory — making it obvious which
  workshop tooling carried forward untouched, which got
  hardened, and which is new. Papers 4-5 should continue the
  shape.

*Operational side-note.* Paper 1 also surfaced two infrastructure
gaps this playbook had no prior answer to, both fixed as part of
this iteration:

- **Local-file paper ingestion.** `mvp.ingestion.papers_ingest`
  originally only knew how to fetch HTTP-mirrored papers (Beneish,
  Altman). The `paper_examples/` corpus is local-only, so we added
  `ingest_local_paper` + a `LocalPaperRef` catalogue + a test suite
  mirroring the HTTP path. Every subsequent paper uses this same
  pattern.
- **Narrative-section citation resolution.** The engine's
  `resolve_citation` resolver originally only handled canonical
  financial-statement citations and market-data fixture citations.
  MD&A citations use the locator form `<cik>/<accession>::mdna::item_7`
  — we added a third branch to the resolver (`_resolve_mdna`) that
  re-invokes `extract_mdna` to rebuild the section and returns a
  bounded preview. Any narrative-layer skill added in future papers
  now has a working citation-resolution path without further engine
  work.

### Branch-3 sub-pattern: when the paper publishes an OLS regression with explicit coefficients on public-firm inputs, port the coefficients verbatim — no weight-normalisation, no sign-reversal.

*Added during paper 5 onboarding (`paper_examples/ssrn-4480309.pdf`:
Bernard, Blankespoor, de Kok & Toynbee 2025, "Using GPT to measure
business complexity," forthcoming The Accounting Review).*

Paper 5 is a branch-3 case ("ML without proxy; scan the paper for a
deterministic sub-construct"), but with a new shape distinct from both
Paper 2 (Kim & Nikolaev 2024) and Paper 3 (Bernard et al. 2025 RAST).
The headline construct — a fine-tuned Llama-3 8b scoring iXBRL footnote
tags — is unreachable (companion website with weights promised but not
yet available). We fall to branch 3 and scan for a deterministic
construct. Section 4.3 / Table 3 Column 2 **IS** that construct: a
full OLS regression of filing-level Complexity on 11 standard firm-
characteristic regressors, with published coefficients, t-statistics,
a 58k-filing sample, and R² = 0.225.

**What's different from Paper 2's branch-3 pattern.** Paper 2 (Kim &
Nikolaev 2024 context signals) took the partition-signal |t-stats|
from Table 7 Panel A and used them as RELATIVE WEIGHTS in a composite
— because the paper published a signal panel, not an OLS regression,
and no natural composite score existed. The weight-normalisation was
a construction we authored to turn per-signal differential contextuality
into a single scalar.

**What's different from Paper 3's branch-3 pattern.** Paper 3 (Bernard
et al. 2025 information acquisition) ported a private-data determinants
regression to public-company canonical analogs — with sign-reversal
(because the paper's volatility coefficient was negative and we wanted
a uniformly-positive composite), proxies (SG&A-intensity for
single-store), and |t-stats| as weights (because the regressors were
on different measurement scales and needed normalisation). All three
constructions are documented approximations layered on top of the
paper's regression.

**What's different about Paper 5.** Paper 5's regressors (10K, Size,
Leverage, BM, ROA) are on the SAME measurement scale and SAME
variable-family as MVP's canonical line items + the existing
market-data fixture. The paper's coefficients carry PAPER-EXACT
MAGNITUDES — we don't normalise, we don't flip signs, we just apply
them verbatim to decile-ranked inputs. The construction is a direct
port of the paper's regression; the only approximations are (a) five
of eleven regressors shipped (rest dropped because MVP doesn't ingest
the data), (b) decile ranks estimated from Table 2 percentiles rather
than computed on a live panel, and (c) ROA uses EBIT/TA as a
line-item-level proxy for IBQ/ATQ.

**The rule that generalises.** When the paper's branch-3 deterministic
sub-construct is **a published OLS regression whose RHS variables are
standard firm characteristics with names MVP's canonical line items
can reconstruct** (Size, Leverage, BM, ROA, profitability-type inputs),
port the coefficients verbatim. No weight-normalisation (paper gives
you the weights — they're the coefficients). No sign-reversal (paper
gives you the signs — they're the coefficient signs; flipping them
is a bug). The only construction work is (i) listing the subset of
regressors computable from the MVP substrate, (ii) documenting each
dropped regressor in the rule template with its paper coefficient +
t-stat + required data source so a future expansion is drop-in,
(iii) decile-rank interpolation from the paper's Table 2 percentiles,
(iv) baseline anchoring on the paper's sample mean (since industry /
year-quarter / filer-status FEs absorb the regression's intercept and
per-firm intercepts are not recoverable).

**Decision-tree generalisation (now six branches, with Paper 5 as a
sub-pattern of branch 3).** The five top-level branches remain:

1. **Closed-form formula** (Beneish, Altman): ship it.
2. **ML with closed-form proxy** (Kim et al. 2024 Upfrontedness): ship
   the proxy with warning + confidence ceiling.
3. **ML without proxy; deterministic sub-construct in the paper**
   (Kim & Nikolaev 2024 §5.4 signals, Paper 5): scan the paper for an
   honest alternative and ship THAT. Sub-patterns:
   - **(3a) signal-panel with |t-stats| as weights** (Kim & Nikolaev
     2024 pattern) — paper gives you the per-signal magnitudes but
     not the composite; you author the normalisation.
   - **(3b) OLS regression with paper-exact coefficients on public-
     firm inputs** (Paper 5 pattern, also Paper 3 RAST with extra
     construction) — paper gives you the weights directly; ship
     verbatim with dropped-regressor documentation.
4. **Worlds-away private-data behavioural study** (Paper 3 RAST,
   small-business paper): port the determinants framework, not the
   behavioural finding.
5. **Dataset-gap with published deterministic sub-construct**
   (Paper 4 de Kok keyword filter applied to MD&A): substrate-port
   the sub-construct with explicit "paper performance stats don't
   transfer" framing.

Sub-pattern (3b) is **the easiest branch-3 variant to port honestly**
because the coefficients carry paper-exact magnitudes and no
weight-normalisation guesswork is needed — provided a sufficient
subset of the regressors are computable on the MVP substrate. If
you have a branch-3 paper, **look for an OLS regression table in
the paper's deterministic sections first** — it's the highest-
fidelity port available when the headline ML is out of reach.

*Operational side-note (paper 5).* Three workshop deltas landed on
this iteration, each a hardening of infrastructure Paper 4 built:

- **`mvp/skills/manifest_schema.py:Example` extended** with
  `expected_score_range: list[float] | None` and
  `expected_score_tolerance: dict[str, float] | None`. Paper 4's
  harness design assumed these fields existed; Paper 4's own tests
  passed because they were liveness-only (no typed expectations used).
  Paper 5 is the **compounding test** that proved the harness's
  typed-expectation schema was not actually supported by the manifest
  validator. Extension is backward-compatible (Papers 1-4 manifests
  unchanged because the new fields default to `None`).

- **`workshop/paper_to_skill/replication_harness.py` aligned** with
  the extended schema. The harness's `_SCORE_KEYS` table now includes
  Paper 5's entry
  `predict_filing_complexity_from_determinants → predicted_complexity_level`.
  With the schema extension + score-key entry + Paper 5's shipped
  examples[] using the typed fields, the harness drives Paper 5's
  replication end-to-end with `5/5 examples passed`.

- **Paper 5's shipped `examples[]` block** is the **first manifest
  in the corpus to use `expected_score_range` typed expectations
  on every example**. Papers 1-4's examples were text-notes-only —
  the harness reported liveness-only PASSes. Back-filling Papers 1-4
  with typed expectations is filed as `backfill_manifest_typed_
  expectations.py` in `workshop/maintenance/README.md` (originally
  surfaced during Paper 4, now with a concrete driver pattern to
  follow from Paper 5's manifest).

## Post-corpus reflection — after 5 papers

*This section was written at the end of Paper 5 onboarding, after
all five `paper_examples/*.pdf` had been processed into shipped
skills (MVP went from 7 → 12 skills, workshop tooling from zero
executables to four first-class scripts). It captures what the
tooling DOES well, what it STRUGGLES with, what a day-1 team member
should know, and the prioritised next improvements. A sixth paper
processed against this corpus should bring wall-clock down to under
100 minutes; the compounding is real.*

**What the 4 paper_to_skill scripts do well (after 5 papers of use).**

- `extract_paper.py` handles both SSRN working-paper and journal-
  style PDFs. Its TOC helper routinely surfaces the load-bearing
  sections (Section 4, Table 3, Appendix D, OA 3) in under 5
  seconds — the biggest time-saver of any workshop script.
- `inspect_canonical.py` pre-flight-checks whether the MVP
  canonical line items needed by a candidate skill resolve across
  the 5 MVP issuers. Catches single-filing gaps (Carvana's
  missing EBIT, WorldCom's missing inventory) before they surface
  as test failures; ~30 seconds of upfront audit saves 10+ minutes
  of test-debug later.
- `draft_manifest.py` scaffolds the provenance block, limitations
  list, and examples block from a methodologist notes file in
  under 10 seconds. Gets ~70% of the final manifest line count
  right on paper 3 and ~80% on paper 5 (with the still-unshipped
  `--output-shape` hint, it could be 90%).
- `replication_harness.py` now drives manifest `examples[]` as
  live paper-replication checks. Paper 5 is the first manifest
  that uses the typed expectations end-to-end; the pattern is
  proven and back-filling Papers 1-4 is a mechanical follow-up.

**What the scripts still struggle with.**

- `extract_paper.py` parses text but can't parse tables reliably.
  Table 2 / Table 3 bodies in Bernard et al. (2025) came out as
  flat whitespace-separated number streams; I eyeballed the
  percentile rows manually. A PDF-table extractor (pdfplumber or
  camelot) would be a real upgrade for papers with rich tabular
  content (Papers 3, 5).
- `draft_manifest.py`'s scaffold emits a generic
  `{score, flag, components}` outputs block that fits roughly half
  the shipped skills. Paper 4 (density + hits-by-category trace)
  and Paper 5 (level + delta + regressor contributions + decile
  ranks + paper coefficients + baseline mean) both needed heavy
  hand-adaptation. The `--output-shape` hint is the fix; filed in
  `workshop/maintenance/README.md` since Paper 4 and reinforced
  by Paper 5.
- `inspect_canonical.py` doesn't know about market-data fixture
  entries. Papers 3 and 5 both need the `data/market_data/
  equity_values.yaml` entry for BM / X4-like signals; a pre-flight
  audit that also surfaces fixture-availability gaps would be a
  nice extension.
- There is no tool for **PDF percentile / coefficient table
  extraction**. Both Papers 3 and 5 had me copy rows by hand from
  the extracted text into the skill's constants. A
  `extract_paper_tables.py` helper (pdfplumber-backed) would be
  the single most valuable next workshop script.

**What a day-1 team member should know.**

- Read `workshop/docs/paper_onboarding_playbook.md` FIRST — the
  six-branch decision tree is the orientation artefact. Pick your
  paper's branch before you write any code.
- Then read the methodologist notes file for ONE prior paper in
  your branch — they're the concrete application of the playbook.
  The (a)..(h) section template is load-bearing; follow it.
- Spend 5 minutes on `inspect_canonical.py` before committing to
  a skill — knowing which canonical line items resolve for which
  MVP issuers tells you whether your branch-3 sub-construct is
  shippable on the MVP substrate.
- Use `draft_manifest.py` for the first pass on the manifest;
  expect 20-30% hand-fill on inputs/outputs. Run
  `SkillManifest.load_from_yaml(path)` early and often.
- Paper-replication tests should follow Papers 3-5's shape:
  coefficient / threshold pins, decile / sign-reversal pins,
  monotonicity per regressor, synthetic composite arithmetic,
  indeterminate-path tests, real-filing soft sanity checks
  (`@pytest.mark.requires_live_data`), and an in-test
  harness-shape driver over the manifest's examples[].
- Write the workshop delta DURING the paper, not after. Every
  iteration of paper_to_skill is an opportunity to harden the
  tooling for the next team member — don't skip it.
- Never `from workshop.X import Y` inside `mvp/` code or tests.
  The separation contract is load-bearing; a grep gate catches
  violations. If you need the harness's logic in a test,
  replicate its shape inline (Paper 5's paper-replication test is
  the reference pattern).

**Prioritised next improvements (author them when you hit them).**

1. **`extract_paper_tables.py`** — pdfplumber-backed Table / Panel
   extractor. Papers 3 and 5 both had me hand-transcribe
   percentile + coefficient rows; this is the highest-leverage
   next tool. Rough spec: given a PDF + a Table N identifier,
   return a list-of-dicts with header row + body rows.
2. **`draft_manifest.py --output-shape` hint** (filed by Paper 4,
   reinforced by Paper 5). Three templates:
   `score_flag_components` (the current default; fits Paper 3),
   `density_hits` (Paper 4 shape), `regression_decomposition`
   (Paper 5 shape with level + delta + contributions + decile
   ranks + coefficients). A fourth `custom` template emits a
   minimal required-keys stub.
3. **`backfill_manifest_typed_expectations.py`** — walks Papers
   1-4's manifests and adds `expected_score_range` / `expected_flag`
   typed expectations to each example based on the live skill
   output ± a configured tolerance. Turns Paper 1-4 harness runs
   from liveness-only into real replication checks. Paper 5's
   manifest is the reference shape.
4. **`inspect_canonical.py` fixture-awareness** — extend the
   pre-flight audit to surface market-data and manual-extraction
   fixture entries, so papers with BM / X4 / other market-
   dependent inputs surface fixture-gap risks up front.
5. **Per-paper wall-clock tracking in the workshop** — Paper 1
   took 210 minutes, Paper 5 took under an hour (continuation
   only) thanks to tooling compounding. Make the measurement
   explicit: a `workshop/maintenance/wall_clock.md` ledger that
   records start/stop timestamps per phase (ingest / notes /
   manifest / skill / rules / tests / gold / playbook). This
   converts "it got faster" into auditable evidence the tooling
   investment is paying off.

---

## Pointers

- The skill manifests for the two MVP paper-derived skills are worth
  reading end-to-end before authoring your first: [`compute_beneish_m_score`](../../mvp/skills/paper_derived/compute_beneish_m_score/manifest.yaml)
  and [`compute_altman_z_score`](../../mvp/skills/paper_derived/compute_altman_z_score/manifest.yaml).
  Their `implementation_decisions` blocks are the concrete application of
  every lesson above.
- Before submitting a paper's skill for review, run through
  [`skill_design_checklist.md`](skill_design_checklist.md). It's a
  one-page pre-review gate.
- The per-skill READMEs under `mvp/skills/paper_derived/*/README.md` are
  the author-voice summaries — write yours in the same shape.
- `mvp/human_layer/rule_authoring_guide.md` is the rule-template
  equivalent of this playbook. Read it before authoring a new rule
  template.
- `mvp/human_layer/gold_authoring_guide.md` is the same for gold cases.
- The `paper-to-skill #N` subagent contract (`SPEC_UPDATES.md` §"Per-paper
  subagent contract") is the 10-point done bar the master-agent loop
  verifies after each paper.

---

## One more time: the dual-growth directive

If you're reading this because you're about to process paper N under
`paper_examples/`, the end-of-iteration checklist is:

- [ ] `mvp/skills/<layer>/<new_skill_id>/` exists with a passing manifest,
      working `skill.py`, and (if L2/L3 per-component) rule template.
- [ ] `tests/integration/test_<skill>_paper_replication.py` asserts ±0.05
      on the paper's worked examples.
- [ ] At least one gold case under `mvp/eval/gold/<skill>/` (if the skill
      runs against an MVP sample filing).
- [ ] `mvp eval` still green — 4/5 M, 5/5 Z, 100% citations for the
      pre-existing skills; whatever the new skill's manifest declares for
      itself.
- [ ] `mvp skills list` shows the new skill; `mvp skills mcp | jq length`
      is one higher than before.
- [ ] `grep -R "from workshop" mvp/` still prints nothing.
- [ ] `workshop/docs/paper_onboarding_playbook.md` has a new section or
      callout recording the lesson that paper taught you.
- [ ] If any playbook step felt ad-hoc, at least one workshop script got
      written or improved.

Eight boxes, every paper. Paper 5 ships with nine total skills, a hardened
playbook, and a `paper_to_skill/` directory that has actual executable
tooling in it.
