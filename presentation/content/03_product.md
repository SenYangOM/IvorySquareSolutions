# 03 — Product Architecture

**Six layers internally, three layers externally. The internal decomposition keeps engineering and expert judgment disjoint; the external view keeps the buyer message simple.**

## Internal — six layers plus four cross-cutting concerns

```
                      Cross-cutting concerns
                      ─ Evaluation & gold-standard
                      ─ Versioning & provenance
                      ─ Governance / IP / legal
                      ─ Observability & metering

  L5  Delivery surface     CLI + FastAPI (auth, tenancy, billing — Stage 2)
  L4  Skills library       Manifest-driven, agent-callable, versioned, metered
  L3  Interpretation       (a) Rule set / ontology   — declarative, expert-authored
                           (b) Interpretation engine  — code, hybrid rules + constrained LLM
  L2  Standardization      Taxonomy mapping → 16 canonical line items, period & restatement detection
  L1  Document/fact store  Immutable, hash-addressed; the audit foundation
  L0  Sources & ingestion  SEC EDGAR + paper mirrors; rate-limited, declared User-Agent
```

Each separation is load-bearing:

- **L1 / L2.** The fact store is *what was filed* (immutable). Standardization is *how we map it* into a canonical schema (evolves with taxonomy and rule changes). Conflating them corrupts the audit trail every time the taxonomy moves.
- **L3(a) / L3(b).** The rule set is **knowledge**, authored and iterated by accounting experts at expert velocity (a PhD edits a YAML file and the change ships). The engine is **code**, released by engineers at engineering velocity. Coupling them forces every template change through an engineering cycle — the single most common structural error in expert-in-the-loop products.
- **L3 / L4.** Skills are orchestrations over L3 outputs with their own API surface (rate limits, billing, semver). They must be independently versioned because Stage 2 economics depend on metering and SLA per-skill.
- **L0–L2 are infrastructure, not product.** Not separately monetized. They exist to make L3 and L4 trustworthy.

**Sellable layers:** L3 (interpretation-as-a-service) is the wedge. L4 (the agent-callable skills library) is the moat once L3 is mature. L0–L2 are owned but not priced — buyers pay for expert judgment and for agent-addressable capability, not for data they can get cheaper elsewhere.

## External — three layers

For the buyer conversation we collapse the same picture to three layers:

```
  ┌──────────────────────────────────────────┐
  │  Skills API (Stage 2)                    │  ← agents call typed functions
  ├──────────────────────────────────────────┤
  │  Interpretation outputs (Stage 1)        │  ← precomputed, citation-grounded
  ├──────────────────────────────────────────┤
  │  Standardized data substrate             │  ← canonical statements + facts
  └──────────────────────────────────────────┘
```

The MVP ships a vertical slice through all three.

## Rule set vs engine — the human-layer contract

`mvp/rules/templates/m_score_components.yaml` is hand-written YAML. A real accounting PhD can read it without ever opening Python. Each component (DSRI, GMI, AQI, …) has interpretation rules with substantive text:

```yaml
component: DSRI
description: "Days Sales in Receivables Index"
formula: "(Receivables_t / Sales_t) / (Receivables_{t-1} / Sales_{t-1})"
interpretation_rules:
  - condition: "value > 1.31"
    interpretation: "Receivables growing materially faster than sales — possible
                     aggressive revenue recognition or collection issues."
    severity: "high"
    follow_up_questions:
      - "Has the company changed credit terms?"
      - "Is there a one-time customer contract inflating year-end receivables?"
    citations_required:
      - "trade_receivables_t in balance_sheet"
      - "revenue_t in income_statement"
```

The engine (`mvp/engine/rule_executor.py`) walks the YAML deterministically and emits cited interpretations. **Authoring and execution are decoupled.** A reviewer edits a YAML file and the change ships without engineering involvement.

The same contract holds for personas (`mvp/human_layer/personas/*.yaml`), gold-standard cases (`mvp/eval/gold/`), and audit-log review (`mvp/human_layer/audit_review_guide.md`).

## Why declarative-for-experts / code-for-engineers is a feature

Two failure modes we explicitly avoid:

1. **"The PhD has to ship a PR."** When experts must operate inside the codebase, expert-velocity iteration drops to engineering-velocity. The product stops compounding domain knowledge at the rate the domain evolves.
2. **"The codebase becomes a DSL."** When engineers express domain logic in code, the rule set becomes invisible to the experts who own its correctness. Reviewability dies; audit-grade claims become aspirational.

Splitting the two — a YAML/markdown surface for experts, a Python surface for engineers, and a runtime that joins them at execution — is the structural choice that lets both populations iterate at their own cadence without stepping on each other. We treat it as the load-bearing architectural decision of the product.
