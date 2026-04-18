# 12 — The Ask and Use of Funds

**We are raising to compound the working playbook, not to replace the founder's work. The MVP is shipped; the playbook is documented; the next 18 months convert one playbook into a defensible coverage universe and a small handful of design-partner contracts.**

---

## Round terms

<!-- FOUNDER: Fill in the financial terms before sending. Suggested format below. -->

- **Round size:** `[ROUND_SIZE]` *(e.g., $X seed)*
- **Pre-money valuation:** `[VALUATION]` *(or "valuation under discussion")*
- **Lead:** `[LEAD]` *(or "lead under discussion")*
- **Use of funds horizon:** 18 months
- **Optional safety net:** `[BRIDGE_TERMS]` *(e.g., bridge / SAFE / convertible note structure)*

---

## Use of funds — the four hires

The seed-round dollars convert into people, not infrastructure. The capital gets deployed against four roles:

1. **One Stern (or peer) accounting PhD, full-time.**
   - Owns the rule-template authoring backlog.
   - Reviews every new L3 paper-derived skill against the source paper before it ships.
   - Maintains the gold-standard corpus and the audit-review process.
   - Replaces the `accounting_expert` subagent persona by editing the same YAML files. The contract is already designed for the handoff.

2. **One agent-infra engineer, full-time.**
   - Owns MCP and OpenAI tool-spec compatibility as both standards evolve.
   - Owns the L5 production surface: auth, multi-tenancy, billing, rate limiting, SLA.
   - Owns CLI ↔ API parity testing as the catalog grows.

3. **One backend / data engineer, full-time.**
   - Owns coverage expansion from 5 → 50 → 500 issuers.
   - Owns the L0/L1/L2 infrastructure scaling work (companyfacts caching, restatement-aware re-run, transcript ingestion when that lands).
   - Owns the post-MVP migration from filesystem + JSONL to a real document/fact store.

4. **One solutions engineer / design-partner lead, half-time at first then full-time.**
   - Runs the design-partner pilot motion. Initial focus on Segment C (agent vendors) and Segment A (quant funds) per §06.
   - Translates pilot feedback into rule-template and skill-roadmap priority.

The founder remains the product lead and the GTM voice; the four hires take on the components the playbook is already built around. Hiring against named contracts (rather than against a general "ML team") is the same disjoint-layer discipline that built the MVP.

---

## 18-month milestone grid

<!-- FOUNDER: Fill in the specific numeric targets after the round closes — they should be defensible against the design-partner pilots that close in the first 60 days. The shape below is the template; numbers are placeholders. -->

| Milestone | Month 6 | Month 12 | Month 18 |
|---|---|---|---|
| Coverage universe | `[COVERAGE_M6]` issuers (suggested: 50 large-cap US) | `[COVERAGE_M12]` issuers (suggested: S&P 500) | `[COVERAGE_M18]` issuers (suggested: 1,000+ US large/mid-cap) |
| Skill catalog | `[SKILLS_M6]` skills (suggested: 25, paper-derived dominant) | `[SKILLS_M12]` skills (suggested: 50, with first multi-jurisdiction skill) | `[SKILLS_M18]` skills (suggested: 75+, with first transcript-consuming skill) |
| Gold-standard cases | `[GOLD_M6]` (suggested: 100 — unlocks confidence calibration) | `[GOLD_M12]` (suggested: 500) | `[GOLD_M18]` (suggested: 1,500) |
| Design-partner contracts | `[DESIGN_PARTNERS_M6]` paid pilots (suggested: 3) | `[DESIGN_PARTNERS_M12]` (suggested: 8 with 3 in production) | `[DESIGN_PARTNERS_M18]` (suggested: 15 with first enterprise deal) |
| Annual recurring revenue | `[ARR_M6]` *(probably $0 — pilot-only)* | `[ARR_M12]` *(suggested: $0.5M – $1.5M)* | `[ARR_M18]` *(suggested: $2M – $5M)* |
| Team headcount | `[TEAM_M6]` (suggested: 5 incl. founder) | `[TEAM_M12]` (suggested: 7) | `[TEAM_M18]` (suggested: 9-10, prepping Series A) |
| Technical milestones | First multi-jurisdiction (IFRS) skill in flight; restatement-aware re-run shipped; SOC 2 Type 1 readiness assessment | First transcript-consuming skill shipped; SOC 2 Type 1 in audit; calibrated confidence model | SOC 2 Type 2 audit complete; first enterprise contract signed; Series A targeting Year 2-3 |

The ARR ranges are illustrative and consistent with the conservative-to-base scenarios in `deep_research_report.md` §"3-year revenue scenarios." They will be re-parameterized after the first 5 paid pilots.

---

## Why this is "compound the founder's work," not "replace it"

The MVP exists. The playbook exists. The cadence is observable. The four hires take the existing playbook and run it in parallel against a coverage universe and a design-partner motion the founder cannot run alone. Three discipline anchors:

- **The PhD hire owns rule templates** and gold cases — the founder's domain output, scaled.
- **The agent-infra engineer owns the catalog surface** — the founder's API-design output, scaled.
- **The backend engineer owns coverage scale** — the founder's ingestion + standardization output, scaled.
- **The solutions engineer owns the design-partner motion** — the founder's GTM output, scaled.

In every case the founder remains the source of the contract; the hire executes against it. The same P1 / P2 / P3 gates that bound the MVP build bind every shipped piece going forward — the gates are the management system, not the founder's individual time.

---

## What we're explicitly NOT raising for

- **Not raising to build a UI / consumer chat product.** Per §10 roadmap. The user is an agent.
- **Not raising to enter a second domain (corporate finance, quant finance, etc.).** Year 2-3 roadmap; the seed proves accounting first.
- **Not raising to acquire content licenses (broker research, paid transcript feeds).** Stays public-data substrate at seed; transcripts are a Year 1.5 question.
- **Not raising to spin up a sales team.** Founder-led GTM through seed; sales hire is post-Series A.
- **Not raising to build a research-publication brand.** We are infrastructure, not a research vendor. Stays out of scope.

The asks and the *not*-asks together describe a tightly scoped seed round: enough to compound the playbook into a defensible Year 1 product surface; not so much that we drift into adjacent categories before the wedge is established.
