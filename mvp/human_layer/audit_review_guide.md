# Audit-log review guide

One-page checklist for a reviewer sampling entries from
`mvp/agents/audit_log/`. Owned by the `citation_auditor` persona.

Each audit-log entry is one JSON record written by
`PersonaRuntime.call()`. Entries are named
`<YYYY-MM-DD>_<persona_id>_<short_hash>.json`. The directory is never
hand-edited; reviewers leave their review notes in
`mvp/agents/audit_log/_review_notes/`.

## Sampling rhythm

- **Weekly rhythm.** Sample 5 audit-log entries per week across all
  personas, stratified so each persona is represented at least once.
- **Event-triggered.** After a rule-template bump, sample the next
  batch of `accounting_expert` entries. After a new paper is
  onboarded, sample the next batch of `quant_finance_methodologist`
  entries.
- **Evidence of drift.** Any sampled entry whose `persona_config_hash`
  does not match the current YAML's hash is sampled for the next
  audit.

## The five-bullet checklist

For each sampled audit-log entry:

1. **Persona-config-hash drift.** Compute the sha256 of the current
   YAML at `mvp/human_layer/personas/<persona_id>.yaml` (via
   `mvp.agents.persona_runtime._persona_config_hash`) and confirm it
   matches the entry's `persona_config_hash`. If it doesn't, the
   persona was changed between the call and the review — note and
   move on (this is not itself a finding, just context).

2. **Anchoring.** Read the `user_message` and the `response_text`. The
   response MUST be anchored in the user message: every numeric claim
   in the response should be a number that appears in the user
   message, or a derivation that is obviously correct from the user-
   message numbers. Finding: the response includes a number that is
   not derivable from the user message (severity: blocker).

3. **Fabricated line items.** Scan the response for references to
   canonical line items. Every named line item must appear in
   `mvp/standardize/mappings.py`. Finding: the response references a
   line item not in the canonical set (severity: blocker).

4. **Contract compliance.** Confirm the response shape matches the
   persona's `output_contract_description`. For the
   `accounting_expert` producing a rule template, that means valid
   YAML with the shape documented in `rule_authoring_guide.md`. For
   the `quant_finance_methodologist` producing a provenance block,
   that means every numeric claim carries a page / line / table
   reference. Finding: response shape does not match the contract
   (severity: major).

5. **Severity-band coverage.** For responses that are rule-template
   content, confirm every `medium`, `high`, or `critical` rule has
   at least 2 `follow_up_questions` and that the interpretation
   string is ≥ 30 characters of substantive accountant voice (not
   "elevated reading, consistent with manipulation signals"). Finding:
   vacuous placeholder (severity: major — this is the §8 negative
   gate in `success_criteria.md`).

## Writing up a review

A review note is one file per audit-log entry sampled, under
`mvp/agents/audit_log/_review_notes/`:

```markdown
# Review of 2026-04-17_accounting_expert_f4e2c91abc.json

Reviewed by: [reviewer name]
Reviewed at: 2026-04-18 09:15 UTC

## Findings

1. [none / blocker / major / minor] [one-line description]
2. ...

## Actions taken

- None / filed ticket / amended rule template / bumped persona version
```

A review with zero findings still gets a file — the record of sampling
is itself valuable.

## When a finding is a blocker

The `citation_auditor` persona's voice is: **zero tolerance on
fabricated citations and fabricated line-item references**. A single
blocker finding pauses the skill it affects until remediated. The
audit log becomes a gate, not a report.

## Replacement path for a real human reviewer

The internal-audit partner who replaces the `citation_auditor` persona
can:

1. Use this same guide — the checklist is framework-independent.
2. Edit `personas/citation_auditor.yaml`'s `system_prompt` to record
   their own checklist wording.
3. Or: stop invoking the persona entirely and author the review notes
   under `_review_notes/` directly. No engineering change required.
