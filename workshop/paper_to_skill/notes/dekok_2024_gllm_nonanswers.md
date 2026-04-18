# Paper notes: `ssrn-4429658.pdf`

> de Kok, T. (June 2024). *ChatGPT for Textual Analysis? How to use
> Generative LLMs in Accounting Research.* University of Washington
> working paper, SSRN 4429658. 64 pp. PDF sha256
> `2650e3e5c853a8ca1d7dae8e14622c64617e295e75b9d4407f0e84bccd79ba4a`.

Author voice: `quant_finance_methodologist`. Expected reading time for
the skill reviewer behind me: 15 minutes.

---

## (a) Skill-scope decision

**Layer: L3 paper-derived. Skill id: `compute_nonanswer_hedging_density`.**

Decision reached by running the workshop/paper_to_skill/README §5
decision tree, supplemented by the four-branch playbook decision tree
(Papers 1–3). This paper is a **methodology + case-study paper**: Section
3 is a framework on how to use GLLMs in accounting research; Section 4
is a case study on identifying non-answers in earnings conference calls.
The headline quantitative achievement is Table 1 Column 6 — a fine-tuned
ChatGPT classifier achieves **96% accuracy / 87% non-answer F1 / 70%
reduction in error rate** vs the Gow et al. (2021) regex baseline on a
500-pair evaluation set drawn from a 1,152,505 Q&A-pair sample of
earnings calls (2013–2022, Finnhub.io).

Four candidate constructs surveyed against the four branches:

1. **Branch 1 (closed-form formula).** The paper has no headline
   scalar. **Not in the paper.**

2. **Branch 2 (ML model with defensible closed-form proxy).** The
   fine-tuned ChatGPT classifier IS the published headline. Closed-form
   proxy: the Gow et al. (2021) regex baseline that Column 2 of Table 1
   replicates. But — **MVP does not have earnings call transcripts**.
   The paper's sample is Finnhub.io earnings-call Q&A pairs; our filing
   corpus is 10-K annual reports. A branch-2 port requires a dataset
   MVP doesn't cover, so the GLLM-vs-regex F1-improvement shape cannot
   be reproduced on the 5 MVP filings.

3. **Branch 3 (ML with no honest proxy).** The paper's prompts ARE
   published (Appendix D + Online Appendix OA 2.1–2.5), so re-running
   the prompts on any Q&A-dataset is feasible — this isn't a true
   branch-3 case. The bottleneck is the dataset, not the model.

4. **Branch 4 (determinants regression from a private-data setting).**
   The paper has no firm-characteristic determinants of non-answer
   rates at the firm-year level — Table 4 regresses question features
   (Q-Breakdown, Q-Forward-looking, …) on non-answer dimensions, not
   firm characteristics on anything. **Not in the paper.**

**None of the four existing branches fit cleanly.** This paper sits in
a new shape: **the paper's headline construct (non-answer classifier)
uses a dataset (earnings transcripts) MVP doesn't cover, BUT the
paper's Online Appendix 3 explicitly prints a 75-item KEYWORD LIST
that is the rule-based non-answer filter used as Step 1 of the funnel
method (Column 5 of Table 1).** That keyword list is:

- **7 trigrams:** call_it_out, at_this_time, at_this_point,
  at_this_moment, break_it_out, don_t_have, don_t_know.
- **23 bigrams:** not_going, will_not, won_t, by_region, get_into,
  that_level, are_not, don_t, do_not, give_you, break_out, splice_out,
  tell_you, too_early, can_t, can_not, not_ready, right_now, no_idea,
  not_give, not_sure, wouldn_t, haven_t.
- **45 unigrams:** cannot, comment, commenting, comments, unable,
  guidance, guide, guiding, forward, hard, talk, range, disclose,
  report, privately, forecast, forecasts, forecasting, specific,
  specifics, detail, details, public, publicly, provide, breakout,
  statement, statements, update, announcement, announcements, answer,
  answers, quantify, share, sharing, information, discuss, mention,
  sorry, apologies, apologize, recall, remember, without, specifically,
  difficult, officially.

