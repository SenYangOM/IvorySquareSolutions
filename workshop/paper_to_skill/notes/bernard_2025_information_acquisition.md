# Paper notes: `s11142-025-09885-5.pdf`

> Bernard, D., Cade, N. L., Connors, E. H., & de Kok, T. (2025).
> *Descriptive evidence on small business managers' information choices.*
> Review of Accounting Studies, 30, 3254–3294.
> DOI: 10.1007/s11142-025-09885-5. 41 pp. PDF sha256
> `1760a4c614f6051052beff0fad61587bdd344bea700f5205e24e5142399d8290`.

Author voice: `quant_finance_methodologist`. Expected reading time for
the skill reviewer behind me: 15 minutes.

---

## (a) Skill-scope decision

**Layer: L3 paper-derived. Skill id: `compute_business_complexity_signals`.**

Decision reached by running the workshop/paper_to_skill/README §5
decision tree. The paper is a **behavioral descriptive study** using
proprietary retail-cannabis point-of-sale data and Headset, Inc.
business-intelligence tracking logs — a setting worlds away from SEC
10-K filings. Three candidate constructs presented themselves, each
with a different feasibility profile:

1. **The headline hedonic-asymmetry finding** (Section 5, Table 5).
   Managers open the daily email more often after high-sales days
   than after low-sales days, even holding store-specific fixed
   effects and the number of transactions constant. **Not shippable
   at MVP scope.** The test requires daily email-open logs from
   Headset's embedded-pixel tracking + per-store per-day sales data
   (946 stores × ~365 days = 345k store-days in the paper's panel).
   Neither exists for SEC public-company filings. Public-company
   analogs would be 8-K timing relative to earnings news (Kothari-
   Shu-Wysocki 2009) or insider-trading-pattern asymmetry — those
   are different constructs entirely, not faithful ports of this
   paper's empirical test.

2. **Store × week future-performance predictability** (Section 6,
   Table 8). "More info-acquisition days in week t predicts higher
   sales in week t+1." Depends on the same Headset tracking logs;
   the public-company analog would be "does executive-attention-
   to-disclosure-data predict future firm performance?" which is
   an entirely different research design. **Not shippable.**

3. **Section 4 / Table 3 determinants of information-acquisition
   intensity.** The paper regresses monitoring-service-use
   intensity (percentage of days email opened, mean daily opens) on
   a set of **deterministic store-level business-characteristic
   variables**:
   - `Average sales` (log-level of daily sales) — coef +0.003***
     on extensive-margin email opens
   - `Sales volatility` (CV = std/mean of daily sales) — coef
     −0.098*** (volatile stores monitor LESS — unintuitive but
     robust)
   - `Average category HHI` (product-mix concentration) — coef
     −0.078, not significant
   - `Single store` (is the store a one-off vs part of a chain) —
     coef −0.100*** (chains monitor MORE)
   - `Parent number of states` — coef −0.012, not significant for
     email; +0.174*** for dashboards (multi-state chains use
     dashboards more)
   - `Late joiner` (joined during sample) — coef −0.205***
   - `Sells medical` — coef −0.183***

   The economic story is: **business complexity + scale drive
   monitoring intensity; volatility reduces it (perhaps because
   small, new, volatile stores haven't set up mature reporting
   workflows).** These determinants are analogs of public-company
   characteristics — size, operational complexity, stability — each
   of which maps to canonical 10-K line items or the existing
   market-data fixture. **THIS IS THE SHIPPABLE CONSTRUCT.**

**Decision: ship option 3 — `compute_business_complexity_signals`.**
It emits three firm-year signals from the paper's Table 3 Panel a
extensive-margin specification (the most-cited headline determinant
results) that are computable from canonical line items, plus a
composite **business_complexity score** (a 0–1 rating aggregating
the signals using weights derived from Table 3 Panel a's reported
|t-statistics|). Output flag: `complex_monitoring_intensive`,
`moderate_monitoring_intensity`, `simple_monitoring_light`,
`indeterminate`. Citations back to canonical line items. Per-component
severity bands governed by a rule template. Same per-signal trace
shape as the other paper-derived skills.

This is a NEW analytical lens in the catalogue. The existing 9 skills
score firms on distress (Altman), manipulation (Beneish), narrative
structure (Upfrontedness), narrative-context-need (Context-Importance).
This skill scores firms on **operational complexity as a driver of
monitoring-service demand** — i.e. for a given filing, does the firm's
business profile suggest intense managerial information needs? It's
a structural-complexity signal that an agent might combine with
Upfrontedness or Context-Importance for a richer view of "does this
firm's reporting environment call for closer scrutiny?"

Options 1 and 2 are deferred to the future-candidates list at the
bottom of this file.

## (b) What the paper/text offers that the current catalogue lacks

The current 9-skill catalogue (after Paper 2) has zero skills that
quantify **firm-level operational complexity as a driver of
information-use intensity**. Altman/Beneish/Upfrontedness/Context-
Importance all describe distress, manipulation risk, narrative quality,
or context need. None describe the structural complexity of the firm's
operations as predictor of monitoring demand. Bernard et al.'s
Table 3 Panel a is the cleanest published anchor I've seen for this
concept in accounting — the three dominant coefficients (size,
volatility, single-store) map to public-firm analogs cleanly.

Composability win: the score is a per-filing scalar plus a per-signal
trace, both of which downstream L4 composites can consume. A natural
composite would be: "high business_complexity + low Upfrontedness"
(firm has complex operations but its narrative is back-loaded —
reporting mismatch), or "high business_complexity + high context-
importance" (firm is complex AND the paper predicts context should
help — the MD&A is a high-priority read for this firm).

