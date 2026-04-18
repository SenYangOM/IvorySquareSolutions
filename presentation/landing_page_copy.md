# Landing Page Copy

Ready-to-paste source for the public landing page. Voice is second-person, hedged, no fabricated metrics. Total word count ≈ 720.

---

## Hero

**Audit-grade accounting interpretation, callable as a skill.**

Your AI agent can now read 10-Ks the way an experienced analyst does — with cited line items, paper-faithful screens, and structured judgment outputs. Not search. Not summarization. Skills.

[**Request a design-partner slot →**](mailto:[FOUNDER_EMAIL])  ·  [**Get the MCP catalog →**](https://github.com/[ORG]/[REPO])

<!-- FOUNDER: replace [FOUNDER_EMAIL] and [ORG]/[REPO] before publishing. -->

---

## Subhead

Public-company filings are machine-readable in format (XBRL) but not in interpretation. Every agent that wants to reason about an issuer redoes the work from scratch — and cannot cite its sources deterministically. We close the gap with a versioned skill catalog that any AI agent can call.

---

## Three things you get

### 1. Skills, not search.
Twelve callable skills today, scaling to fifty within six months. Each returns typed JSON: scores, components, flags, interpretations, and per-line-item citations. Composable. Cacheable. Deterministic.

### 2. Provenance on every claim.
Every numeric output carries a stable `(doc_id, statement_role, line_item, value, sha256)` tuple. A `resolve_citation` skill returns the cited passage text on demand. Your agent never has to scrape — and your auditor can trace any number back to its source filing in one call.

### 3. Agent-native by construction.
One manifest renders to MCP tool specs and OpenAI tool-use specs simultaneously. CLI and API share one registry with byte-identical outputs. Every error is a typed object — no raw exceptions cross the skill boundary. The natural-agent test (cold Claude solves the Enron 2000 question from the catalog alone) is our acceptance gate, and it passes.

---

## How it works in three steps

1. **Connect.** Drop our MCP catalog into Claude Desktop, Codex, or any MCP-compatible agent. Or load our OpenAI tool-use spec into a chat-completions call. Same skills, two surfaces, one manifest each.
2. **Call.** Your agent picks a skill from the catalog using its `description_for_llm` text and populates the JSON-schema-typed inputs. Composite skills orchestrate the lower skills automatically.
3. **Cite.** Every output includes citations to the source filings, resolvable via a `resolve_citation` skill. Show the user the passage, not just the number.

---

## The current skill catalog

Twelve skills as of April 2026, regenerable from the registry:

| Skill | Layer | What it does |
|---|---|---|
| `extract_canonical_statements` | fundamental | IS / BS / CF for a 10-K with line-item citations |
| `extract_mdna` | fundamental | Verbatim MD&A text, headings + paragraphs |
| `interpret_m_score_components` | interpretation | Per-component natural-language explanation of an M-score |
| `interpret_z_score_components` | interpretation | Per-component natural-language explanation of a Z-score |
| `compute_beneish_m_score` | paper-derived | Beneish (1999) earnings-manipulation discriminant |
| `compute_altman_z_score` | paper-derived | Altman (1968) bankruptcy-prediction discriminant |
| `compute_mdna_upfrontedness` | paper-derived | Kim et al. (2024) information-positioning score |
| `compute_context_importance_signals` | paper-derived | Kim & Nikolaev (2024) context-importance signals |
| `compute_business_complexity_signals` | paper-derived | Bernard et al. (2025) monitoring-demand signals |
| `compute_nonanswer_hedging_density` | paper-derived | de Kok (2024) hedging-language density on MD&A |
| `predict_filing_complexity_from_determinants` | paper-derived | Bernard et al. (2025) regression-based complexity prediction |
| `analyze_for_red_flags` | composite | M-score + Z-score in one call, with citations |

---

## FAQ

**Who is this for?**
Builders of personal AI agents, custom GPTs, quant funds writing internal copilots, and fundamentals shops with engineering teams. The user surface is a tool catalog, not a UI.

**Is this a Bloomberg replacement?**
No. Bloomberg sells the seat; we sell the structured judgment that flows under the seat. Many of our buyers will keep their terminals and call our skills from agents that wrap them.

**Do you license analyst-research content?**
No. Public-data substrate only — SEC EDGAR plus published academic-paper implementations. The interpretation layer (rule templates, judgment templates, gold cases) is original.

**What's your relationship to GPT-Rosalind?**
GPT-Rosalind is the closest public architectural analog: a domain-specific reasoning model paired with an orchestration plugin exposing modular skills. They built it for life sciences. We build it for accounting and financial reporting. Same shape, different domain, different judgment.

**Why "audit-grade"?**
Every claim resolves to a real passage. Hashes match. Determinism is a contract. A CFO defending a number to a regulator can run the same skill the agent ran, get the same answer, and trace each component to a specific line item in a specific filing. That contract is what unlocks the regulated buyers.

**Are you raising?**
Yes. Seed under discussion. Design-partner pilots open now.

---

## CTA

[**Request a design-partner slot →**](mailto:[FOUNDER_EMAIL])

We're talking to a small number of agent vendors, quant funds, and fundamentals shops who want to integrate the catalog and shape what we build next. If that's you, get in touch.

---

## Footer

[Docs](https://[ORG]-docs/) · [GitHub](https://github.com/[ORG]/[REPO]) · [MCP catalog](https://[ORG]/mcp/tools) · [OpenAI tool spec](https://[ORG]/openai/tools)

© 2026 `[COMPANY_NAME]`. Public-company data sourced from SEC EDGAR under the SEC's fair-access policy (≤10 req/s, declared User-Agent). Not investment advice.