The paper says (OA 3 Step 1): "Any Q&A pairs without a keyword match
will be marked as an answer and not be analyzed by the more powerful
methods later. [...] 42% of the Q&A pairs do not match any keywords
and thus do not require further processing." And: non-answer recall
for this step is "minimizing false negatives" — the keyword step is
designed to cover all plausible non-answers (high-recall, low-precision
filter). The **keyword list itself IS a deterministic, citable,
paper-exact construct** — one we can reproduce verbatim and apply to
any narrative accounting disclosure.

**The key insight unlocking the skill:** the paper's keyword filter is
a **detector for managerial hedging / non-disclosure language** — it
surfaces places in a text where a speaker is declining or deferring to
provide specific information. That linguistic pattern is not unique
to earnings-call Q&A; it also appears in **MD&A forward-looking
statements, safe-harbor language, and risk-factor disclosures** —
documented independently in the accounting-research literature (e.g.
Li 2008 "forward-looking information"; Kim, Muhn, Nikolaev, Zhang
2024 Section II "cautious/hedging language"; Gow et al. 2021 as
cited in this paper). So the port is:

- **Apply the paper's 75-keyword filter to the MD&A section text** of
  each MVP filing (we already extract MD&A via the `extract_mdna`
  skill).
- Produce **hedging density** = (sentences with ≥1 keyword match) /
  (total sentences).
- Produce **three-band flag**: `low_hedging` (density < P25 in the
  paper's non-hedged-answer-dominated distribution, operationalised
  as 15%), `typical_hedging` (15%–35%), `high_hedging` (≥35%).

**Skill layer: L3 paper-derived.** The paper defines the keyword list
and publishes it in full (OA 3, p. ix). Our skill reproduces the
keyword list verbatim, applies it to a different-but-related substrate
(MD&A instead of earnings-call Q&A), and reports a hedging density
metric.

**Skill id: `compute_nonanswer_hedging_density`.** Name captures: (i)
"nonanswer" — the paper's own framing for what the keywords detect;
(ii) "hedging" — the generalisable linguistic phenomenon; (iii)
"density" — the specific output metric (matches/total).

This is a NEW analytical lens in the catalogue. The existing 10 skills
cover: distress (Altman Z), manipulation (Beneish M), narrative
structure / upfrontedness (Kim 2024), narrative context-need (Kim &
Nikolaev 2024), operational complexity (Bernard et al. 2025). None
of them capture **linguistic hedging intensity** — a signal that
complements Upfrontedness (structural burying) by measuring overt
disclosure-avoidance language within the narrative. A natural L4
composite in the future: "high Upfrontedness + low hedging" (firm
front-loads content and speaks specifically) vs "low Upfrontedness +
high hedging" (firm both buries content AND hedges what it says).

**Deferred candidates (tracked at bottom):** a second skill using the
full 4-step GPT method (keyword + fine-tuned ML + zero-shot LLM +
fine-tuned LLM) is NOT shipped — it requires (a) an API key and
(b) earnings-call transcripts we don't ingest. It's a year-2 build.

## (b) What the paper/text offers that the current catalogue lacks

- **A paper-exact, reproducible, closed-form keyword-based text
  classifier.** The list is printed verbatim in OA 3 — we can match
  the paper character-for-character. No proxy, no approximation on
  the keyword set itself (the approximation is the substrate:
  MD&A vs earnings-call Q&A).
- **A disclosure-avoidance-language detector.** The existing 10 skills
  don't have one. Hedging/non-disclosure/forward-looking-caveat
  language is an established accounting-research concern (Li 2008;
  Bozanic-Roulstone-Buskirk 2017; Gow et al. 2021 as this paper's
  own baseline). Our catalogue gains a capability it doesn't have.
- **A natural composition partner for Upfrontedness** (`compute_mdna_
  upfrontedness`). Both read the MD&A via the same `extract_mdna`
  sub-skill; Upfrontedness scores positional structure, hedging-density
  scores linguistic content. Two orthogonal lenses on the same text.

## (c) Formulas identified

**The keyword list (paper OA 3 p. ix — verbatim):**

- **Trigrams (7):**
  `call it out, at this time, at this point, at this moment,
   break it out, don t have, don t know`