## (c) Formulas identified

**Section 4 Table 3 Panel a column 1 coefficients (extensive-margin
email open on store-day-level):**

The paper does not print closed-form single-variable definitions — it
lists the regressors directly. The coefficients that serve as the
weight source:

| Paper variable        | Coefficient | Std. Err. | |t| | Publication weight |
| ---                   | ---:        | ---:      | ---:| ---:               |
| `Average sales`       | 0.003***    | 0.001     | 3.0 | size_signal        |
| `Sales volatility`    | −0.098***   | 0.035     | 2.8 | stability_signal   |
| `Single store`        | −0.100***   | 0.027     | 3.7 | complexity_signal  |

We port each variable to a public-company-filing analog and build
binary indicators. Absolute t-statistics become the composite weights
(so sign-reversed coefficients in the paper become "inverse
indicators" — we capture the paper's direction by defining the
binary the other way rather than by giving it a negative weight).

**Our three analog signals:**

1. **size_signal** (Table 3 "Average sales" positive predictor):
   `size_signal = 1 if revenue_t >= $1,000,000,000 else 0`
   Source: `revenue` canonical line item.
   The paper's "Average sales" is daily store-level sales; the
   binary-large-cap threshold of $1B is a practitioner default for
   "large firm" in US public-company analysis, two orders of
   magnitude above mid-cap and three above small-cap.

2. **stability_signal** (Table 3 "Sales volatility" **negative**
   predictor — so stable firms fire, not volatile ones):
   `stability_signal = 1 if abs(Revenue_t − Revenue_{t-1}) / Revenue_{t-1} <= 0.10 else 0`
   Source: `revenue` canonical line item (current year + prior year).
   The paper's CV-based Sales volatility uses daily-within-store
   variation; we have only annual revenue — so we use a 2-period
   YoY growth-absolute-magnitude proxy. Threshold 10% is a standard
   "stable-growth" practitioner cutoff. Sign-reversed: the paper
   says volatile firms use less monitoring, so we encode
   "low-volatility" (i.e. stable) firms as firing the signal.

