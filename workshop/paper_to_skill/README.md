# `paper_to_skill/` — the hero workflow

This is the step-by-step playbook for turning an academic paper into a shipped
skill under `mvp/skills/`. It is a retrospective: steps 1–10 below describe
what Phase 3 and Phase 4 actually did to onboard Beneish (1999) and Altman
(1968). Follow the same sequence for every new paper.

The **dual-growth directive** (`SPEC_UPDATES.md` "2026-04-17 — `paper_examples/`
practice corpus") governs this workflow: every paper you process MUST grow
both codebases — `mvp/` gets at least one new shipped skill, and `workshop/`
gets at least one scripted improvement and one playbook callout. Paper 5 should
feel visibly faster than paper 1 because the workshop tooling matured along
the way.

---

## 1. What `paper_to_skill/` is

A paper goes in; a shipped, evaluated, registry-discoverable skill comes out.
The pipeline is:

```
paper PDF
  → ingested into data/papers/
  → quant_finance_methodologist extraction (notes under workshop/paper_to_skill/notes/)
  → skill-layer decision (L1 fundamental, L2 interpretation, or L3 paper-derived)
  → manifest authored under mvp/skills/<layer>/<skill_id>/manifest.yaml
  → skill.py implemented under the same dir
  → rule template (if L2/L3) authored under mvp/rules/templates/
  → paper-replication test under tests/integration/
  → gold cases added under mvp/eval/gold/<skill>/
  → registry auto-discovers; mvp skills list shows the new skill
  → mvp eval still green
  → workshop/docs/paper_onboarding_playbook.md updated with lessons learned
  → DONE
```

## 2. When to start a paper

Only after the MVP gates in `success_criteria.md` §1 are all green (the Task
#9 master-loop check has passed). **One paper at a time.** The goal-driven
master/subagent loop spawns a `paper-to-skill #N: <paper_id>` subagent for
each paper; the master verifies the 10-point per-paper contract
(`SPEC_UPDATES.md` §"Per-paper subagent contract") and only moves to paper
N+1 on confirmed success.

Never short-cut this ordering. A paper added while MVP gates are red just
masks the underlying failure.

---

## 3. Step 1 — ingest the paper

Drop the PDF into `paper_examples/` if it isn't already there, then register
it:

```python
from mvp.ingestion.papers_ingest import ingest_paper

record = ingest_paper(
    paper_id="<short_snake_case_id>",        # e.g. "kim_2024_context"
    source_url="<mirrored_url_or_file_path>",
)
print(record.sha256, record.size_bytes)
```

`papers_ingest.py` writes the PDF to `data/papers/<paper_id>.pdf`, computes
sha256, extracts an abstract to `<paper_id>.abstract.txt`, and appends a
`paper_ingested` event to `data/manifest.jsonl`. Reruns are idempotent (hash
mismatch raises `expected_hash_mismatch` — never silent overwrite).

**Anti-pattern:** don't skip the manifest step by copying the PDF in by hand.
The hash pin is what lets us detect silent mirror swaps later.

---

## 4. Step 2 — read and annotate (`quant_finance_methodologist` persona)

The quant-finance persona (or a human replacing it) reads cover-to-cover and
captures:

- **Every formula**, with the paper's own symbol naming. Keep the original
  symbols; do not rename to our canonical line-item names yet.
- **Every coefficient table**. Copy the full precision from the paper — **not
  rounded**. Beneish's TATA coefficient is 4.679, not 4.68; Altman's X5 is
  0.999, not 1.0 (lessons 1 and 2 in the playbook).
- **Every threshold value** with its exact page reference. Beneish (1999) p. 16
  says the optimal cutoff is **-1.78**, not the widely-cited -2.22 (which is
  from Beneish et al. 2013).
- **Worked examples** — the paper's own tables where individual firm numbers
  are reported. These become the paper-replication test oracles.
- **Sample characteristics** — size, time period, asset class, exclusions.
  These go into the manifest's `provenance.study_scope`.

Record the output in `workshop/paper_to_skill/notes/<paper_id>.md`. The notes
file is the input to every subsequent step.

---

## 5. Step 3 — choose the skill layer

Use this decision tree:

```
Does the paper define a specific, callable construct (a score, a ratio, a
classifier) that an agent would reasonably request by name?
  YES → L3 paper_derived (compute_<construct>)
        e.g. compute_beneish_m_score, compute_altman_z_score
  NO  → continue

Does the paper describe HOW to judge an existing construct (e.g., "here's how
an analyst reads this ratio in this context")?
  YES → L2 interpretation (interpret_<construct>)
        e.g. interpret_m_score_components
  NO  → continue

Does the paper surface a new PRIMITIVE extractable from a filing (a section,
a footnote, a table concept) that downstream skills can consume?
  YES → L1 fundamental (extract_<primitive>)
        e.g. extract_mdna
  NO  → escalate

If the paper fits none of the three patterns, escalate to the user before
authoring. Per the dual-growth directive, "this paper doesn't fit" is a
research-design problem — don't silently skip.
```

For MVP, Beneish and Altman were both L3 (paper_derived), and the interpretive
per-component rules went into separate L2 skills
(`interpret_m_score_components`, `interpret_z_score_components`). That split
is the default shape for a paper that both defines a score AND supplies
paragraph-level component-by-component discussion.

---

## 6. Step 4 — author the manifest

Start from the schema in `mvp_build_goal.md` §6. Copy the closest existing
manifest (Beneish or Altman) as a template and adapt.

Required substantive blocks:

- `skill_id`, `version: 0.1.0`, `layer`, `status: alpha`,
  `maintainer_persona`.
- `description_for_llm` — 2–4 sentences for an LLM caller. What does it do,
  typical inputs, typical outputs, when NOT to call it. A cold agent should
  pick the right skill from the description alone.
- `provenance.source_papers[]` — full citation, DOI/URL, local_pdf path,
  pdf_sha256 (from step 1).
- `provenance.study_scope` — asset_class, time_period_in_paper,
  sample_size_in_paper.
- `provenance.problem` — one-line + long-form.
- `provenance.methodology.formulas_extracted_from_paper` — every formula in
  the paper's own notation, plus the canonical notation our implementation
  uses.
- `provenance.expected_results` — what the paper reports as the replication
  bar.
- `implementation_decisions[]` — EVERY place the paper is ambiguous or where
  you made a call. The Beneish TATA 16-canonical approximation, the Altman
  X5=0.999-not-1.0, the "indeterminate when EBIT is null" policy — those all
  live here. One entry per decision, with `decision`, `rationale`, and
  `reviewer_persona`.
- `inputs` / `outputs` — full JSON Schema with `description` on every field.
- `citation_contract` — what fields must cite what line items.
- `dependencies.skills[]` — declare every other skill you call through the
  registry.
- `evaluation.eval_metrics[]` — the pass-rate targets.
- `limitations[]` — honestly record what the paper's sample doesn't cover.
- `examples[]` — at least one worked input/output with expected flag range.
- `cost_estimate` — tokens, API calls, typical latency.

**Anti-pattern:** don't leave `provenance.source_papers: []` unless the skill
has no paper (fundamental skills legitimately do — the SEC taxonomy IS the
provenance). For a paper-derived skill an empty provenance block is a bug.

The manifest validates via `SkillManifest.load_from_yaml(path)` at import
time. If validation fails, the registry won't pick up the skill.

---

## 7. Step 5 — implement the skill

Follow the `mvp/skills/_base.py` contract. Three rules:

1. **Null propagates**. When a required input is null, return the skill's
   "indeterminate" flag (not 0.0, not an imputed value, not a raised
   exception). The Carvana FY2022 EBIT null (which makes Altman X3 undefined)
   returns `flag=indeterminate` cleanly — that's the model case.
2. **Every arithmetic output carries its source citation**. If the skill
   emits `m_score: -0.2422`, the citations array must include locators for
   the line items that produced it. `engine.citation_validator` enforces the
   contract.
3. **Errors are typed**. Every raise is a `LibError` subclass (or subclass
   thereof like `IngestionError`, `StoreError`, `PersonaCallError`). No bare
   exceptions, no HTTP 500s — the API layer maps the typed exceptions to the
   5-field structured envelope automatically.

Tests: one unit test per helper, one integration test that runs the whole
skill against real fixture data. Unit tests should be hermetic (tmp_path +
monkeypatch + httpx.MockTransport). Integration tests MAY read the real
filings in `data/filings/`.

---

## 8. Step 6 — author the rule template (if L2/L3 with per-component rules)

Per `mvp/human_layer/rule_authoring_guide.md`. The template lives at
`mvp/rules/templates/<skill_id>_components.yaml`. It is pure YAML — no Python.

Hard rules enforced by `tests/unit/rules/test_rule_template_schema.py`:

- Every component has ≥4 severity bands that **partition the real line with
  no gaps**. The test sweeps 1001 values over [-10, 10] and asserts exactly
  one rule matches at each point.
- Every `medium`, `high`, or `critical` rule has ≥2 `follow_up_questions`.
- Every `interpretation` string is ≥30 characters of substantive accountant
  voice — not "elevated reading, consistent with manipulation."
- Every `citations_required` entry references a canonical line item in
  `mvp/standardize/mappings.py`.

Reference: `mvp/rules/templates/m_score_components.yaml` (8 components × 4
bands = 32 rules + composite threshold) and
`z_score_components.yaml` (5 × 4 = 20 rules + 3-zone thresholds). Both are
what an accounting expert would recognize as their kind of artifact.

---

## 9. Step 7 — paper-replication test

Pick one or more worked examples from the paper's own tables. Construct a
canonical-statements fixture that reproduces the paper's raw inputs for that
firm. Assert the shipped skill's output is within **±0.05** of the paper's
reported headline metric (±2% on each component).

Example: `tests/integration/test_beneish_paper_replication.py` takes the
paper's reported manipulator-sample means and asserts
`compute_beneish_m_score` reproduces M ≈ -1.891 from those inputs within
±0.05.

**Anti-pattern:** don't use the paper-replication test as a dumping ground
for fixture sanity checks. The test's one job is "our implementation
reproduces the paper's own numbers." Other assertions go in the unit tests
for the skill.

If your replication can't hit ±0.05, DO NOT fudge coefficients. Document the
deviation in the manifest's `implementation_decisions` block (like the
Beneish TATA 16-canonical approximation) and widen the test tolerance with a
comment pointing at the decision.

---

## 10. Step 8 — gold cases

If the skill can plausibly run against one or more of the 5 MVP sample
filings (Enron 2000, WorldCom 2001, Apple 2023, Microsoft 2023, Carvana
2022), add gold cases under `mvp/eval/gold/<skill_short>/<issuer>_<year>.yaml`.
Per `mvp/human_layer/gold_authoring_guide.md`.

Each gold case names:

- Expected score (range OR value+tolerance).
- Expected flag (exact enum).
- `must_cite` line-item list.
- Confidence range.
- `warnings_must_include` if the skill should surface a specific warning.
- `notes.source_of_expected` — where the expected value came from (Phase 4
  live run + ±0.10 band is the standard pattern; paper-reported value with a
  widened band is the fallback).
- `known_deviation_explanation` if the case is deliberately encoded to fail
  in a documented, explainable way (the WorldCom Beneish case is the MVP
  model for this).

Indeterminate cases (like Carvana's Altman with null EBIT) use
`expected.score.value: null` + `expected.flag.value: "indeterminate"`; the
runner has null-matches-null semantics.

---

## 11. Step 9 — verify registry discovery

```
mvp skills list       # new skill must appear with one-line summary
mvp skills show <id>  # full manifest YAML prints cleanly
mvp skills mcp  | jq length    # must be ≥ previous catalog size + 1
mvp skills openai | jq length  # same
```

The registry is auto-discovering — it walks `mvp/skills/**/manifest.yaml`
at startup and builds the catalog. If your skill doesn't appear, the
manifest didn't validate. Check `SkillManifest.load_from_yaml(path)`
directly and read the pydantic error.

---

## 12. Step 10 — run the full eval

```
mvp eval
```

Must still pass the §4.2 gates: **4/5 M-within-0.10**, **4/5 M-flag-match**,
**4/5 Z-within-0.10**, **4/5 Z-zone-match**, **100% citations resolved**,
**10/10 gold present** for the pre-existing skills. Your new skill's gate is
whatever its own manifest declares in `evaluation.eval_metrics`.

If the new skill pushes an existing metric below its threshold, that's a
regression. Diagnose before merging — don't loosen the gate.

---

## 13. Lessons-learned from Beneish + Altman (MVP Phase 3–4)

These war stories go into `workshop/docs/paper_onboarding_playbook.md` in
longer form. The bullets below are the operational callouts.

### Beneish-specific

- **The -1.78 vs -2.22 threshold trap.** The 1999 paper p. 16 says -1.78.
  The -2.22 you'll see in textbooks and `mvp_build_goal.md`'s original draft
  is from **Beneish, Lee & Nichols (2013)** — a different sample, later
  paper. Always cite the paper you're implementing; never copy from
  secondary sources.
- **TATA's 16-canonical approximation and the WorldCom consequence.** The
  paper's full TATA formula subtracts Δ Current Maturities of LTD and Δ
  Income Tax Payable, neither of which is a canonical line item in the 16
  we standardize at MVP. We ship TATA as `(ΔCA − ΔCL − D&A) / TA` with a
  `warning=tata_approximation` on every call. **WorldCom's M-score drifts
  by ~0.23 across the -1.78 threshold as a result** — the eval records it
  as an explainable_failure (not rescued by loosening gold). A future
  expansion to 20+ canonical line items would close the gap.
- **Enron's SG&A-combined-with-operating-expenses caveat.** Enron's 10-K
  doesn't report a separate SG&A line — it rolls SG&A into "Operating
  expenses." Our `selling_general_admin_expense` mapping picks up the
  combined figure and the SGAI component is flagged with
  `sga_combined_with_opex` context. Interpretation skills surface the
  warning; don't silently use the larger aggregate.
- **DEPI / SGAI / LVGI are weak signals.** The paper's own coefficients on
  these three are statistically insignificant. Don't write confident
  high-band interpretations for them — the rule templates call this out in
  each component's `contextual_caveats`.

### Altman-specific

- **X5 is 0.999, not 1.0.** Equation I of the 1968 paper prints the
  coefficient explicitly. Most textbooks round to 1.0. The drift is small
  (0.001 × X5, typically < 0.003) but carrying the paper-exact coefficient
  is discipline: if we round one coefficient because "it's close enough,"
  we will round the next one for the same reason.
- **Original 1968 Z (not Z'-prime from the 1983 book).** Z'-prime drops X5
  and re-estimates for non-manufacturers. Using it would let us score
  Carvana (which fails X3 in the original because its EBIT is null), but
  it's published in a book, not a paper — and "paper-derived" is the label
  on the skill. Staying faithful to the 1968 paper is how we earn the
  label.
- **Market value of equity is a fixture, not a line item.** X4 uses the
  issuer's market cap at fiscal-year-end, which is not in the 10-K. The
  `data/market_data/equity_values.yaml` fixture supplies it; the citation
  locator extends to `<fixture_file>::<cik>::<fye>` so a reviewer can
  resolve it back to source. This pattern extends to any paper that
  requires exogenous inputs.
- **WorldCom's market cap is an aggregate estimate.** The two tracking
  stocks (WCOM, MCIT) dropped from Yahoo after delisting.
  companiesmarketcap.com reports an aggregated $43.33B which we encode with
  `market_cap_source: estimated_from_aggregated_market_cap`. The skill
  emits `warning=market_value_estimated` and confidence drops by 0.15. A
  future paper that requires any post-bankruptcy market data will hit the
  same pattern — record the data-quality flag at ingestion time, not when
  the skill runs.

---

## 14. The `paper_examples/` corpus — what's next

Five PDFs sit at `/home/iv/research/Proj_ongoing/paper_examples/` queued for
post-MVP processing:

1. `fundamentals_text.pdf`
2. `J of Accounting Research - 2024 - KIM - Context‐Based Interpretation of Financial Information.pdf`
3. `s11142-025-09885-5.pdf` (Review of Accounting Studies)
4. `ssrn-4429658.pdf` (SSRN working paper)
5. `ssrn-4480309.pdf` (SSRN working paper)

Task #10 applies steps 1–12 above to each paper in sequence. The
**dual-growth directive** (SPEC_UPDATES.md §"2026-04-17 — `paper_examples/`")
requires that every paper grow both codebases:

**`mvp/` must grow** — at least one new shipped skill per paper. "This
paper doesn't yield a skill" is a research-design problem, not a skip-this
excuse. Either find the skill inside the paper, or escalate.

**`workshop/` must grow** — at every iteration:

- If formula extraction from the PDF was tedious, either write or improve
  `workshop/paper_to_skill/extract_paper.py`. Paper 1 creates a rough first
  version; paper 2 hardens it; by paper 5, it should be robust enough that
  onboarding is visibly faster.
- If the paper's worked-example replication needed a scaffold, either write
  or improve `workshop/paper_to_skill/replication_harness.py`.
- Append at least one lessons-learned callout to
  `workshop/docs/paper_onboarding_playbook.md`. War-story style, 2–3
  paragraphs per callout.
- If any playbook step felt ambiguous, codify the resolution — even a
  20-line CLI helper is worth committing.

**Cross-checks at the end of each paper:**

- `grep -R "from workshop" mvp/` still prints nothing (separation contract
  intact).
- `mvp eval` still green.
- `mvp.skills.registry` discovers one more skill.
- `workshop/docs/paper_onboarding_playbook.md` has at least one new
  section / callout.

Paper 5 is the regression bar: if paper 5 doesn't feel visibly faster than
paper 1, the workshop tooling didn't mature the way it was supposed to.

---

## 15. Workshop helpers as of Paper 4

The post-MVP `paper_examples/` workstream has so far landed four
helper scripts in this directory; each grew out of concrete pain
points during paper-onboarding:

- **`extract_paper.py`** — PDF → structured JSON of formulas /
  TOC / sha256. Paper 1 (`fundamentals_text.pdf`) wrote the first
  draft against working-paper PDFs. Paper 2 (Kim & Nikolaev 2024,
  J. Accounting Research) hardened it for journal-format PDFs:
  added the `equation_paren_label` pattern (Wiley-style end-of-line
  `(N)` equation labels), the `numbered_table_or_figure` pattern
  (cross-references like "table 7, panel A"), the
  `_strip_journal_footers` preprocessor (removes the per-page Wiley
  footer), and the `top_toc_sections` helper (filters TOC to top-N
  levels for paper-with-deep-TOC scanning). Hit-counts on Paper 2:
  ~57 paren-equations + ~57 table/figure references; Paper 1 was
  unaffected (regression-tested in `workshop/tests/`). Paper 3
  (Bernard et al. 2025, Review of Accounting Studies) used the
  existing Paper-2 patterns cleanly — ~60 table/figure references
  surfaced the paper's headline results in under a minute.

- **`inspect_canonical.py`** — prints a per-issuer table of which
  canonical line items are populated for the 5 MVP sample filings.
  Paper-2 added; the methodologist had assumed `net_income` was a
  canonical line item and silently failed for ~10 minutes when the
  loss signal returned null on every issuer. This helper surfaces
  gaps (Carvana's missing EBIT / D&A; WorldCom's missing inventory)
  in 30 seconds. Use BEFORE writing a paper-derived skill that needs
  specific line items, not after.

- **`draft_manifest.py`** — scaffold a `manifest.yaml` from a
  methodologist-notes file + a chosen layer. Paper-3 added; the
  variation across Papers 1-2's manifests had saturated enough that
  a scaffold generator paid for itself. The scaffold emits ~70% of
  what ends up shipping (skill_id / version / layer header, full
  provenance block, implementation_decisions stubs keyed off the
  notes' §(f) bullets, inputs/outputs skeleton appropriate to the
  layer, limitations[] populated from §(g), examples[] populated
  from §(e), confidence + dependencies skeletons). The engineer's
  hand-fill is the remaining ~30% (the skill math, the citation
  contract body, the confidence-model factors). Scaffold validates
  to a strict subset of every shipped paper-derived manifest
  (regression-tested in `workshop/tests/test_draft_manifest.py`).
  DOI extraction handles both Springer (10.1007/...) and Wiley
  (10.1111/...) citation styles.

- **`replication_harness.py`** — run a shipped skill's manifest
  `examples[]` block through the skill via the registry and report
  pass/fail per example. Paper-4 added; as of Paper 4 the
  `paper_examples/` workstream has shipped 4 L3 skills, each with
  an `examples[]` block listing MVP-sample inputs — the harness
  lets those declarative blocks drive a uniform live-run check
  without re-authoring per-skill imperative pytest code. Optional
  typed expectations (`expected_flag`, `expected_score_range`,
  `expected_score_tolerance`) drive per-example pass/fail; in
  their absence the harness does a loose liveness check (skill
  returned a non-error envelope). Papers 1-3's manifests predate
  the typed-expectation shape and currently liveness-only under
  the harness; a back-fill to add typed expectations is filed in
  `workshop/maintenance/README.md`. Tested against Paper 4's own
  manifest (3 examples, all liveness-pass) plus 16 pure-function
  unit tests on expectation-checking logic. CLI:
  `python -m workshop.paper_to_skill.replication_harness
  --manifest <path> [--verbose]`.

Still NOT here (deferred until a paper-onboarding iteration needs
them):

- `templates/manifest_scaffold.yaml` and `templates/rule_scaffold.yaml`
  — YAML starting points. `draft_manifest.py` now generates inline
  YAML, making standalone template files redundant. Will likely
  come back into play once two or three skill-layer variants
  (L1 fundamental, L4 composite) ship — currently all three papers
  have shipped L3 paper-derived skills.

The workshop directory still ships the **playbook in prose** as its
load-bearing artifact (`docs/paper_onboarding_playbook.md`); the
scripts earn their keep when there's enough variation across
papers that a copy-paste flow becomes painful.
