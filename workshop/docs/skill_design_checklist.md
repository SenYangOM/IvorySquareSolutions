# Skill-design review checklist

One-page checklist a reviewer runs before approving a new skill's PR.
Derived from what reviewing the 7 MVP skills actually required. Each box is
either obviously satisfied from the manifest/code, or requires a specific
file to open and check.

Estimated review time: 20 minutes per skill.

## Identity and metadata

- [ ] `skill_id` is unique, snake_case, immutable. No existing skill uses
      this id.
- [ ] `version` is semver (e.g. `0.1.0`). Major bumps accompany breaking
      input/output changes.
- [ ] `layer` is one of `fundamental | interpretation | paper_derived |
      composite` and matches the skill's role.
- [ ] `status` is `alpha` for a first ship; don't start at `beta` or `ga`.
- [ ] `maintainer_persona` is one of the 4 MVP personas or a named human
      successor.
- [ ] `description_for_llm` is ≥80 characters and answers: what does this
      skill do, typical inputs, typical outputs, when NOT to call it. A
      cold LLM given only this description should pick the right skill
      from a catalog of 10+.

## Provenance (paper-derived only)

- [ ] `provenance.source_papers[]` has at least one entry with full
      citation, DOI/URL, `local_pdf` path, and `pdf_sha256`.
- [ ] `provenance.study_scope` names `asset_class`, `time_period_in_paper`,
      `sample_size_in_paper`.
- [ ] `provenance.methodology.formulas_extracted_from_paper` lists every
      formula the skill depends on, in the paper's notation.
- [ ] Every coefficient in every formula is to the paper's exact
      precision (0.999 not 1.0; 4.679 not 4.68). No rounding.
- [ ] `provenance.expected_results` names the replication bar (what the
      paper reports as the canonical numbers for at least one worked
      example).

## Implementation decisions

- [ ] Every place the paper is ambiguous is named in
      `implementation_decisions[]`. No silent calls.
- [ ] Every non-trivial approximation (like Beneish's 16-canonical TATA)
      is named with `decision`, `rationale`, and `reviewer_persona`.
- [ ] Every decision that affects the headline metric is surfaced as a
      runtime warning when the skill runs.

## Inputs / outputs

- [ ] `inputs.type: object`, `required: [...]`, and
      `additionalProperties: false` set (or justified if true).
- [ ] Every input property has a `description` ≥ 30 characters written
      for an LLM reader.
- [ ] Every input property has a type and (where applicable) a `pattern`,
      `format`, or `enum`.
- [ ] `outputs.type: object`, `required: [...]` lists every non-null
      output field.
- [ ] Every output property has a `description` written for an LLM reader.
- [ ] Outputs include (at minimum) the headline metric, a categorical
      flag, a `citations[]` array, a `confidence` object, and a
      `warnings[]` array.

## Citation contract

- [ ] `citation_contract.required_per_field` covers every claim the skill
      makes. The composite of required citations names every canonical
      line item the skill consumes.
- [ ] `citation_contract.hash_algorithm: sha256`.
- [ ] `citation_contract.locator_format` is documented (either the
      standard `<cik>/<accession>::<role>::<line_item>` or a named
      extension like `market_data::<cik>::<fye>`).

## Rule template (L2 / L3 with per-component rules)

- [ ] `mvp/rules/templates/<skill_id>_components.yaml` exists.
- [ ] Every component has ≥4 interpretation_rules partitioning the real
      line with no gaps (verified by
      `tests/unit/rules/test_rule_template_schema.py`).
- [ ] Every `medium`, `high`, or `critical` rule has ≥2
      `follow_up_questions`.
- [ ] Every `interpretation` string is ≥30 characters of substantive
      accountant voice (no "elevated reading, consistent with
      manipulation" boilerplate).
- [ ] Every `citations_required` entry references a canonical line item in
      `mvp/standardize/mappings.py` (or an approved fixture like
      `market_value_of_equity`).
- [ ] Every component's `contextual_caveats[]` names known edge cases
      (data-quality, sector-specific, paper-sample limits).

## Tests

- [ ] At least one unit test per public helper function in `skill.py`.
      Hermetic — uses `tmp_path`, `monkeypatch`, `httpx.MockTransport` as
      needed.
- [ ] One integration test under `tests/integration/` that runs the whole
      skill against real fixture data (an MVP sample filing or a
      constructed canonical-statements fixture).
- [ ] Paper-replication test asserts ±0.05 on the paper's reported
      headline metric for at least one worked example. Tolerance widening
      requires a documented reason pointing at an
      `implementation_decisions` entry.
- [ ] Determinism: two back-to-back calls with identical inputs produce
      byte-identical output bodies (modulo `run_at`, `run_id`, `build_id`,
      per-citation `retrieved_at`). The CLI↔API parity test covers this
      for all registry skills.

## Gold cases

- [ ] If the skill can run on one or more of the 5 MVP sample filings,
      `mvp/eval/gold/<skill_short>/<issuer>_<year>.yaml` exists for each.
- [ ] Each gold case names `expected.score` (range OR value+tolerance),
      `expected.flag`, `citation_expectations.must_cite`,
      `expected.confidence.{min,max}`.
- [ ] `notes.source_of_expected` is specific — "author judgment" is too
      weak; "Phase 4 live run + ±0.10 band" is the standard pattern.
- [ ] `known_deviation_explanation` is populated for any gold case that
      deliberately records an explainable failure.
- [ ] `last_reviewed_at` and `last_reviewed_by` are current.

## Registry and surface

- [ ] `SkillManifest.load_from_yaml(path)` succeeds in strict mode.
- [ ] `mvp skills list` shows the skill.
- [ ] `mvp skills show <id>` prints the full manifest cleanly.
- [ ] `mvp skills mcp | jq length` and `mvp skills openai | jq length`
      both increase by 1.
- [ ] A CLI invocation and an equivalent API POST produce byte-identical
      outputs (modulo the 4 volatile fields).
- [ ] Error paths return the 5-field structured envelope
      (`error_code`, `error_category`, `human_message`, `retry_safe`,
      `suggested_remediation`). No HTTP 500 with a traceback.

## Documentation

- [ ] `mvp/skills/<layer>/<skill_id>/README.md` exists. Paper summary,
      coefficient derivation, implementation decisions, MVP eval coverage,
      known limitations.
- [ ] Per-skill README is authored in the maintainer persona's voice
      (match the tone of the existing Beneish/Altman READMEs).
- [ ] The README links back to the manifest and to any relevant rule
      template.

## Build-quality gates (inherited from §11)

- [ ] Zero TODO / FIXME / XXX markers in the new code.
- [ ] Zero `pass` placeholders in production paths (not counting
      `contextlib.suppress` no-ops with a documented rationale).
- [ ] Zero bare `except:` constructs.
- [ ] No commented-out blocks > 2 lines.
- [ ] Every new module imports cleanly under `python -W error`.
- [ ] No `from workshop` imports anywhere under `mvp/`.

## Final eval gate

- [ ] `mvp eval` still passes §4.2 gates (4/5 M, 5/5 Z, 100% citations)
      for the pre-existing skills. New skill's eval_metrics line up with
      its own manifest declaration.
- [ ] No regressions in the 380+ existing tests.

---

If any box is unchecked after a 20-minute review, the PR doesn't merge
until it is. This checklist is **the** gate between draft and ship.
