# 05 — Moat and Defensibility

**Four pillars. Each is testable today; together they describe a wedge that terminals will not rebuild and foundation-lab plugins will not replicate.**

The wedge is *expert judgment + citation provenance + agent-native surface*. It is small. It is the right size for a startup.

---

## Pillar 1 — Expert judgment encoded in reviewable YAML

**The contract.** P1 from the operating principles: human verification and experience layers are disjoint from engineering layers. A real domain expert (Stern accounting PhD, audit specialist, finance methodologist) contributes through declarative artifacts — `mvp/human_layer/personas/<persona>.yaml`, `mvp/rules/templates/*.yaml`, `mvp/eval/gold/<skill>/*.yaml`, audit-log review comments — and never needs to write, read, or run Python.

**Why this matters.** The single most common failure mode of expert-in-the-loop products is forcing experts to ship through the engineering pipeline. Their iteration velocity collapses to engineering velocity; the rule set stops compounding at the rate the domain evolves; the product becomes "an LLM wrapper with marketing." The MVP avoids this structurally:

- The four subagent personas (`accounting_expert`, `quant_finance_methodologist`, `evaluation_agent`, `citation_auditor`) each have their full prompt + model assignment in YAML at `mvp/human_layer/personas/`. The Python in `mvp/agents/` is a thin runtime that loads the YAML — no domain text lives in code.
- Rule templates like `mvp/rules/templates/m_score_components.yaml` (8 components × 4 severity bands × interpretation text + follow-up questions + citation requirements) are written in language an accounting PhD recognizes as their kind of artifact, not as machine-generated boilerplate.
- Gold-standard cases under `mvp/eval/gold/` are YAML files an expert can review and amend without reading any code.

**Why a generic foundation-lab plugin cannot replicate this.** A frontier lab can ship a "GPT-Accountant" plugin with 50 tools auto-extracted from public material. What it cannot ship is a **versioned ontology and judgment-template set authored under a named accounting practitioner's contract**, governed like code, signed off by name, and updated as standards evolve. The expert is the moat; the YAML surface is what makes the expert scalable.

---

## Pillar 2 — Citation/provenance on every claim

**The contract.** Every numeric output carries `(doc_id, statement_role, locator, excerpt_hash)`. The MVP's eval gate is **100% citation resolution across all production runs of the 5 cases** — 213 live citations resolving today, zero broken hashes, zero fabricated locators. A single broken citation blocks release.

**The user-facing surface.** `extract_canonical_statements` and the L3 paper-derived skills emit citations as part of their structured output. A `resolve_citation` skill (or registry endpoint) takes a `(doc_id, locator)` tuple and returns the cited passage text plus surrounding context — agents do not have to scrape the doc store directly.

**Why this is hard to retrofit.** XBRL data quality is a documented risk: tag extensions, mis-classified concepts, footnote-clustered errors. The provenance-first design is the mitigation, but it has to be designed in from L1; bolting it onto an existing pipeline requires re-architecting the immutable doc/fact store. Our L1 is hash-addressed from day one. Every fact is reachable from every claim that uses it. The audit trail composes through L2, L3, and L4 without loss.

**Why this is the audit and compliance contract.** An auditor or regulator does not ask "what does the model think?" — they ask "show me the source." The product answers that question by construction. A CFO defending a number to a regulator can run the same skill the agent ran, get the same answer, and trace each component to a specific line item in a specific filing. That contract is what unlocks regulated-buyer revenue.

---

## Pillar 3 — Paper-faithful L3 skills

**The discipline.** When implementing a paper-derived skill, the source paper's exact coefficients and exact thresholds win. Two examples:

- `compute_beneish_m_score` uses the **1999 paper's threshold of -1.78**, not the popular -2.22 from Beneish et al. 2013. The decision is documented in the rule template's notes block. A regression test (`test_beneish_threshold_is_1978.py`) guards the value.
- `compute_altman_z_score` uses the **paper-exact X5 coefficient of 0.999**, not the rounded 1.0 commonly seen in textbooks. Another regression test (`test_altman_x5_is_0999.py`) guards the value.

