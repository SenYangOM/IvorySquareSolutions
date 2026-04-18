# 07 — Competitive Landscape

**The market is crowded in data + search and very thin in professional, standardized interpretation with auditable provenance and an agent-native surface. The wedge is small and deliberately so.**

---

## Comparison table

| Competitor / category | What they're strong at | Their moat | Our wedge against them |
|---|---|---|---|
| **Bloomberg / LSEG Workspace** | Comprehensive licensed data + analyst workflows; deep transcript coverage; Microsoft AI partnership (LSEG) | Data licenses, enterprise distribution, terminal lock-in | Their core product is human-first; AI/agent integrations are bolted on a per-feature basis. We are agent-native from the manifest down. They will not rebuild around an MCP catalog. |
| **S&P Global Market Intelligence (Capital IQ)** | 109,000+ public-company coverage; document intelligence; AI document tools | Proprietary datasets (CIQ, ratings, indices); enterprise sales motion | Outputs are workflow/search-centric, not standardized accounting-judgment primitives. Buyer has to do the interpretation work themselves. |
| **FactSet** | Fundamental datafeeds, transcripts since 2003, institutional client entrenchment | Data breadth, datafeed reliability | Less interpretive; outputs are values and event metadata, not cited judgments. |
| **AlphaSense** | AI search across 500M+ premium documents; 240,000+ expert-call transcripts; strong UX | Content aggregation + search UX | Excellent at finding passages; does not produce structured interpretation. A `revenue_quality_assessment` JSON with citations is not their product surface. |
| **BamSEC** | Fast filings/transcripts productivity for individuals + small teams; transparent pricing ($69/month Pro) | UX simplicity, low price point | Productivity tool, not an interpretation engine. Same story as AlphaSense — finding ≠ structuring. |
| **Daloopa / Canalyst / Visible Alpha** | Analyst-grade reformatted models for thousands of issuers; consensus data | Hand-built models with manual QA; analyst-network distribution | Their unit of work is the analyst's spreadsheet. Ours is the agent's structured JSON call. Different buyers, complementary outputs — but they are not building toward an agent surface. |
| **CalcBench / XBRL.US viewers** | Direct XBRL queryability across SEC filings; comparability tools | Free-tier coverage, machine-readability of raw facts | Stops at raw facts. Does not interpret, does not cite at the passage level, does not version judgment. |
| **Foundation models direct (GPT, Claude, Gemini chat)** | Universal availability; zero integration cost | Frontier reasoning quality | Hallucinate numbers; cannot cite deterministically; no domain rule set; no audit trail. Useful as a top-of-stack reasoner *over* our skills, not as a substitute. |
| **OpenAI GPT-Rosalind (Life Sciences)** | Domain-specific frontier reasoning model + Codex orchestration plugin + 50+ external tools and databases. The closest public architectural analog. | OpenAI compute, foundation-model expertise, frontier-lab brand, enterprise relationships (Amgen, Moderna, Allen Institute) | Different domain (life sciences). Our wedge inside accounting is *PhD-authored versioned rule templates + citation-grounded outputs* — depth of expert judgment, not the orchestration shape. The shape is now industry-validated; the depth is the differentiator. |

---

## Strategic framing

The category we are building — **machine-readable, audit-grade accounting interpretation as agent-callable skills** — does not yet have a dominant incumbent. The adjacent categories do:

- **Terminals** (Bloomberg, S&P CIQ, LSEG, FactSet) own the analyst seat. They will not rebuild themselves around an MCP catalog because their economics depend on the seat — switching to per-call agent monetization would cannibalize their core. They will likely buy or partner rather than build a true agent-native interpretation layer.
- **AI search** (AlphaSense, BamSEC) owns the "find me a passage" workflow. They will likely add structured-extraction features but are unlikely to ship versioned, expert-authored, cited interpretation primitives — the content moats they have are passage-corpus-licensed, not judgment-licensed.
- **Foundation labs** (OpenAI, Anthropic, Google) ship the reasoning. Their accounting-vertical play, when it comes, will look like GPT-Rosalind-for-accounting: a domain model + a plugin with 50+ generic tools. **They will not embed a Stern-PhD-authored rule template set under a versioned ontology with restatement-aware provenance**, because that requires a domain-practitioner contract their structure does not support. This is exactly the wedge GPT-Rosalind validates by *not* trying to fill it.

The overlap area where all three classes of competitor *cannot* live — versioned expert judgment + per-claim citation provenance + agent-native typed surface — is small. It is the right size for a focused startup to occupy and defend.

---

## Why GPT-Rosalind is the most useful reference, not the most threatening competitor

OpenAI's GPT-Rosalind launch in late 2026 is the strongest public validation of the architectural shape we have built toward: **a domain-specific frontier reasoning model paired with an orchestration plugin exposing modular skills over external tools and databases**. Their plugin connects to 50+ public multi-omics databases, literature sources, and biology tools. They explicitly describe it as an "orchestration layer."

This matters for three reasons:

1. **Architectural validation.** The "domain model + modular skills + orchestration" pattern is no longer a research curiosity; it is a deployable production pattern at frontier-lab scale. Buyers (and investors) recognize the shape.
2. **Where the wedge moves.** The orchestration layer becomes commodity. The remaining differentiator is the depth of domain judgment encoded in the skills, the integrity of citation-grounded outputs, and the practitioner contracts that govern both.
3. **Cross-domain proof of focus discipline.** GPT-Rosalind shipped life sciences only — not "all of science." A specialized product earns the right to broaden by first doing one thing visibly well. That is the same discipline our MVP scope-decision (US public companies only) imposes.

A future "GPT-Accountant" or equivalent from any frontier lab is a credible 18-to-36-month threat. The two pre-emptive defenses we have already built into the MVP are:

- **Expert-authored judgment templates with versioned ontology**, governed by a domain practitioner. Auto-extracting these from public material (the foundation-lab approach) loses the practitioner's tacit knowledge — what to focus on, what cross-cuts, what edge-cases matter.
- **Citation-grounded provenance with restatement-aware versioning** — an audit-and-compliance contract a generic plugin cannot ship without rebuilding an immutable doc/fact store, the L1 layer of our architecture.

The wedge is not "we built an orchestration layer" — that is now commodity. The wedge is **"every output is defensible to a CFO, an auditor, and a regulator, today."**
