# compute_nonanswer_hedging_density

Paper-derived L3 skill that applies de Kok (2024) Online Appendix OA 3's
78-token non-answer keyword filter to a US public 10-K MD&A, producing
a scalar `hedging_density` in [0, 1] and a three-band flag
(`low_hedging` | `typical_hedging` | `high_hedging` | `indeterminate`).

**Paper.** de Kok, T. (June 2024). *ChatGPT for Textual Analysis? How
to use Generative LLMs in Accounting Research.* University of Washington
working paper, SSRN 4429658. PDF sha256
`2650e3e5c853a8ca1d7dae8e14622c64617e295e75b9d4407f0e84bccd79ba4a`.

## What it does

Given a 10-K CIK + fiscal year end, the skill:

1. Delegates MD&A extraction to `extract_mdna` via the registry.
2. Sentence-tokenises the MD&A text on `[.!?]\s+`, dropping fragments
   shorter than 30 characters (list markers, section headers).
3. For each sentence, case-insensitively matches against the paper's
   78-token keyword list:
   - **7 trigrams:** `call it out`, `at this time`, `at this point`,
     `at this moment`, `break it out`, `don t have`, `don t know`.
   - **23 bigrams:** `not going`, `will not`, `won t`, `by region`,
     `get into`, `that level`, `are not`, `don t`, `do not`, `give you`,
     `break out`, `splice out`, `tell you`, `too early`, `can t`,
     `can not`, `not ready`, `right now`, `no idea`, `not give`,
     `not sure`, `wouldn t`, `haven t`.
   - **48 unigrams:** `cannot`, `comment`, `commenting`, `comments`,
     `unable`, `guidance`, `guide`, `guiding`, `forward`, `hard`,
     `talk`, `range`, `disclose`, `report`, `privately`, `forecast`,
     `forecasts`, `forecasting`, `specific`, `specifics`, `detail`,
     `details`, `public`, `publicly`, `provide`, `breakout`,
     `statement`, `statements`, `update`, `announcement`,
     `announcements`, `answer`, `answers`, `quantify`, `share`,
     `sharing`, `information`, `discuss`, `mention`, `sorry`,
     `apologies`, `apologize`, `recall`, `remember`, `without`,
     `specifically`, `difficult`, `officially`.
4. Computes `hedging_density = (sentences with ≥1 hit) / total sentences`.

The keyword list is reproduced verbatim from OA 3 p. ix. Unigrams match
as whole words (`\b<word>\b`); bigrams/trigrams match as whitespace-
normalised word sequences after apostrophe stripping so `don't` matches
`don t` and `can't` matches `can t`.

## Substrate port

**This skill ports the paper's filter to MD&A, not the paper's earnings-
call Q&A substrate.** MVP does not ingest earnings-call transcripts;
the linguistic phenomenon the filter detects (hedging, non-disclosure,
forward-looking caveat) generalises to MD&A narrative, so applying the
paper's keyword list there is a defensible port. The paper's reported
performance statistics (96% accuracy / 87% non-answer F1 / 70% error-
rate reduction vs Gow et al. 2021, Table 1 Column 6) are EARNINGS-CALL
SPECIFIC and do not apply to MD&A density.

Every non-null call emits
`substrate_port_mdna_vs_earnings_call`. Confidence is capped at 0.7
while the substrate-port approximation is active.

## Flag bands

- `low_hedging` — density < 0.15
- `typical_hedging` — 0.15 ≤ density < 0.35
- `high_hedging` — density ≥ 0.35
- `indeterminate` — MD&A not located OR fewer than 10 valid sentences

**Bands are presentation conventions, NOT paper thresholds** (the paper
has no MD&A-specific cutoffs). Editable by an accounting expert without
Python (P1) in `mvp/rules/templates/nonanswer_hedging_density_components.yaml`.

## Example

```python
from mvp.skills.registry import default_registry

skill = default_registry().get("compute_nonanswer_hedging_density")
result = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
print(result["hedging_density"], result["flag"])
# → 0.126437 low_hedging
```

## Composition

`compute_nonanswer_hedging_density` pairs naturally with
`compute_mdna_upfrontedness`:

- Upfrontedness scores POSITIONAL structure (is the heavy content up
  front or at the back?).
- Hedging density scores LINGUISTIC content (is the text specific or
  hedged?).

A future L4 composite could combine both: "high Upfrontedness + low
hedging" (firm front-loads content and speaks specifically) is a
disclosure-quality upper bound; "low Upfrontedness + high hedging"
(firm buries content AND hedges) is a red-flag pattern.

## Not a disclosure-quality verdict

A `high_hedging` flag says the MD&A uses a lot of non-disclosure
language; it does NOT say the disclosure is LOW-QUALITY. Firms facing
material uncertainty (litigation, going-concern doubt, restructuring)
legitimately hedge. Pair with Altman Z / Beneish M for the financial
axis.

## References

- Paper: `/data/papers/dekok_2024_gllm_nonanswers.pdf`.
- Methodologist notes:
  `workshop/paper_to_skill/notes/dekok_2024_gllm_nonanswers.md`.
- Rule template:
  `mvp/rules/templates/nonanswer_hedging_density_components.yaml`.
- Paper-replication test:
  `mvp/tests/integration/test_compute_nonanswer_hedging_density_paper_replication.py`.
- Gold case:
  `mvp/eval/gold/nonanswer_hedging_density/carvana_2022.yaml`.