Both decisions are visible in the manifest. Both are testable. Both are different from what a junior analyst working from popular references would produce.

**Why this is the differentiator from "vibe-coded" accounting.** The bar for "professional-grade" interpretation is precisely this kind of small, defensible call — the difference between an analyst who has read the paper and one who has read a blog post about the paper. An LLM left to its own devices will return -2.22 because the internet says -2.22. We return -1.78 because the paper says -1.78, and we can show you where on page 16. Compounded across hundreds of paper-derived skills, this is a quality moat that is invisible from the outside until a buyer's auditor pulls a thread.

**The replication discipline scales.** The 5 papers onboarded post-MVP each shipped with a per-skill replication harness comparing the implementation against the paper's worked examples. The post-MVP playbook (`workshop/docs/paper_onboarding_playbook.md`) documents 5 branches of paper-to-skill onboarding patterns, each with explicit "did you hold to the paper's actual numbers?" checks.

---

## Pillar 4 — Agent-native by design

**The contract.** P3 from the operating principles. Every skill manifest is the single source of truth for the MCP tool spec, the OpenAI tool-use spec, the CLI help text, and the OpenAPI doc. The agent reads `description_for_llm` to choose the skill; the agent populates inputs against the JSON schema; the agent receives a typed response or a typed error.

**The agent-accessibility gates the MVP passes:**

- `GET /mcp/tools` returns a 12-skill MCP catalog consumable by Claude Desktop or any MCP-compatible agent without modification.
- `GET /openai/tools` returns the same 12 skills as a valid OpenAI `tools=[…]` array.
- Every error response matches `{error_code, error_category, human_message, retry_safe, suggested_remediation}`. No HTTP 500 with a stack trace ever leaks to the agent.
- CLI ↔ API parity is verified by an integration test: for each of the 12 skills, a CLI invocation and the equivalent API POST produce byte-identical output bodies (modulo timestamps).
- Citations are resolvable via the registry, not by parsing.

**The natural-agent test.** A real Claude instance was given only the MCP tool catalog (no system prompt naming the skills, no hand-holding) and the prompt: "analyze whether Enron's 2000 10-K shows accounting red flags, with citations." The agent converged on `analyze_for_red_flags` with the correct inputs (`{cik: "0001024401", fiscal_year_end: "2000-12-31"}`) on its own. All four sub-criteria — skill selection, input schema correctness, output usefulness, error recoverability — passed. This is the definitive agent-accessibility test, and we built the MVP to pass it before we built anything else.

**Why this is structural, not stylistic.** Most "API-first" finance products are an HTTP wrapper around a human-first UI; their endpoints expose pipeline units the UI happens to need. Ours start from the agent surface and work backward. The composite skill `analyze_for_red_flags` exists because that is what an agent calls; the lower skills exist because the composite needs them. The CLI is generated from the registry; the API is generated from the registry; the MCP and OpenAI catalogs are generated from the same manifests. There is one source of truth and three rendering targets.

---

## Why these four hold together

Each pillar individually is replicable by a sufficiently disciplined team with sufficient capital and time. **The four together compound:** expert-authored rules feed gold cases that calibrate confidence on cited outputs that agents call deterministically. A competitor would have to copy all four contracts simultaneously, with the same expert practitioner contracts and the same citation discipline. The small overlap area where all four hold is where we live. We do not need to be the only product in any single dimension; we need to be the only one at the intersection.

Combined with the working evaluation harness, the gold-standard corpus that grows with every iteration, and the observable wall-clock compounding of the paper-onboarding loop (210 → 105 minutes across 5 papers), the moat is one that gets harder to attack the longer we operate. That is the test of a real moat: time strengthens it.