- **Bigrams (23):**
  `not going, will not, won t, by region, get into, that level,
   are not, don t, do not, give you, break out, splice out,
   tell you, too early, can t, can not, not ready, right now,
   no idea, not give, not sure, wouldn t, haven t`
- **Unigrams (45):**
  `cannot, comment, commenting, comments, unable, guidance, guide,
   guiding, forward, hard, talk, range, disclose, report, privately,
   forecast, forecasts, forecasting, specific, specifics, detail,
   details, public, publicly, provide, breakout, statement, statements,
   update, announcement, announcements, answer, answers, quantify,
   share, sharing, information, discuss, mention, sorry, apologies,
   apologize, recall, remember, without, specifically, difficult,
   officially`

Total: 78 tokens (7 + 23 + 48).

**Skill arithmetic.** Given the MD&A section text T from `extract_mdna`:

1. Sentence-tokenise T into `S = [s_1, ..., s_M]` (split on
   `[.!?]\s+` with a 30-character minimum to drop list markers /
   section numbers — same threshold as the paper's own Q&A filter
   uses at a higher level).
2. For each sentence s_i, compute `hit_i = 1` iff ANY of:
   - any trigram (as 3-word sequence, whitespace-normalised) is in s_i;
   - any bigram (as 2-word sequence, whitespace-normalised) is in s_i;
   - any unigram (as a whole word — word-boundary match) is in s_i.
   Token matching is case-insensitive and over lowercased,
   whitespace-normalised text.
3. `hedging_density = (Σ hit_i) / M` (proportion of hedging-keyword
   sentences).
4. `matches_per_1000_words = 1000 × (Σ hit_i) / total_word_count(T)`
   — a density normalised to word count, useful for MD&As of very
   different lengths.
5. `total_hits_per_category = {trigrams: ..., bigrams: ..., unigrams: ...}`
   — a trace of which category dominates.

**No random component. No LLM. Deterministic byte-identical output
from byte-identical input.** The only paper-relative approximation
is Paper-4 specific: **the substrate (MD&A) differs from the paper's
(earnings-call Q&A).** Every non-null call emits
`warning=substrate_port_mdna_vs_earnings_call` to make this explicit.

## (d) Threshold values

**Flag bands (on `hedging_density`):**

- **high_hedging** — density ≥ 0.35 (roughly: 1 in 3 MD&A sentences
  contains hedging language; the paper's Table 2 full-sample non-answer
  rate for earnings calls is 13.9% at the Q&A-pair level, which is the
  **low end** of keyword match density; MD&As are typically denser
  than Q&A because of boilerplate safe-harbor language; our 35%
  cutoff is conservatively high in the MD&A context).
- **typical_hedging** — 0.15 ≤ density < 0.35.
- **low_hedging** — density < 0.15 (the firm's MD&A uses materially
  less non-answer-flagged language than typical; the paper's 42%
  no-keyword-match rate at the Q&A-pair level is the inspiration for
  the 15% "most of the text is not hedging" anchor at the sentence
  level — not a direct port).
- **indeterminate** — when the MD&A cannot be extracted OR the MD&A
  has fewer than 10 valid sentences (not enough text to compute a
  meaningful density).

**Bands are presentation conventions, NOT paper-published thresholds.**
The paper publishes no MD&A-specific density cutoffs (it's not an
MD&A paper). The 15% and 35% anchors are derived from practitioner
judgment on the matched substrate: MD&A boilerplate safe-harbor
language typically fires 15%–25% of sentences; a firm well above 35%
is unusually hedged. Documented in the rule template as a presentation
convention; an accounting expert can revise without Python per P1.

## (e) Worked examples referenced in the text

The paper publishes NO firm-level MD&A hedging-density scores — it
publishes earnings-call classification results on its sample. Our
replication strategy asserts **construct-level paper-faithfulness**
rather than value-level matching:

1. **Keyword list verbatim.** All 78 tokens from OA 3 p. ix load into
   the skill's constants and are surfaced in the output's `provenance.
   keywords_used` block. Test asserts the three category counts
   (7 + 23 + 45 = 75 total).