3. **complexity_signal** (Table 3 "Single store" **negative**
   predictor — so multi-entity chains fire, not singletons):
   `complexity_signal = 1 if sga_to_revenue_t >= 0.15 else 0`
   Source: `selling_general_admin_expense` + `revenue` canonical
   line items.
   The paper's "Single store" is a binary "chain vs one-off" —
   not directly observable from a 10-K. SG&A-to-revenue ratio is a
   defensible proxy: multi-entity corporate structures maintain
   larger overhead (SG&A) relative to revenue than simple
   single-unit businesses. Threshold 15% is a practitioner cutoff
   that separates "overhead-light" operations from "substantial
   corporate overhead" firms. Sign-reversed via the proxy
   construction: high SG&A-intensity fires, low SG&A-intensity
   doesn't.

**Composite business_complexity score:**

We aggregate the three signals into a single 0-1 score using fixed
weights derived from |t-statistics| in Table 3 Panel a column 1:

    size_signal         |t| = 3.0
    stability_signal    |t| = 2.8  (from -0.098 / 0.035)
    complexity_signal   |t| = 3.7  (from -0.100 / 0.027)

These three are normalised into weights summing to 1.0:

    w_size       = 3.0 / 9.5 = 0.3158
    w_stability  = 2.8 / 9.5 = 0.2947
    w_complexity = 3.7 / 9.5 = 0.3895

The score is a weighted sum of the three binary indicators:

    business_complexity =
          w_size         · I[revenue_t >= $1B]
        + w_stability    · I[|Revenue_t − Revenue_{t-1}|/Revenue_{t-1} <= 0.10]
        + w_complexity   · I[sga_to_revenue_t >= 0.15]

The four dropped Table 3 regressors are documented in
`implementation_decisions`:
- `Average category HHI` (not significant)
- `Parent number of states` (not significant for email extensive
  margin)
- `Late joiner` — a time-series-specific control for Headset's
  sample period, no public-company analog
- `Sells medical` — an industry-specific control with no analog

## (d) Threshold values

**Per-component bands** (binary indicator thresholds, see (c) above):

- **size_signal** fires when revenue_t ≥ **$1,000,000,000**
  ("large cap" practitioner cutoff).
- **stability_signal** fires when
  |ΔRevenue| / Revenue_{t-1} ≤ **0.10** ("stable growth"
  practitioner cutoff).
- **complexity_signal** fires when
  SG&A / Revenue ≥ **0.15** ("substantial corporate overhead"
  practitioner cutoff — e.g. WorldCom FY2001 SG&A/Rev ≈ 0.20;
  Apple FY2023 ≈ 0.07; Microsoft FY2023 ≈ 0.13).

**Composite flag bands** (on business_complexity score in [0, 1]):

- **complex_monitoring_intensive** — score ≥ 0.60 (at least two
  of the three signals fired; the paper predicts this firm's
  managers have the strongest demand for monitoring tools).
- **moderate_monitoring_intensity** — 0.30 ≤ score < 0.60 (one
  signal firing; moderate monitoring demand).
- **simple_monitoring_light** — score < 0.30 (zero signals;
  the firm's profile is a low-complexity, low-size, volatile
  one where the paper predicts lighter monitoring-tool usage).
- **indeterminate** — when revenue_t is missing OR when size +
  complexity both can't compute AND stability also can't
  (needs prior year).

The bands are paper-anchored in the sense that the WEIGHTS come
from Table 3 Panel a |t-statistics|; the BANDS themselves are a
presentation convention (equally-spaced cuts at 0.30 and 0.60,
matching the compute_context_importance_signals convention).
Documented as a presentation convention in the rule template, not
represented as paper-exact.

## (e) Worked examples referenced in the text

The paper publishes NO firm-level business_complexity scores — it
publishes store-level coefficient estimates (Table 3) and summary
statistics (Table 2). These are aggregates over 946 stores in the
email sample; they are not directly comparable to a single-firm
score.

