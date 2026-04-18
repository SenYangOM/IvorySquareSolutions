# 06 — Market and Segments

**Illustrative TAM/SAM/SOM with stated assumptions, plus four buyer segments and a hypothesis about each. Numbers below are anchored to the deep-research-report figures and labeled as illustrative — they are working ranges to be re-parameterized after design-partner pilots, not commitments.**

---

## Reference anchors (from public filings)

These are the adjacent revenue pools we sit between:

| Provider | Most-recent reported revenue | Source |
|---|---:|---|
| S&P Global Market Intelligence segment | $4.916B (2025) | S&P Global FY2025 |
| LSEG Data & Analytics segment | £4,338M (2025) | LSEG FY2025 |
| FactSet (full company) | $2.322B FY2025 GAAP | FactSet FY2025 |
| BamSEC pro plan | $69 / month billed annually | bamsec.com pricing page |

These three big providers alone represent **>$7B + £4.3B of annual spend in adjacent data/analytics/workflow segments**, before counting Bloomberg, Refinitiv, AlphaSense, the smaller modeling vendors, and the proliferating internal-build budgets at large funds. Our category — *audit-grade interpretation as agent-callable skills* — is a sliver of this, but the sliver is real and it is currently un-served at the audit-grade bar.

---

## TAM / SAM / SOM (illustrative; assumptions explicit)

> **All figures below are illustrative.** They are working ranges with stated assumptions, derived from the deep-research-report sizing model. They are intended to frame the order of magnitude, not to commit to a number. Each will be re-parameterized after the first 5-10 paid design-partner pilots.

### TAM — Total Addressable Market

**Definition.** Global spend for tools supporting public-company financial-disclosure research workflows (filings + transcripts + interpretation), including seats and API usage.

- **Working range:** $20B – $50B annually.
- **Assumptions:** based on the proxy that single segments of major incumbents already generate multi-billion-USD revenue, scaled to a global footprint and adjusted for the broader interpretation-adjacent budget pool.
- **Caveat:** this includes broader datasets than our initial narrow offering. The headline number is meant to anchor "this is a large enough pool to support a generational company," not "we will capture this."

### SAM — Serviceable Addressable Market

**Definition.** Spend specifically addressable by our product characteristics — public-company filings + earnings + transcripts interpretation, with strict traceability and standardized schema, accessible to AI agents.

- **Working range:** $2B – $10B annually.
- **Assumptions:** SAM is 10%–20% of TAM. Many terminal/workflow budgets are spent on asset-class data, trading, indices, or non-disclosure datasets that are out of our scope; we strip those out.
- **Caveat:** the agent-native sliver of SAM is small today and growing fast. Estimating its 2028 size is a forecast, not an observation.

### SOM — Serviceable Obtainable Market

**Definition.** Revenue a focused new entrant could realistically capture in 3–5 years.

- **Working range:** $5M – $25M ARR by year 3.
- **Assumptions:** narrow coverage wedge (large-cap US first), high retention from workflow integration, enterprise pilots converting at a believable rate. Consistent with a focused premium-infrastructure startup, not a terminal replacement.
- **Caveat:** the wide range reflects uncertainty about which buyer segment monetizes first. The bull case is API-first traction with quant funds and agent-vendors; the bear case is slower enterprise conversion with fundamentals shops.

---

## Segment breakdown

We see four buyer segments, each with a distinct hypothesis about willingness-to-pay and current alternatives. The MVP's vertical slice (Beneish + Altman on five filings) is small enough to be useful to all four; the post-MVP coverage expansion picks the segment that monetizes first.

### Segment A — Quant funds and systematic strategies (Stage 2 API consumers)

