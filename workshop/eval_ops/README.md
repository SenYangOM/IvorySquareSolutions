# `eval_ops/` — eval harness extensions

Scripts that extend `mvp/eval/` beyond the single-pass `mvp eval` call. The
harness in `mvp/eval/runner.py` runs every gold case through every skill and
prints the one-page report that gates MVP completion. That's sufficient for
"did this change break anything?" but it's the ceiling, not the floor. When
we want to compare two eval runs, visualize confidence drift across a rule-
template bump, or backtest a new skill over a rolling fiscal-year window,
that work lives here.

Typical first real items, in descending priority:

- **`eval_diff.py <run_id_a> <run_id_b>`** — compare two
  `eval/reports/<date>_<run_id>.json` runs. Flag cases where the score
  changed by more than ±0.02, where the flag changed, where the citation
  count changed, or where a case newly landed in `explainable_failure`.
  Outputs a markdown report suitable for a PR description. The immediate
  use case: whenever the M-Score rule template changes, this script names
  the cases whose interpretation text changed.
- **`rolling_backtest.py skill=<id> cik=<cik> years=<y1..y2>`** — for a
  single skill and a single issuer, run the skill across a rolling window
  of fiscal years (requires `coverage/add_issuer.py` to have populated the
  filings). Produces a CSV of (year, score, flag, confidence, warnings).
  Useful for validating that a new paper's skill doesn't produce implausible
  time-series behavior before it ships.
- **`calibration_dashboard.py`** — render confidence vs. gold-outcome for
  every case across every eval run. At n=5 MVP gold cases this is not
  statistically meaningful; the point of the script is to land before n=50
  so the calibration work has a tool to land into.
- **`rule_template_version_diff.py <version_a> <version_b>`** — compare two
  rule-template versions (via git SHA or template_version field). Flag
  every severity-band edit, every threshold bump, every new contextual
  caveat. Useful when an accounting expert amends a template and wants the
  engineer to understand the scope of the change before the eval rerun.
- **`directional_match_report.py`** *(need surfaced by Paper 3 —
  `compute_business_complexity_signals`)*. Not yet written. Paper-3's
  skill emits a score whose exact value is sensitive to threshold-
  adjacent borderline cases (e.g. WorldCom FY2001's stability signal
  at |dRev/Rev| = 0.10005 vs the 0.10 threshold), so the existing
  ±0.05 tolerance-band eval check is the wrong shape — a value-match
  can still coincide with a flag-mismatch across the band boundary.
  The right eval gate for this class of skills is a **directional
  match**: does the flag fall in the same directional band (complex /
  moderate / simple / indeterminate), without requiring an exact
  value match? The eval runner's `_SCORE_KEYS` extensibility and the
  per-case `tolerance` knob accommodate this today, but a dedicated
  report that aggregates directional-match rates across the gold set
  (and flags cases where value-match passes but flag would flip on a
  threshold nudge) would make the pattern observable. Filed for when
  two or more determinants-regression-style skills are in the
  catalogue — currently just Paper 3's one.

Owner: the `evaluation_agent` persona. These scripts share their
dependencies with `mvp/eval/`: they import `EvalReport`, `CitationReport`,
and the gold_loader, all via the public API of `mvp.eval.*`. They do NOT
import the skill registry's internals — the registry's public interface is
the seam.