Replication strategy: the paper-replication test asserts
**signal-level paper-faithfulness** rather than score-mean matching:

1. **Weight derivation faithfulness.** The three shipped weights
   must match the normalisation of Table 3 Panel a column 1
   absolute t-statistics: {size=3.0, stability=2.8, complexity=3.7}.
   Sum 9.5. Within 1e-3.
2. **Per-signal threshold faithfulness.** The three binary cutoffs
   match the practitioner-derived defaults ($1B, 10%, 15%)
   documented in the rule template.
3. **Signal-level monotonicity.** Synthetic firm-year fixtures hit
   each band correctly: a $5B-revenue fixture fires size; a stable
   (≤10% YoY growth) fixture fires stability; a high-SG&A-intensity
   fixture fires complexity; etc.
4. **Composite arithmetic.** When all three signals fire, score =
   1.0 (within float tolerance); when none fire, score = 0.0; when
   only size fires, score = w_size = 0.3158. Tests the weighted-sum
   implementation against the documented weights.
5. **Sign-reversal faithfulness.** Because two of the three
   indicators encode the paper's NEGATIVE coefficients via sign-
   reversal in the binary, a dedicated test confirms:
   - A volatile firm (|ΔRev/Rev| > 0.10) does NOT fire stability
   - A stable firm (|ΔRev/Rev| ≤ 0.10) DOES fire stability
   - A low-SG&A firm (SG&A/Rev < 0.15) does NOT fire complexity
   - A high-SG&A firm (SG&A/Rev ≥ 0.15) DOES fire complexity
6. **Sample-firm sanity check (soft).** On the 5 MVP filings:
   - **Apple FY2023**: revenue ≈ $383B → size fires; YoY revenue
     change ≈ −3% → stability fires; SG&A/Rev ≈ 0.07 → complexity
     does NOT fire. Expected score ≈ 0.3158 + 0.2947 = 0.6105 →
     **complex_monitoring_intensive** (just over threshold).
   - **Microsoft FY2023**: revenue ≈ $212B → size fires; YoY ≈ +7%
     → stability fires; SG&A/Rev ≈ 0.13 → complexity does NOT
     fire. Expected similar to Apple.
   - **Enron FY2000**: revenue ≈ $100B → size fires; YoY ≈ +150%
     (notoriously inflated) → stability does NOT fire; SG&A/Rev
     low → complexity does NOT fire. Expected
     **moderate_monitoring_intensity** (size only).
   - **WorldCom FY2001**: revenue ≈ $35B → size fires; YoY ≈ +4%
     → stability fires; SG&A/Rev ≈ 0.19 → complexity fires (all
     three). Expected
     **complex_monitoring_intensive** (score ≈ 1.0).
   - **Carvana FY2022**: revenue ≈ $13B → size fires; YoY ≈ 0%
     → stability fires; SG&A/Rev ≈ 0.20 → complexity fires (all
     three). Expected **complex_monitoring_intensive**.
   The soft band is `score ∈ [0, 1]` and `flag != null` for all 5;
   no tighter expectations are encoded.

## (f) Implementation decisions

Documented in the manifest's `implementation_decisions[]`:

1. **The paper's headline hedonic-asymmetry finding is NOT
   implemented.** The paper's Section 5 / Table 5 tests "good-news
   consumption asymmetry" using Headset email-open logs — daily
   micro-level managerial behaviour that has no counterpart in
   SEC filings. We do NOT try to port this via 8-K timing, insider
   trading, or other indirect proxies — those would be different
   papers entirely. The skill ships only Section 4 / Table 3's
   **determinants framework**: what firm characteristics predict
   monitoring-service demand? That port is defensible; an
   asymmetric-news-consumption port is not.

