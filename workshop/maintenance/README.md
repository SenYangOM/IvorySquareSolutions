# `maintenance/` — periodic upkeep

Scripts the team runs on a schedule (weekly, monthly, quarterly) to keep the
data substrate fresh and the audit log healthy. Maintenance differs from
`research/` (one-off questions) and `coverage/` (universe-expansion events):
maintenance runs the same script on the same cadence, and the value
compounds — skipping a month's run means the caches drift, rule-template
versions fall behind GAAP updates, and the audit log accumulates unreviewed
entries.

Typical first real items, in descending priority:

- **`refresh_companyfacts.py`** — re-pull `data/companyfacts/CIK<cik>.json`
  for every CIK in the sample universe, using
  `mvp.lib.edgar.EdgarClient`'s rate limiter (≤10 req/s) and declared UA.
  Writes the new file atomically and logs a diff of concept changes vs.
  the previous cache. Weekly cadence during active development; monthly
  once the sample universe stabilizes. Catches companyfacts API schema
  changes early — they happen.
- **`audit_log_sampler.py [--persona P] [--since DATE] [--n 5]`** —
  implements the sampling rhythm in
  `mvp/human_layer/audit_review_guide.md`. Pulls 5 entries from
  `mvp/agents/audit_log/`, stratified across personas, writes a review
  template to `mvp/agents/audit_log/_review_notes/<entry>.md` for a human
  to fill in. Runs weekly under the `citation_auditor` persona's
  supervision.
- **`rule_version_bump.py <template> <new_version>`** — mechanical bump of
  a rule template's `template_version` field, with validation that the
  schema still loads and the §4.2 eval gates still pass. Captures the git
  SHA of every input to the version's fingerprint so a later
  `rule_template_version_diff.py` can compare cleanly.
- **`hash_verify.py`** — walk `data/manifest.jsonl` and re-hash every
  ingested filing / paper, reporting any drift from the recorded
  `sha256`. The scale is small (12 artifacts at MVP, maybe 40 post-paper-
  corpus) so this is quick. Quarterly cadence; catches bit-rot or mirror
  swaps.
- **`backfill_manifest_typed_expectations.py`** — back-fill Papers 1, 2, 3
  manifests' `examples[]` blocks with typed expectation fields
  (`expected_flag`, `expected_score_range`, `expected_score_tolerance`)
  so the Paper-4 `workshop/paper_to_skill/replication_harness.py` can
  drive meaningful per-example checks rather than loose liveness-only
  passes. Shape: read each manifest, consult the shipped gold case for
  the corresponding sample firm (if any), copy the gold's
  `score.value` + `tolerance` into the example's
  `expected_score_tolerance` block. One-pass maintenance; runs once,
  then the harness's coverage jumps from liveness (Papers 1-3) to
  full-typed-expectation on every shipped skill. Filed during Paper 4
  onboarding; surfaced by the harness on its first run.
- **`draft_manifest_output_shape_hint.py`** — extend
  `workshop/paper_to_skill/draft_manifest.py` to accept an
  `--output-shape` hint (e.g. `score_flag_signals` for Papers 1-3's
  shape, `density_hit_trace` for Paper 4's `hedging_density` +
  `hits_by_category` shape, `probability_classifier` for future
  ML-output skills). The scaffold's outputs-block hand-fill is
  currently ~70% of the outputs-block line count when the skill's
  output shape diverges from the generic "score / flag / components"
  template; an output-shape hint would cut that to ~30%. Filed during
  Paper 4 onboarding; motivated by the hedging-density + hits-by-
  category trace Paper 4's skill emits that the scaffold didn't
  anticipate.

Owner: the engineer on call plus the `citation_auditor` persona for the
audit-log sampling. Unlike `research/` scripts, maintenance scripts earn
light testing — a broken `refresh_companyfacts.py` that silently fails is
worse than no refresh at all, because it looks like the caches are fresh.
