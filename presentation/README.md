# `presentation/` — pitch deck + landing-page copy

Source materials for the seed pitch deck and the public landing page. Two surfaces, one set of underlying content files. Voice is analytical and hedged (matches `../deep_research_report.md`); no fabricated customers, no invented metrics, every number traceable.

## How to use these materials

- **For the pitch deck:** open `index.html` in any modern browser. Self-contained single file — inline CSS, no external dependencies. Scroll-based with anchor navigation in the top bar; left/right arrow keys also jump between slides. Print-safe (`@media print` rules render one slide per page).
- **For the landing page:** copy from `landing_page_copy.md`. Second-person voice, ≈720 words, ready to paste into a static-site generator or CMS.
- **For deeper investor follow-up:** the `content/*.md` files are the long-form expansions of each deck slide. They are the source of truth for the deck — every TL;DR in the deck is lifted from the corresponding content file.

## File index

| File | Purpose | Length |
|---|---|---:|
| `README.md` | This file | ~80 lines |
| `index.html` | The pitch deck — self-contained, single file, inline CSS, optional JS | 16 slides |
| `landing_page_copy.md` | Marketing copy for the public landing page (hero / features / skills / FAQ / CTA / footer) | ~720 words |
| `content/01_problem.md` | The problem — public-company disclosures are machine-readable in format but not in interpretation | ~600 words |
| `content/02_solution.md` | The solution — skills API with two-stage thesis and three product guarantees (P1/P2/P3) | ~700 words |
| `content/03_product.md` | Layered architecture — 6 internal layers + 3 external; the rule-set ↔ engine separation | ~750 words |
| `content/04_skills_catalogue.md` | All 12 current skills with `description_for_llm` text + deferred-candidate skills | ~1,800 words |
| `content/05_moat_and_defensibility.md` | The four pillars (expert YAML, citation provenance, paper-faithful L3, agent-native) | ~1,000 words |
| `content/06_market_and_segments.md` | Illustrative TAM/SAM/SOM + four buyer segments with hypotheses | ~900 words |
| `content/07_competitive_landscape.md` | vs terminals, vs AI search, vs analyst-model vendors, vs foundation models, vs GPT-Rosalind | ~800 words |
| `content/08_traction_and_mvp_status.md` | The "it's real" page — actual numbers from `mvp/BUILD_STATE.json` | ~1,100 words |
| `content/09_how_it_works_for_agents.md` | P3 in detail — MCP/OpenAI catalogs, structured errors, natural-agent test, the headline call pattern | ~1,000 words |
| `content/10_roadmap_and_coverage_plan.md` | Coverage tiers, skill-library targets, multi-jurisdiction Year-2 commitments, gotchas | ~900 words |
| `content/11_team_and_execution.md` | Founder/team placeholders + the measurable-cadence claim | ~600 words |
| `content/12_ask_and_use_of_funds.md` | Round terms placeholders + four hires + 18-month milestone grid | ~800 words |
| `assets/` | Empty directory (CSS is inlined in `index.html`; preserved for future static assets) | — |

## Source-of-truth notes

- The skills catalogue (`content/04_skills_catalogue.md` and the corresponding section of `index.html`) is generated from the live registry. To regenerate after a skill is added, removed, or reworded:

  ```bash
  cd ../mvp && .venv/bin/python -m mvp.cli.main skills list
  ```

  Each skill's `description_for_llm` is in the manifest at `mvp/skills/<layer>/<skill_id>/manifest.yaml`. Use those texts verbatim — they were authored for LLM readers and they read well for human investors too.

- Numeric claims in `content/08_traction_and_mvp_status.md` are pulled from `../mvp/BUILD_STATE.json`. Refresh when the build state advances:
  - `final_gate_report.gate_*` — the seven final gates.
  - `post_mvp_workstream.papers_processed[*].wall_clock_minutes_approx` — the 5-paper compounding sequence.
  - `phase_artifacts.phase_*` — phase-by-phase test counts and demo outputs.

