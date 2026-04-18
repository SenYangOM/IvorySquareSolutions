# 01 — Problem

**Public-company disclosures are machine-readable by *format* (XBRL) but not by *interpretation*. Every AI agent that wants to reason about an issuer's filings has to redo the interpretive work from scratch — and cannot cite its sources deterministically.**

## The gap

A modern personal AI agent — Claude, ChatGPT, an internal copilot — that asks "does Enron's 2000 10-K show accounting red flags, with citations?" today has three poor options:

1. **Call a financial-data terminal.** Bloomberg, S&P Capital IQ, FactSet, LSEG Workspace expose deep datasets, but they are human-first products with APIs bolted on. They give you fields, not interpretations. They tell you DSO went from 30 to 51 days; they do not tell you that the change exceeds the Beneish DSRI threshold and which line items in which footnote drove it.
2. **Call an AI search product.** AlphaSense, BamSEC, and the search layers of the terminals find passages that match a query. They are great at retrieval. They do not produce structured judgment: "manipulator_likely with these eight component values and these eight cited line items" is not a query they answer.
3. **Call a foundation model directly.** GPT, Claude, Gemini will produce a confident-sounding analysis with numbers in it. The numbers will sometimes be wrong, the citations will sometimes be hallucinated, and there is no audit trail. For a CFO, an auditor, or a regulator this is unusable.

The status quo forces every team to reinvent the same interpretation pipeline — typically as a brittle one-off built on a junior analyst's Excel model. Quality is uneven. Provenance is informal. Repeatability across analysts is nil.

## Why this is sharper now than two years ago

The substrate beneath agents is settling fast. Anthropic's MCP and OpenAI's tool-use specs converged on the same shape: agents call typed functions over JSON schemas. The implication is straightforward — the next generation of finance and accounting work will be done by **personal AI agents acting on behalf of humans**, and those agents need data substrates that are typed, cited, deterministic, and composable.

OpenAI's late-2026 GPT-Rosalind launch made this concrete in life sciences: a domain-specific reasoning model paired with a Codex plugin exposing 50+ databases as modular skills, explicitly described as an "orchestration layer." The same shape is coming to accounting and finance. The architectural question is no longer *whether* — it is *who builds the rule-set, the gold corpus, and the citation backbone first*.

## What this implies

- The product surface is **not** a UI; it is a **skill catalog**. Agents are the primary user.
- Every output must carry **provenance to the source disclosure**, not "as of the model's training cutoff."
- The interpretation layer must be **versioned, expert-authored, and testable** — not a prompt-stack inside a vendor's chat product.
- Reproducing an analysis a year later, against the same filing, must yield the same answer (modulo logged restatements). This is a basic audit contract; very few existing tools provide it.

The opportunity is to build the missing layer: a machine-readable accounting interpretation service whose outputs are agent-native, citation-grounded, and authored under a real expert-judgment contract. That is what we are building.