2. **Three analog signals, not the paper's six store-level
   regressors.** Table 3 Panel a has 6 regressors; we ship 3. Kept:
   size (Average sales, +coef), stability (Sales volatility, −coef
   → sign-reversed), complexity (Single store, −coef → proxied via
   SG&A/Revenue). Dropped: `Sells medical` (industry control, no
   analog), `Late joiner` (sample-period-specific control, no
   analog), `Parent number of states` (not significant on email
   extensive margin; would require a segments-count proxy we don't
   have), `Average category HHI` (not significant). The three kept
   signals are the three statistically significant generalisable
   determinants.

3. **Size threshold is $1B revenue (public-firm "large-cap"
   cutoff), not log-transformed.** The paper uses log(average
   sales). Our binary indicator fires at revenue_t ≥ $1B, which
   corresponds to log10(rev) ≥ 9.0. A log-continuous version would
   align more exactly with the paper's linear specification, but
   since we bundle everything into a binary-sum composite at MVP,
   a binary threshold is simpler and matches the paper's high-vs-
   low partition story. Documented; a future continuous-score
   variant is filed as post-MVP expansion.

4. **Stability-signal sign-reversal vs the paper's coefficient.**
   The paper's Sales volatility coefficient is NEGATIVE: volatile
   stores monitor LESS. To make the composite uniformly positive
   ("higher score = more monitoring demand"), we flip the indicator
   definition: instead of `I[volatility > threshold]` with negative
   weight, we use `I[volatility ≤ threshold]` (i.e. "stable" firm)
   with positive weight. The economic meaning is preserved. Signed
   explicitly in manifest so a reviewer doesn't mistake this for a
   coefficient-sign bug.

5. **Complexity-signal is SG&A/Revenue, not Single-store.** The
   paper's `Single store` binary is natively observable — the
   store is either part of a chain or isn't. In the 10-K context,
   the closest analog is the segment-count reported in the
   segment footnote (not part of our 16 canonical line items) or
   the SG&A-intensity ratio (proxy for corporate-overhead
   footprint). We pick SG&A/Revenue because it's computable from
   canonical line items we have. Drift: a firm with high SG&A but
   a single operating segment (e.g. a tech firm with big R&D)
   would fire complexity but wouldn't match the paper's "chain"
   concept. A future multi-segment analysis would tighten this.

6. **Stability proxy uses 2-period YoY, not within-period CV.**
   The paper's Sales volatility is the within-store CV of daily
   sales (std/mean over ~365 days). We have annual financial
   statements only — no within-year daily revenue. We use
   `|ΔRevenue|/Revenue_{t-1}` as a 2-period stability proxy. Same
   shape as compute_context_importance_signals' 2-period volatility
   proxy for the Dichev-Tang construct. Warning
   `stability_two_period_proxy` on every non-null call.

7. **Per-component thresholds are practitioner-derived, not
   paper-published.** The paper's regressors are continuous linear
   terms with no partitions. We use fixed-point thresholds that
   approximate common practitioner large-cap / stable-growth /
   high-overhead cutoffs. Documented in the rule template,
   editable by an accounting expert.

8. **Indeterminate when revenue_t is missing.** Revenue is the
   denominator for two of three signals and the threshold input
   for the first. If revenue_t is null, none of the three signals
   can be evaluated → score null, flag indeterminate. If only
   stability can't compute (no prior-year data), the signal is
   null and treated as "off" — same conservative under-count
   approach as compute_context_importance_signals.

9. **Composes via canonical statements; does NOT delegate to any
   sub-skill via the registry.** The three signals are purely
   line-item arithmetic. Pairs with compute_mdna_upfrontedness
   or compute_context_importance_signals in a future L4 composite;
   no direct sub-skill calls in this skill.

## (g) Limitations (goes into manifest `limitations[]`)

- The paper's headline hedonic-asymmetry finding (Section 5,
  Table 5) is NOT implemented. The three shipped signals are the
  Section 4 Table 3 determinants framework only — they describe
  the firm's business profile as a predictor of monitoring
  demand, not the paper's behavioural asymmetry phenomenon.
