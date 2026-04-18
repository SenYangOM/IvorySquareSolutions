# 11 — Team and Execution

**The one real claim we make about ourselves: execution cadence is measurable. The five-paper post-MVP loop happened in five days at a documented 50% wall-clock reduction. Investors can run the playbook themselves on a new paper and see it work.**

---

## Founding team

<!-- FOUNDER: Fill in name + 2-3 sentence bio. The deep_research_report.md and the build references suggest a Stern Accounting PhD track (founder is the accounting domain expert) and a primary engineering contributor (the build's SEC User-Agent string declares "Sen Yang sy2576@stern.nyu.edu" per `mvp_build_goal.md` §13 decision 2 — confirm before publishing). Adjust as appropriate. -->

- **`[FOUNDER_NAME]`** — Founder & CEO. *(Suggested framing: domain wedge + product story. Stern Accounting PhD or equivalent; deep familiarity with US GAAP / SEC reporting; primary author of the rule set and judgment templates.)*
- **`[ENGINEERING_LEAD]`** — Engineering Lead / Founding Engineer. *(Suggested framing: built the MVP end-to-end in 7 phases; declared SEC User-Agent on every EDGAR request.)*
- **`[FOUNDING_TEAM]`** — *(One-line names + roles for any additional founding-team members; otherwise delete this bullet.)*

## Advisors

- **`[ADVISORS]`** — *(One bullet per advisor: name, current/past affiliation, what they advise on. Likely candidates given the project's substantive grounding: an accounting-academia advisor (Stern, Booth, etc.), a quant-research-head advisor, an MCP / agent-infra-leaning technical advisor.)*

---

## What we can claim concretely

The MVP shipped end-to-end in 7 documented phases. Every phase has a demoable artifact. Every gate in `success_criteria.md` is green. The build artifact is reproducible from a clean clone in **164 seconds against a 1,800-second bar** (Gate 5 — clean-clone walkthrough).

After MVP completion, the team ran a 5-paper × 5-skill onboarding sprint to test whether the playbook the build produced was actually repeatable. Wall-clock per paper:

| # | Paper | Skill shipped | Wall-clock (min) |
|---|---|---|---:|
| 1 | Kim, Muhn, Nikolaev & Zhang (2024) | `compute_mdna_upfrontedness` | 210 |
| 2 | Kim & Nikolaev (2024) | `compute_context_importance_signals` | 165 |
| 3 | Bernard, Cade, Connors & de Kok (2025) | `compute_business_complexity_signals` | 140 |
| 4 | de Kok (2024) | `compute_nonanswer_hedging_density` | 125 |
| 5 | Bernard, Blankespoor, de Kok & Toynbee (2025) | `predict_filing_complexity_from_determinants` | 105 |

**The 50% wall-clock reduction is the data point.** It is not a forecast; it is the actual five-iteration arc, against a heterogeneous corpus that exercised five distinct paper-to-skill onboarding patterns. The compounding came from concrete, named workshop scripts (`extract_paper.py`, `inspect_canonical.py`, `draft_manifest.py`, `replication_harness.py`) the team wrote *as* it onboarded, not before. Each script earned its keep by removing manual steps the previous paper made painful.

---

## How we make decisions

The three operating principles (P1, P2, P3) doubled as the team's internal decision rules during the MVP build. Every design choice was checked against all three:

- **P1 — Disjoint expert and engineering layers.** "Would a real PhD have to write Python to ship this change?" If yes, redesign.
- **P2 — Don't over-engineer, don't be lazy.** "Is this abstraction earned by two callers?" If no, inline. "Is this stub or TODO going to ship?" If yes, finish it now (`不要怕麻烦`).
- **P3 — The user is an AI agent.** "Would a cold agent given only this catalog find this surface natural to use?" If no, redesign.

All three checks are encoded as automated gates in `success_criteria.md` §11 and §12. The MVP did not ship until all three gate-grouped checks passed. The discipline is in the codebase, not in the slide.

---

## Why these principles will travel

Two reasons the same operating principles will hold as the team grows from a founding pair to ~10 people through a seed round:

1. **They are written down, gated, and testable.** "Don't be lazy" reduces to a `grep` for TODOs and `pass` stubs. "Disjoint expert layer" reduces to a contract check on which directories experts edit. "Agent-native" reduces to the natural-agent test, which can be re-run against any new skill in minutes. Onboarding a new engineer is *handing them the gates*, not training them on a culture.
2. **They were the actual discipline of the build, not a post-hoc rationalization.** The MVP was built under them; we know what they cost in real engineering time and what they save in rework. They will not be quietly dropped under deadline pressure because we already know the trade-off and we already chose.

---

## What investors will get from a working session with the founder

A 30-minute session reproduces the demo from a clean clone, runs the natural-agent test live, and walks through one paper-to-skill onboarding cycle end-to-end. The artifact is real; the cadence is observable; the rule set is reviewable line-by-line.

If you want to stress-test the team on quality, pick any paper in the candidate-skills lists in `workshop/paper_to_skill/notes/<paper>.md` and ask how long it would take to onboard. The honest answer (within the 105-minute steady-state range, plus or minus a confidence interval the founder can defend) is the cadence.