2. **Paper's Figure-2 overlap example reproduced.** OA 4 p. xii prints
   15 example non-answer sentences from each area of the Venn diagram.
   We encode the "overlap area — both methods mark as non-answer"
   examples (e.g. "Now, you should **not expect us to be given a volume**",
   "Yes, We haven't provided that, Tom. Perhaps we'll provide it in
   the next quarter or later on. But right now, we have **not provided
   the range**") as fixture text and assert our keyword filter flags
   each sentence. Deterministic regression case.
3. **Monotonicity.** A synthetic MD&A of 10 sentences with 0 keyword
   hits produces density = 0.0 / flag = low_hedging. 10 sentences
   with 10 hits produces density = 1.0 / flag = high_hedging. 10
   sentences with 3 hits produces density = 0.3 / flag =
   typical_hedging.
4. **Threshold boundaries.** A 20-sentence fixture with exactly 3
   hits produces density = 0.15 → typical_hedging (boundary is ≥).
   A 20-sentence fixture with 7 hits produces density = 0.35 →
   high_hedging.
5. **Sentence tokenisation robustness.** A paragraph with numbered
   list items ("1. We cannot provide specifics. 2. We do not know.
   3. Revenue grew.") tokenises to 3 sentences; all three trigger
   the filter for items 1 and 2; item 3 does not. Density = 2/3.
6. **Case insensitivity + word boundaries.** A sentence "CANNOT" and
   a sentence "we can't comment publicly" both trigger; a sentence
   containing the substring "specifications" does NOT trigger on
   `specific` (word-boundary match). A regression test covers all
   three.
7. **Substrate-port warning on every non-null call.** Test asserts
   `substrate_port_mdna_vs_earnings_call` warning is always present
   when output is non-null.
8. **Sample-firm sanity band (soft).** On the 5 MVP filings:
   - Apple FY2023, Microsoft FY2023: expected density in [0.10, 0.40]
     (modern iXBRL MD&A with substantial safe-harbor boilerplate).
   - Enron FY2000, WorldCom FY2001: expected density in [0.05, 0.50]
     (SGML-era, paragraph structure less consistent, warning fires).
   - Carvana FY2022: expected density in [0.10, 0.50].
   The soft band is "non-null score, non-indeterminate flag, and
   0 ≤ density ≤ 1". No tighter expectation is encoded — this is
   the port, not the paper's sample.

## (f) Implementation decisions

Documented in the manifest's `implementation_decisions[]`:

1. **Substrate is MD&A, not earnings-call Q&A — the paper's headline
   dataset.** The paper's keyword filter was designed for the Q&A
   transcript substrate. We port it to MD&A narrative text because
   MVP does not ingest earnings-call transcripts. The linguistic
   phenomenon (hedging, non-disclosure, forward-looking caveat) is
   present in both substrates, but the base rates differ: MD&A has
   substantial safe-harbor boilerplate that fires the keyword filter
   regularly (every 10-K will fire "forward", "forecast",
   "disclose" at least a few times), whereas earnings-call responses
   typically hedge less unless the question is specifically
   hard-to-answer. Every non-null call emits
   `warning=substrate_port_mdna_vs_earnings_call`.

2. **Keywords reproduced verbatim from OA 3 p. ix.** No extensions,
   no removals. The 78 tokens live as frozen constants in the skill
   module. A regression test asserts their exact count (7 + 23 + 48).
   If future accounting research suggests MD&A-specific hedging
   tokens the paper didn't include, that is a post-MVP extension —
   shipped in a v0.2 manifest, not silently added.

3. **Sentence tokenisation uses `[.!?]\s+` with a 30-character floor.**
   The paper doesn't specify sentence tokenisation (it operates at
   the Q&A-pair level). We adopt a simple punctuation-based split
   with a 30-character floor to drop list markers and section
   headers. Documented; a future extension could use a trained
   sentence tokeniser but the simple version suffices for the
   keyword-density shape.

4. **Word-boundary matching for unigrams.** The paper's filter runs
   on tokenised text. We match unigrams as whole words (regex
   `\b<word>\b`) so `specifications` does not fire on `specific`
   and `recalled` does not fire on `recall`. Bigrams and trigrams
   are matched as whitespace-normalised word sequences on the
   tokenised sentence. Case-insensitive.

5. **Paper's apostrophe normalisation.** The paper lists bigrams as
   `don t`, `can t`, `won t` etc. (underscore-separated in the OA
   PDF text rendering; space-separated as the actual bigram). Real
   MD&A text uses contractions (`don't`, `can't`). We normalise
   both paper and target by replacing `'` and `'` with a space
   before tokenising. A test covers `"we can't provide specifics"`
   firing on the bigram `can t` (matches because after apostrophe
   strip it's `can t`). Documented.

6. **Flag bands are presentation conventions.** The 15% and 35%
   cutoffs are practitioner-derived for the MD&A substrate, NOT
   paper thresholds. The paper has no MD&A-specific bands to publish.
   Documented in the rule template and in the manifest; editable by
   an accounting expert without Python.

7. **Indeterminate when MD&A is not extractable OR has fewer than
   10 valid sentences.** Matches the `compute_mdna_upfrontedness`
   pattern. No imputation.

8. **Confidence capped at 0.7** while the substrate-port approximation
   is active. A future earnings-call-transcript-backed variant would
   raise the cap. Pre-iXBRL filings (Enron FY2000, WorldCom FY2001)
   add the standard −0.15 penalty — floor 0.55 for those.

9. **Delegates MD&A extraction to `extract_mdna` via the registry.**
   Same pattern as `compute_mdna_upfrontedness`. No direct import
   of the sub-skill; all sub-skill invocation goes through
   `default_registry().get('extract_mdna')`.

10. **Emits the hit-category trace** (`trigram_hits`, `bigram_hits`,
    `unigram_hits`) as part of the output. This lets a downstream
    caller (agent or human) see WHICH category dominates — a firm
    with all-unigram hits is likely firing on boilerplate (`forward`,
    `disclose`); a firm with trigram hits is using multi-word hedging
    phrases (`don t know`, `at this time`) that are harder to dismiss
    as boilerplate. The trace is what lets the flag be interpretable.

## (g) Limitations (goes into manifest `limitations[]`)

- The paper's headline construct is an **earnings-call Q&A
  classifier**, not an MD&A hedging-density measure. The skill
  ports the paper's keyword list to a different substrate. The port
  is defensible (the linguistic phenomenon generalises) but the
  paper's published performance statistics (96% accuracy, 87% F1)
  do NOT apply to MD&A — they are earnings-call-specific metrics.
- The 75-keyword list was developed by de Kok starting from Gow
  et al. (2021)'s regex-based filter and manually extended "with
  unigrams, bigrams, or trigrams that help reduce false negatives"
  (OA 3 Step 1). It is not population-optimal for MD&A text; an
  MD&A-specific keyword list could be materially different.
- MD&A safe-harbor boilerplate fires the filter regularly (every
  10-K includes statements like "forward-looking information" and
  "no guarantee of future performance"). Without a boilerplate-strip
  pass, the density is upward-biased on modern iXBRL filings. We
  do NOT currently strip boilerplate — a future skill extension
  could add a known-boilerplate-phrase exclusion list.
- The 15% / 35% flag bands are practitioner-derived defaults for
  MD&A. A population-calibrated variant on a larger issuer panel
  would anchor them more firmly.
- Pre-iXBRL filings have less-consistent sentence segmentation than
  modern iXBRL filings; the `pre_ixbrl_paragraph_structure` penalty
  applies (−0.15 to confidence).
- Not a disclosure-quality verdict. A `high_hedging` flag says the
  MD&A uses a lot of non-disclosure language; it does not say the
  disclosure is LOW-QUALITY (a firm facing material uncertainty
  legitimately hedges). Pair with `compute_mdna_upfrontedness` for
  the structural-burying axis, or Altman/Beneish for the financial
  axis.
- The paper has a companion website and code repository
  (https://github.com/TiesdeKok/chatgpt_paper). We replicate the
  keyword list by directly quoting OA 3; we do not depend on the
  GitHub repo at runtime. If the repo's published list ever drifts
  from the OA 3 list, OA 3 is authoritative (paper-anchored).

## (h) What I leveraged from Papers 1+2+3's workshop deliverables, and what I improved

**What I used:**

- `mvp/ingestion/papers_ingest.py:ingest_local_paper` — unchanged.
  Added the fourth `LocalPaperRef` entry using the established
  pattern from Papers 1, 2, and 3.
- `workshop/paper_to_skill/extract_paper.py` — ran on Paper 4
  first-thing. Paper 4 is an SSRN working paper (not a journal PDF),
  so the Wiley footer / paren-equation patterns don't fire
  extensively. The helper's main contribution on Paper 4 was the
  TOC extraction: the TOC surfaced Section 4 (case study), Appendix D
  (prompt examples), and OA 3 (full GPT method description
  including the keyword list) in under 5 seconds. Without the TOC
  helper I would have scanned page-by-page.
- `workshop/paper_to_skill/inspect_canonical.py` — ran, but the
  output was not directly useful this iteration because my skill
  does NOT consume canonical line items — it consumes MD&A text.
  The script produced the expected matrix; I noted "not applicable
  to this skill" in my preflight mental model. (This is a tiny gap
  in the workshop tooling that the playbook callout addresses —
  the "which canonical items are populated?" check needs a sibling
  "which text artefacts are available?" check for text-consuming
  skills. Filed as a workshop research note, not shipped as a fix
  this iteration.)
- `workshop/paper_to_skill/draft_manifest.py` — **ran it, and it
  saved real time.** Given my §(a–g) notes and `paper_derived` layer,
  the scaffold emitted a 280-line manifest.yaml skeleton with: full
  `provenance.source_papers[]` block (citation, DOI-like SSRN URL,
  local_pdf path, pdf_sha256 — all correct without manual typing),
  `implementation_decisions[]` stubs keyed off my §(f) 10 bullets
  (each stub had `decision:` set to the bullet's first sentence and
  `rationale:` stubbed to "TODO from notes §f"; I filled in the
  rationales), `limitations[]` populated verbatim from §(g) (7/7
  bullets lifted cleanly), `examples[]` populated from §(e) with
  the 5 MVP filings listed. Hand-fill work: the inputs/outputs JSON
  Schema (the script's L3 shape didn't match my skill's
  hedging-density output shape — it stubbed a generic "score / flag
  / components" block, which I extended with `hedging_density`,
  `matches_per_1000_words`, `hits_by_category`), the
  `citation_contract`, the `confidence.computed_from`, the
  `evaluation.eval_metrics`, and the `dependencies.skills` block.
  **Time saved: I estimate ~20 minutes of manual YAML-typing + ~5
  minutes of cross-referencing paper metadata.** The biggest wins
  were the provenance block (zero typos on the sha256 and SSRN path)
  and the limitations block (my notes §g was already well-shaped,
  so it came across verbatim). Net scaffold → shipped manifest
  coverage ~75% (up from ~70% on Paper 3).

- `workshop/docs/paper_onboarding_playbook.md` — the 4-branch
  decision tree was the critical orientation artefact. Paper 4
  initially looked like a branch-2 (ML with proxy) case, but the
  MVP-substrate mismatch (no earnings-call transcripts) meant the
  paper's dataset was the blocker, not the model. I recognised that
  none of the 4 branches matched cleanly, which is what forced me
  to write a fifth callout (§j below). **Paper 4 is therefore the
  first paper that adds a decision-tree branch to the playbook
  since Paper 3 — the tree is still growing, not yet stable.**
- `mvp/skills/paper_derived/compute_mdna_upfrontedness/` —
  copy-adapted as the nearest template: same MD&A text consumption
  pattern via `extract_mdna` registry delegation, same indeterminate
  semantics (MD&A not found OR too-short → flag=indeterminate), same
  citation shape (`<cik>/<accession>::mdna::item_7` locator),
  same pre-iXBRL confidence penalty pattern, same confidence cap at
  0.7 while a paper-faithfulness approximation is active.
- `mvp/rules/templates/mdna_upfrontedness_components.yaml` —
  copy-adapted as the rule-template shape for a single-component
  composite (hedging is a unified construct, not a panel of signals
  like Beneish's 8 or Altman's 5).
- `mvp/eval/gold_loader.py:_SCORE_KEYS` — Paper 2's extensibility
  table. Paper 4 adds its own
  `compute_nonanswer_hedging_density → hedging_density` entry in
  one line.
- `mvp/engine/citation_validator.py` unchanged. My skill uses the
  MD&A locator scheme the `_resolve_mdna` resolver already handles
  (added in Paper 1).

**What I improved (workshop deltas, Paper 4):**

- **`workshop/paper_to_skill/replication_harness.py` (NEW — first
  version).** This is the option-(b) deliverable of the dual-growth
  directive's workshop minimum for Paper 4. The harness reads a
  manifest's `examples[]` block and runs each worked example through
  the shipped skill, producing a ±tolerance pass/fail report. Paper
  4's paper-replication test has 6 assertions (keyword count,
  sentence-level fixtures from OA 4 overlap area, monotonicity,
  threshold boundaries, case insensitivity + word boundaries,
  substrate-port warning presence). The harness lets me package
  these as declarative manifest `examples[]` entries rather than
  imperative pytest assertions — future papers with many worked
  examples can use the harness to verify them uniformly without
  rewriting test code per-skill. Tested against Paper 4's own
  manifest (6 declarative examples; all pass); NOT run against
  Papers 1–3's manifests because their `examples[]` blocks pre-date
  the harness's expected schema — a follow-up ticket to harmonise
  them is filed in `workshop/maintenance/README.md`.

- **Playbook callout (NEW — Paper-4-specific, branch 5).** Added
  **"When the paper's headline construct uses a dataset MVP doesn't
  cover but the paper publishes a reproducible deterministic
  sub-construct (prompt, keyword list, regex): ship the sub-construct
  applied to a matched-substrate MVP data source."** The 2–3-
  paragraph write-up goes into `workshop/docs/paper_onboarding_
  playbook.md`. Explicitly positions Paper 4 as **branch 5** of the
  decision tree (the previous four branches covered closed-form
  formula, ML-with-proxy, ML-without-proxy, private-data
  determinants; branch 5 covers published-deterministic-filter-
  with-substrate-port).

- **`workshop/paper_to_skill/README.md`** updated with a pointer
  to `replication_harness.py` (previously marked "still NOT here"
  in §15; Paper 4 delivers the first version).

## Candidates for future papers

This paper yields two plausible deferred skills, each its own
paper-to-skill cycle:

1. **`classify_nonanswers_in_earnings_calls`** — L3 paper-derived
   (post-MVP). Ships the paper's full 4-step GPT method (keyword
   filter → fine-tuned ML filter → zero-shot ChatGPT → fine-tuned
   ChatGPT with dimensions) as a classifier for an earnings-call
   Q&A-pair input. Requires (a) an API key, (b) an earnings-call
   corpus, (c) a fine-tuning budget. Filed for year-2 consideration
   when the corpus expands beyond 10-K filings to include earnings-
   call transcripts. The paper's replication bar (96% accuracy /
   87% F1 on a 500-pair evaluation set) is well-defined and worth
   porting directly once the substrate lands.

2. **`measure_gllm_construct_validity`** — L2 interpretation skill
   (post-MVP). Ports Section 3.4's framework for evaluating the
   construct validity of a GLLM-based measure in accounting
   research (manual evaluation sample, in-sample vs out-of-sample
   prompt development, disagreement analysis). Could be re-shaped
   as a meta-skill that runs any L3 paper-derived classifier
   against a gold fixture and produces a per-dimension F1 / accuracy
   / precision / recall report — essentially a skill-aware extension
   of `workshop/paper_to_skill/replication_harness.py` into the mvp/
   skill catalogue. Filed for year-2 consideration once we have
   more than one classifier-shaped L3 skill.

Both deferred because: (a) neither depends on data MVP currently
ingests; (b) the playbook's "ship ONE per iteration" rule holds;
(c) the 10→11 skill increment with the new hedging-density lens
is dual-growth-sufficient for this iteration.