- The sample the paper's determinants were estimated on is **946
  retail-cannabis dispensary stores** (private, US, 2019-2022).
  Porting the coefficients to US-public-company filings is an
  analog — an accountant calibrating on a public-company panel
  would likely find different coefficient magnitudes. The weights
  are paper-anchored for directionality and relative importance,
  but absolute calibration is not claimed.
- Stability uses a 2-period YoY-revenue proxy for the paper's
  within-store daily-sales CV. Systematically under-reports
  volatility for firms whose annual revenue happens to be similar
  in t and t-1 but variable within-year (seasonal businesses,
  firms with one-off charges).
- Complexity uses SG&A/Revenue as a proxy for the paper's
  `Single store` chain-vs-singleton binary. A firm with high SG&A
  but a simple single-segment structure (e.g. a tech firm with
  heavy R&D in SG&A) would fire complexity without matching the
  paper's chain concept.
- Size threshold ($1B revenue) is a practitioner large-cap cutoff,
  not a paper threshold. The paper's Average sales regressor is
  continuous linear; our binary discretisation loses information.
- Per-component thresholds are practitioner-derived defaults, not
  paper-published. Editable in the rule template; a population-
  anchored variant would be cleaner.
- Pre-iXBRL filings (Enron, WorldCom) carry the standard
  `pre_ixbrl_manual_extraction` confidence penalty (−0.15) per
  the established skill convention.
- Not a governance verdict. A `complex_monitoring_intensive` flag
  means the paper's model predicts this firm's managers would
  demand intense monitoring tools — it does not say whether the
  firm's actual disclosure practices or investor-facing reporting
  are high-quality. Pair with compute_mdna_upfrontedness or
  compute_context_importance_signals for complementary lenses.

## (h) What I leveraged from Papers 1+2's workshop deliverables, and what I improved

**What I used:**
- `workshop/paper_to_skill/extract_paper.py` — ran on Paper 3
  first-thing. Paper 3 is a Springer journal (not Wiley), so the
  `_strip_journal_footers` regex doesn't fire on this PDF's
  Springer footers (they're shorter and don't match the Wiley
  signature) — but the paren-equation-label and numbered-table-
  or-figure patterns hit ~60 table/figure references cleanly,
  surfacing the paper's Table 3 + Table 5 + Table 7 headline
  results in under a minute. Paper 2's journal-format support was
  directly useful here.
