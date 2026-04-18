# 09 — How It Works for Agents

**The agent is the user. Every design decision flows from that. P3 in three sentences: one manifest renders to MCP and OpenAI tool specs simultaneously; every error is a typed object; CLI and API share one registry with byte-identical outputs.**

---

## One manifest, two catalogs, three rendering targets

Each skill ships with a single `manifest.yaml`. The manifest is the source of truth for:

- **MCP tool spec** (`GET /mcp/tools`) — drop-in for Claude Desktop or any MCP-compatible agent.
- **OpenAI tool-use spec** (`GET /openai/tools`) — drop-in for chat-completions calls with `tools=[...]`.
- **CLI help text** (`mvp run --help`).
- **OpenAPI doc** (auto-generated from FastAPI routes).

The agent reads the manifest's `description_for_llm` field — 2-4 sentences written specifically for an LLM caller — to decide whether to call the skill at all. Examples from the live catalog:

> "Compute the Beneish (1999) M-score — an eight-component earnings-manipulation discriminant — for a US public company's 10-K filing. Returns the scalar M-score, the eight component values, a categorical flag, and citations back to the canonical line items. Use this to screen a filing for earnings-manipulation red flags; do NOT treat the output as a fraud verdict — the model is a classifier and its paper-reported Type I error rate is ~50%."

The "do NOT" clauses are deliberate. They prevent agents from misusing the skill — a guardrail at the *catalog* level, not at the runtime.

---

## Structured errors, every time

Every skill failure returns:

```json
{
  "error_code": "missing_prior_year_filing",
  "error_category": "MISSING_INPUT",
  "human_message": "The Beneish M-score requires both year t and year t-1 filings; year t-1 (1999-12-31) was not found for CIK 0001024401.",
  "retry_safe": true,
  "suggested_remediation": "Run `mvp ingest filings --cik 0001024401 --years 1999` and retry."
}
```

No HTTP 500 with a stack trace ever leaks to the agent. No raw Python exceptions cross the skill boundary. An agent receiving this can attempt the suggested remediation, retry, and succeed without human intervention. This is the difference between an API that an agent *can* call and an API that an agent *can recover from*.

---

## CLI ↔ API parity (verified, not aspirational)

For each of the 12 skills, an integration test (`tests/integration/test_cli_api_parity.py`) verifies that:

```
.venv/bin/python -m mvp.cli.main run analyze_for_red_flags --cik 0001024401 --year 2000-12-31
```

and

```
curl -s -X POST localhost:8000/v1/skills/analyze_for_red_flags \
    -H 'content-type: application/json' \
    -d '{"cik":"0001024401","fiscal_year_end":"2000-12-31"}'
```

return byte-identical output bodies (modulo `run_at`, `run_id`, `build_id`, and `retrieved_at` timestamps). The same registry serves both surfaces; there are no CLI-only or API-only paths.

---

## The natural-agent test (the headline acceptance gate)

We took a cold Claude instance — no system prompt naming the skills, no documentation of the catalog beyond the standard MCP tool-spec format — and gave it the MCP catalog (`/tmp/gate4_mcp.json`) plus this prompt:

> "Analyze whether Enron's 2000 10-K shows accounting red flags, with citations."

The agent's recorded behavior (from `BUILD_STATE.json` `final_gate_report.gate_4_natural_agent`):

- **Skill selection.** Converged on `analyze_for_red_flags` as the first call.
- **Input schema.** Populated `{cik: "0001024401", fiscal_year_end: "2000-12-31"}` correctly without hand-holding. The CIK was inferred from "Enron" via the agent's general knowledge; the date format was inferred from the manifest's input schema.
- **Output usefulness.** The returned JSON included both score blocks and per-component citations, which the agent then formatted into a multi-section narrative answer with inline citations.
- **Error recoverability.** When asked a follow-up that hit a missing input path (a year we hadn't ingested), the agent received the typed error envelope, surfaced the `suggested_remediation` to the user, and degraded gracefully.

The verdict in the build state file:

> "Cold agent given only `/tmp/gate4_mcp.json` converged on `analyze_for_red_flags` with correct `{cik:0001024401, fiscal_year_end:2000-12-31}`; all 4 sub-criteria (skill_selection, input_schema, output_usefulness, error_recoverability) PASS."

If this gate had failed, the surface would not be agent-native and the MVP would not be done — even if every other gate had passed. It is the single most important agent-accessibility test.

---

## End-to-end developer experience: the headline call pattern

The flow an agent follows for the headline use case:

```
# Step 1 — agent calls the composite skill
POST /v1/skills/analyze_for_red_flags
{
  "cik": "0001024401",
  "fiscal_year_end": "2000-12-31"
}

# Response (abbreviated)
{
  "m_score_result": {
    "score": -0.2422,
    "flag": "manipulator_likely",
    "components": { "DSRI": 1.365, "GMI": 2.144, ... },
    "interpretations": [
      {
        "component": "DSRI",
        "severity": "high",
        "interpretation_text": "Receivables growing materially faster than sales...",
        "citations": [
          {
            "doc_id": "0001024401/0001024401-01-500010",
            "statement_role": "balance_sheet",
            "line_item": "trade_receivables",
            "value": "1697.0",
            "excerpt_hash": "sha256:8a1c..."
          },
          ...
        ]
      },
      ...
    ]
  },
  "z_score_result": { ... },
  "provenance": {
    "composite_skill_id": "analyze_for_red_flags",
    "composite_version": "0.1.0",
    "rule_set_version": "...",
    "sub_skill_versions": { ... }
  }
}

# Step 2 — agent calls resolve_citation on one of the returned locators
# to surface the actual passage text for the user
POST /v1/citations/resolve
{
  "doc_id": "0001024401/0001024401-01-500010",
  "statement_role": "balance_sheet",
  "line_item": "trade_receivables"
}

# Response: the cited passage text + surrounding context, verifiable by hash
```

This two-step pattern — composite skill returns structured judgment with citations; agent resolves citations on demand to surface passage text — is the headline developer experience. **The agent never has to scrape the doc store directly.** The citation surface is itself a skill.

---

## Why this matters for the buyer

A personal AI agent — or a custom GPT, or a fund's internal copilot — that integrates the catalog gets:

- A drop-in MCP catalog with 12 skills today, scaling to 50+ within 6 months on the post-MVP roadmap.
- Typed inputs and outputs; structured errors; deterministic outputs (identical inputs produce identical outputs modulo timestamps).
- Per-claim citation provenance, resolvable via skill, with byte-identical hashes against the source doc store.
- One contract for both Claude Desktop / Anthropic-style integrations and OpenAI-style chat completions.

What the buyer's engineering team does **not** have to build:

- An EDGAR ingestion pipeline with rate limiting and User-Agent declarations.
- An XBRL canonicalization layer with concept-mapping fall-throughs.
- A reading of the Beneish 1999 paper (page 16) to find the actual threshold value.
- A reading of the Altman 1968 paper to find the actual X5 coefficient.
- A passage-hash + locator resolution layer.
- A regression-test suite that pins every coefficient and threshold against the source paper.

That's the developer-time math. For an agent vendor or a fund's quant-research head, the build-vs-buy decision is dominated by the second list — the things they would otherwise re-derive, get wrong on the details, and quietly carry the consequences of for years.