- TAM / SAM / SOM and pricing come from `../deep_research_report.md`. Preserve the "illustrative" labels and the "to be re-parameterized after pilots" caveats — the report's discipline is load-bearing.

## Style notes

- **Voice.** Analytical and hedged ("likely," "illustrative," "assumption"). Match `../deep_research_report.md`. No "revolutionize the industry" language. No promotional absolutes.
- **No fabrication.** No invented customers, no pretend logos, no testimonials. Pre-revenue and design-partner-conversations-in-progress is honest and is enough.
- **Cite real papers and real standards.** The deck names Beneish 1999, Altman 1968, Kim et al. 2024, Bernard et al. 2025, etc. — actual published sources with actual fixtures in the repo.
- **Hedge sized markets.** Every TAM / SAM / SOM number is illustrative with stated assumptions.

## Placeholders the founder needs to fill in before sending

The deck and the content files leave bracketed `[TOKEN]` strings for the founder to populate. List in order of priority:

1. **`[FOUNDER_NAME]`** — Founder/CEO name. *Files:* `index.html` (title slide, contact slide, team slide), `content/11_team_and_execution.md`, `landing_page_copy.md` (footer mailto).
2. **`[FOUNDER_EMAIL]`** — Founder contact address. *Files:* `index.html` (title + contact), `landing_page_copy.md` (hero + CTA + footer).
3. **`[COMPANY_NAME]`** — Legal/marketing company name. *Files:* `index.html` (top nav, contact, title meta), `landing_page_copy.md` (footer).
4. **`[ENGINEERING_LEAD]`** — Engineering lead/founding engineer. *Files:* `index.html` (team slide), `content/11_team_and_execution.md`. *Hint: the build's SEC User-Agent string declares "Sen Yang sy2576@stern.nyu.edu" per `mvp_build_goal.md` §13 decision 2 — confirm before publishing.*
5. **`[FOUNDING_TEAM]`** — Other founding-team names + roles, or omit. *Files:* `index.html` (team slide), `content/11_team_and_execution.md`.
6. **`[ADVISORS]`** — Advisor names + affiliations + areas of advice. *Files:* `index.html` (team slide), `content/11_team_and_execution.md`.
7. **`[ROUND_SIZE]`**, **`[VALUATION]`**, **`[LEAD]`**, **`[BRIDGE_TERMS]`** — Round terms. *Files:* `index.html` (ask slide), `content/12_ask_and_use_of_funds.md`.
8. **`[COVERAGE_M6]` / `[SKILLS_M6]` / `[GOLD_M6]` / `[DESIGN_PARTNERS_M6]` / `[ARR_M6]` / `[TEAM_M6]`** and the M12 / M18 equivalents — 18-month milestone grid numbers. *File:* `content/12_ask_and_use_of_funds.md`. *Hint: the deck (`index.html` ask slide) already shows suggested target shapes; pick the numbers you can defend.*
9. **`[ORG]` / `[REPO]`** — GitHub org and repo for code/docs links. *Files:* `landing_page_copy.md` (footer + CTA), `index.html` (none — none currently link out to a GitHub URL).
10. **`[FOUNDER_BACKGROUND]`** — Founder bio expansion. *File:* `content/11_team_and_execution.md`.

## CSS choice

CSS is **inlined** in `index.html`. The `assets/` directory is preserved (empty) for future static assets (images, fonts, downloadable PDF version of the deck, etc.). If you decide to externalize CSS later, move the `<style>` block into `assets/styles.css` and replace it with `<link rel="stylesheet" href="assets/styles.css">`.

## Validation

Before publishing, sanity-check:

```bash
# HTML parses without errors
python3 -c "from html.parser import HTMLParser; HTMLParser().feed(open('index.html').read())"

# Ensure no stray placeholders linger in shipped slides (the list above accounts for the intentional ones)
grep -nE '\[[A-Z_]+\]' index.html landing_page_copy.md content/*.md
```

The grep above will show exactly the placeholders enumerated in the "Placeholders" section. If anything else surfaces, treat it as an unfilled slot.