- **Hypothesis on demand.** Quant funds increasingly want text- and disclosure-derived signals as inputs to factor models. Building these in-house is expensive, brittle, and duplicative across funds. A versioned, citable, machine-callable skills API removes the build-it-yourself overhead.
- **Current alternatives.** In-house NLP teams (expensive, attrition-prone), academic-paper replications by junior quants (uneven quality), commercial text-analytics vendors (RavenPack, MarketPsych — narrower scope, less interpretive depth).
- **Pricing hypothesis.** Usage-based API with annual commits; $150K – $1M+/year for full-coverage enterprise tier.
- **Why we win.** Paper-derived skills with explicit replication harnesses are exactly what a quant-research head wants. The provenance contract is a bonus, not the headline.

### Segment B — Fundamentals shops (long-only, hedge funds, PE / credit) — Stage 1 precomputed outputs

- **Hypothesis on demand.** Earnings-season overload is universal. A precomputed structured-judgment view of every filing in the analyst's coverage universe — with citations — compresses initial-read time from hours to minutes per filing.
- **Current alternatives.** Junior analysts (slow, inconsistent), template-based analyst notes (every shop has its own, none scale), AlphaSense / BamSEC search (good for retrieval, not for structured judgment).
- **Pricing hypothesis.** Seat-based tiered subscriptions: $399 – $999/month per seat for Pro; $25K – $150K/year for Team (5–50 seats with SSO and shared workspaces).
- **Why we win.** Citation-grounded structured outputs — every claim resolves to a passage — are differentiated against everything in this segment. Audit-grade is also an internal-compliance asset for the buyer.

### Segment C — Personal AI agents and custom GPT vendors

- **Hypothesis on demand.** Every consumer-facing AI agent that wants to discuss public companies needs an upstream data layer that is typed, cited, and deterministic. Agent vendors do not want to build their own EDGAR ingestion + interpretation pipeline; they want a callable catalog.
- **Current alternatives.** Foundation-model search-with-tools (hallucination risk), generic finance APIs (Polygon, Alpha Vantage — data, not interpretation), in-house pipelines per vendor (duplicative).
- **Pricing hypothesis.** Tiered usage-based API with attractive low-end tier for indie agent builders ($99 – $199/month, capped usage) and enterprise tier for vendor-scale workloads.
- **Why we win.** MCP-native + OpenAI-tool-spec-native from one manifest. The natural-agent test passes today. We are the easiest accounting layer for an agent vendor to drop in.

### Segment D — Compliance, audit, and internal-control platforms

- **Hypothesis on demand.** Internal audit, SOX compliance, and external-audit support teams are under increasing pressure to use AI; they cannot use generative AI without a defensible audit trail. A skill catalog with provenance per claim and reproducibility per call is the only AI surface they can adopt.
- **Current alternatives.** Manual review (status quo), GRC vendors (workflow tools, not interpretation), ad-hoc internal LLM pilots (blocked by audit objections).
- **Pricing hypothesis.** Enterprise contracts with SOC 2, audit-trace export, and per-tenant isolation: $150K – $1M+/year.
- **Why we win.** The combination of citation provenance + restatement-aware versioning + audit-trace export is precisely the contract this segment needs. The MVP's `audit_trace_export` skill is a planned Stage 2 surface; today's eval-and-citation discipline is the foundation.

---

## Where the MVP is most likely to land first

Segment C (personal AI agents and custom GPT vendors) is the closest match to the MVP's current product surface — agent-native skills catalog with documented MCP and OpenAI specs. The natural-agent test was the canonical acceptance gate for the build itself.

Segment A (quant funds) is the highest-revenue-per-design-partner play; the paper-derived-skill discipline maps directly onto quant-research workflow.

Segment B (fundamentals shops) is the largest seat market but requires the most product polish (UI, alerting, reporting cadence) before it converts. Likely Year 2.

Segment D (compliance) is the highest-value-per-customer but the longest sales cycle and the highest bar on certifications (SOC 2, audit trace, restatement re-run). Likely Year 2-3.

The seed plan optimizes for Segment C + A in Year 1 to validate Stage 2 economics; coverage expansion + Segment B come in Year 2; Segment D in Year 3 once SOC 2 and full restatement-aware versioning are in place.
