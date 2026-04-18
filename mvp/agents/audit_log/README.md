# `agents/audit_log/` — machine-written persona-call audit trail

Every invocation of `mvp.agents.persona_runtime.PersonaRuntime.call()`
writes one JSON record to this directory. One record per call.

## What's in a record

Filename: `<YYYY-MM-DD>_<persona_id>_<short_hash>.json` (UTC date;
`short_hash` is a 10-char sha256 prefix over `persona_config_hash` +
`user_message_hash`).

Fields:
- `persona_id`, `persona_version`, `persona_config_hash`
- `model`, `temperature`, `max_tokens`
- `system_prompt` (the exact string sent)
- `user_message`, `user_message_hash`
- `response_text`
- `input_tokens`, `output_tokens`, `cache_hit`
- `called_at` (UTC ISO-8601)

## Do not hand-edit

This directory is **machine-written and read-only to humans**. Entries
here are the authoritative record of what the subagent personas saw
and what they produced during the MVP build. Tampering with an entry
makes the reviewability gate (`success_criteria.md` §6) untrustworthy.

## Reviewing entries

Per `../../human_layer/audit_review_guide.md`, reviewers sample
entries, run the 5-bullet checklist against each, and write a
`_review_notes/<entry_filename>.md` file summarizing any findings.
Review notes are hand-written markdown; audit-log entries themselves
are machine-written JSON.

## Ignored by tooling

The internal LLM cache used by `PersonaRuntime` lives at
`_llm_cache/` under this directory by default. It is safe to delete
the cache at any time; doing so just means the next call with the same
inputs will make a fresh API request (if a key is configured) or raise
`PersonaCallError(error_code="missing_api_key")` (if not).