- `workshop/paper_to_skill/inspect_canonical.py` — ran BEFORE
  committing to a skill input shape. Confirmed revenue,
  selling_general_admin_expense are populated for all 5 issuers;
  prior-year filings available for all 5. This let me pick
  `revenue` + `sga/revenue` over alternatives like `inventory/
  revenue` (WorldCom's inventory is missing) or `total_debt/
  total_assets` (slower to read).
- `workshop/paper_to_skill/notes/kim_2024_context_based_interpretation.md`
  shape — same (a)..(h) section structure. The (h) section format
  Paper 2 introduced is now established.
- `workshop/docs/paper_onboarding_playbook.md` "When the unreleased
  ML model has NO honest proxy" callout — applied directly.
  Paper 3's headline is behavioural-empirical with proprietary
  data, which is the same "no honest proxy for the headline"
  situation as Paper 2, but for a different reason (data not
  model). The playbook callout's "scan elsewhere in the paper
  for a deterministic construct" rule pointed me at Section 4 /
  Table 3.
- `mvp/skills/paper_derived/compute_context_importance_signals/`
  manifest + skill + rule-template shape — adopted the
  weighted-sum-of-binary-indicators shape, the
  signal/component/weight/composite output layout, the
  indeterminate-when-primary-input-missing semantics, the
  presentation-band thresholds with explicit-convention
  documentation, and the confidence-capping-with-proxy pattern.
- `mvp/ingestion/papers_ingest.py:ingest_local_paper` —
  unchanged. Added the third `LocalPaperRef` entry using the
  established pattern from Papers 1 and 2.
- `mvp/eval/gold_loader.py:_SCORE_KEYS` — Paper 2 added this
  extensibility table. Paper 3 adds its own
  `compute_business_complexity_signals → business_complexity_score`
  entry in one line.
- `mvp/engine/citation_validator.py` unchanged. My skill uses only
  canonical-line-item citations (no MD&A, no market-data) so no
  resolver branch is needed.

**What I improved (workshop deltas, Paper 3):**

- **`workshop/paper_to_skill/draft_manifest.py` (NEW — first
  version).** This is the option-(b) deliverable of the dual-growth
  directive's workshop minimum. Given a paper-notes file and a
  chosen layer (L1/L2/L3), it emits a skeleton `manifest.yaml`
  with:
   - `skill_id`, `version`, `layer`, `status`, `maintainer_persona`
     pre-filled from notes metadata;
   - `provenance.source_papers[]` entry constructed from the
     notes' citation block + the Paper-onboarding-ingested PDF
     path + pdf_sha256;
   - `provenance.methodology.formulas_extracted_from_paper`
     populated from the notes' §(c) headers;
   - `implementation_decisions[]` populated as TODO stubs keyed
     off the notes' §(f) bullets;
   - `inputs` / `outputs` shapes that match the skill's layer
     (L3 composites emit score/flag/signals/weights/citations);
   - `limitations[]` populated from the notes' §(g) bullets;
   - `examples[]` populated from the notes' §(e) worked-examples
     section.
  Tested against Paper 3's own notes file as the first regression
  case — the emitted scaffold is ~70% of what ended up shipping
  (the manual fill-in is ~30%), which is the right level of
  leverage for a first version. The existing Paper 1 / Paper 2
  manifests are used as NON-regression references: re-running
  draft_manifest against their notes files produces skeletons
  that are strict-sub-structures of what shipped (the emitted
  scaffold is a subset of the final manifest; the final manifest
  has additional hand-written fields the scaffold intentionally
  doesn't guess at).
- **Playbook callout (NEW — Paper-3-specific).** Added
  **"When the paper's setting is worlds-away from public companies
  (private, behavioural, proprietary-data): port the determinants
  framework, not the behavioural finding."** The 2-3-paragraph
  write-up goes into `workshop/docs/paper_onboarding_playbook.md`.
- **`workshop/paper_to_skill/README.md`** updated with a pointer
  to `draft_manifest.py` (previously marked "deferred until a
  paper-onboarding iteration needs it" — Paper 3 needed it).

## Candidates for future papers

This paper yields two plausible deferred skills, each its own
paper-to-skill cycle:

1. **`compute_monitoring_asymmetry_signals`** — L3 paper-derived
   (post-MVP). Attempts a public-company analog of Section 5's
   hedonic-asymmetry test by combining 8-K timing (Kothari-Shu-
   Wysocki 2009 "managers delay bad news") with earnings-surprise
   direction. Needs 8-K filing metadata we don't ingest today
   and an earnings-surprise fixture we'd have to build. Filed
   for year-2 consideration when the corpus expands beyond 10-K.
2. **`compute_information_acquisition_score`** — L3 paper-
   derived (post-MVP). Ports the Section 6 week-level sales-
   prediction model: "does executive attention to internal
   reporting predict firm performance?" The public-company
   analog would need executive-attention proxies (Form 4
   filings, management-commentary cadence) plus subsequent
   earnings — an entirely different research design from the
   current paper's. Filed for year-3+ when the corpus includes
   insider-trading and disclosure-timing datasets.

Both deferred because: (a) the Section 4 Table 3 determinants
framework is the sharpest single per-firm-year construct this
paper offers without the proprietary Headset-tracking data,
(b) the playbook's "ship ONE per iteration" rule holds, (c) the
9→10 skill increment plus the new business-complexity axis is
dual-growth-sufficient for this iteration.
