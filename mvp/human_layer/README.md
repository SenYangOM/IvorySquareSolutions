# `mvp/human_layer/` — the seam with human contributors

This directory is **the entry point for every human domain expert who
contributes to the MVP**. Nothing in this directory requires Python
knowledge: an accounting expert, a QA engineer, or an audit reviewer
can make useful changes here using only a text editor and domain
knowledge.

That design is load-bearing. It is Operating Principle P1 of the
project (see `../../mvp_build_goal.md` §0 and `../../CLAUDE.md`): a
change in the human layer must not require recompilation, code review,
or engineering involvement; a change in the engineering layer must not
require domain-expert review.

## What lives here

The four kinds of human-layer artifact, each with its own guide:

| Artifact | Location | Guide |
|---|---|---|
| Persona configs | `personas/*.yaml` | (this README's §"Editing a persona") |
| Rule templates | `../rules/templates/*.yaml` and `../rules/ontology.yaml` | [`rule_authoring_guide.md`](rule_authoring_guide.md) |
| Gold-standard eval cases | `../eval/gold/**/*.yaml` | [`gold_authoring_guide.md`](gold_authoring_guide.md) |
| Audit-log reviews | `../agents/audit_log/` (machine-written), reviews under `_review_notes/` | [`audit_review_guide.md`](audit_review_guide.md) |

Everything else in the codebase (`mvp/lib/`, `mvp/ingestion/`,
`mvp/store/`, `mvp/standardize/`, `mvp/engine/`, `mvp/skills/`,
`mvp/api/`, `mvp/cli/`) is engineering-layer code. Domain experts do
not edit those directories.

## The personas

Four LLM-subagent personas stand in for the human experts who will
eventually take over each role. Each persona's prompt, model
assignment, and contract description live in
`personas/<persona_id>.yaml`:

- `accounting_expert.yaml` — Stern accounting PhD; authors rule
  templates + L2 interpretation text.
- `quant_finance_methodologist.yaml` — quant-finance PhD; authors
  provenance blocks + paper summaries.
- `evaluation_agent.yaml` — QA engineer; authors gold cases + eval
  reports.
- `citation_auditor.yaml` — audit / compliance; authors integrity
  reports.

### Editing a persona

A human contributor who is taking over a persona's role edits exactly
one file: `personas/<their_persona>.yaml`. The fields are:

- `id` — must match the file stem. Do not change.
- `role_description` — one-paragraph summary of what this persona does
  in the project.
- `model` — Anthropic model id. Change with care; model assignments are
  recorded in `mvp_build_goal.md` §13 decision 1.
- `system_prompt` — the persona's voice. This is the field a human
  expert replaces with their own style guide when they take the role
  over.
- `input_contract_description` — in English, what the persona receives.
- `output_contract_description` — in English, what the persona
  produces.
- `replacement_note` — the path for a real human to take over.
- `provenance.authored_by`, `provenance.authored_at`,
  `provenance.version` — authoring metadata.

Every change to a persona YAML should bump `provenance.version` (semver)
and update `provenance.authored_at`.

### Replacing a persona with a real human

Two supported patterns:

1. **Edit in place.** The human takes over authorship of the persona
   YAML. They replace `system_prompt` with their own style guide,
   update `provenance.authored_by` to their name, bump the version,
   and optionally point `model` at `claude-sonnet-4-6` (or whatever
   model they want to do the bulk of their own drafting with).

2. **Bypass the runtime.** The human writes the downstream artifacts
   directly — rule templates, gold cases, audit reviews. The
   `PersonaRuntime` class never gets called for that persona. The
   YAML's `replacement_note` field documents this path; no engineering
   change is required.

## Real examples in this repo

Everything the MVP actually shipped under the human layer is available as
worked examples. If you are taking over a persona role, these are the
first files to open:

- **Persona configs** — all four YAMLs under `personas/`. The
  `accounting_expert.yaml` (822 words of system prompt) is the longest and
  most representative.
- **Rule templates** — `../rules/templates/m_score_components.yaml`
  (8 Beneish components × 4 severity bands + composite threshold -1.78) and
  `../rules/templates/z_score_components.yaml` (5 Altman components × 4
  bands + 3-zone thresholds). Both authored by the `accounting_expert`
  persona during Phase 3.
- **Gold cases** — all 10 YAMLs under `../eval/gold/beneish/` and
  `../eval/gold/altman/`. Each case was authored during Phase 5 and carries
  a `notes.source_of_expected` line documenting where the expected value
  came from.
- **Audit-log review checklist** — `audit_review_guide.md` § "The
  five-bullet checklist" is the exact checklist the `citation_auditor`
  persona uses.

## Why this split matters

Read `../../CLAUDE.md` §"Operating principles" for the full rationale.
The short version: domain experts produce declarative artifacts;
engineers produce code; the two do not block each other. The runtime
in `mvp/agents/` exists to translate declarative persona configs into
LLM calls during the MVP phase. The moment real humans take over any
role, the code path they replace simply stops being used for that role
— no reorg required.
