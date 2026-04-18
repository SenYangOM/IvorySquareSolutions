# `workshop/` — team-internal tooling

`workshop/` is the **team-only** codebase that sits alongside `mvp/`. It holds
the scripts, playbooks, and operational docs the founding team uses to grow,
maintain, and audit the product. Nothing here is shipped to end users — end
users only see `mvp/`.

At MVP (2026-04-17) `workshop/` is a **documentation skeleton**. Executable
scripts under `paper_to_skill/`, `research/`, `coverage/`, `eval_ops/`, and
`maintenance/` land post-MVP as the team needs them (see
`mvp_build_goal.md` §15, `success_criteria.md` §13).

## When to reach for `workshop/` vs `mvp/`

| If you are… | Edit here |
|---|---|
| Adding a user-callable skill, endpoint, or data contract | `mvp/` |
| Adding a rule template, persona config, or gold case | `mvp/` (declarative; no Python) |
| Onboarding a new paper (writing the playbook steps) | `workshop/paper_to_skill/` |
| Running a one-off backtest or coverage scan | `workshop/eval_ops/` or `workshop/coverage/` |
| Writing a script the team runs weekly to keep caches fresh | `workshop/maintenance/` |
| Documenting how the team does its own work | `workshop/docs/` |

## Subfolder index

| Folder | Purpose |
|---|---|
| [`paper_to_skill/`](paper_to_skill/) | The **hero workflow** — turning an academic paper into a shipped skill. The README here is the retrospective playbook from onboarding Beneish (1999) and Altman (1968). Executable scripts (`extract_paper.py`, `draft_manifest.py`, `replication_harness.py`) land post-MVP when the second paper lands. |
| [`research/`](research/) | Ad-hoc research scripts — EDGAR queries, peer-group scans, XBRL concept-coverage audits. One-off tools that don't need to graduate to `mvp/`. |
| [`coverage/`](coverage/) | Scripts to expand the issuer / filing universe beyond the 5 MVP samples. Owners of new-CIK / new-fiscal-year / new-filing-type onboarding live here. |
| [`eval_ops/`](eval_ops/) | Eval-harness extensions — backtests over rolling windows, regression diffs between rule-template versions, calibration dashboards. Consumes `mvp/eval/` but lives outside the product boundary. |
| [`maintenance/`](maintenance/) | Periodic upkeep — refreshing companyfacts caches, sampling audit-log entries, bumping rule-template versions when a standard changes. |
| [`docs/`](docs/) | Internal-only playbooks: the paper-onboarding playbook, the skill-design review checklist, and any future team-ops docs. |

## The separation contract (load-bearing)

`workshop/` is strictly a **consumer** of `mvp/`, never a dependency of it.

- `workshop/` scripts MAY import from `mvp.lib` and MAY call `mvp/skills/` via
  the registry.
- `workshop/` scripts MUST NOT import from `mvp/skills/**/skill.py` or
  `mvp/engine/` directly — the registry is the only seam.
- `mvp/` code MUST NOT import from `workshop/`. A single grep enforces this:

  ```
  grep -R "from workshop" mvp/   # must print nothing
  ```

If you find yourself tempted to import a `workshop/` helper from `mvp/`, stop:
either the helper belongs in `mvp.lib` (promote it) or the `mvp/` caller belongs
in `workshop/` (move it). Bidirectional dependencies are what this contract
prevents.

## Quality bar

`mvp/` is held to the §11 build-quality gates (zero TODO, zero bare-except,
every function tested or integration-exercised). `workshop/` is intentionally
looser: exploratory notebooks, scratch scripts, and commented-out experiments
are permitted. The separation contract above is the only hard rule.

## The hero workflow

For the first post-MVP expansion (processing the 5 papers under
`paper_examples/`), start at [`paper_to_skill/README.md`](paper_to_skill/README.md)
and [`docs/paper_onboarding_playbook.md`](docs/paper_onboarding_playbook.md).
The two documents together form the complete onboarding path from a fresh PDF
to a shipped, evaluated skill.
