# 08 — Traction and MVP Status

**Pre-revenue. MVP working end-to-end and gate-green. Five additional papers onboarded post-MVP via a repeatable playbook with documented wall-clock compounding. Design-partner conversations in progress.** Numbers below are pulled directly from `mvp/BUILD_STATE.json` as of 2026-04-18.

---

## What is shipped today

| Item | Today | Reference |
|---|---:|---|
| Skills in registry | **12** (2 fundamental + 2 interpretation + 7 paper-derived + 1 composite) | `mvp.skills.registry.default_registry()` |
| MVP test suite (pytest) | **550 passing** | `mvp/tests/` |
| Workshop test suite | **58 passing** | `workshop/tests/` |
| Sample US large-cap filings canonicalized | **5 issuers × 2 fiscal years = 10 filings** | `data/filings/` |
| Issuers covered | Enron, WorldCom, Apple, Microsoft, Carvana | `data/manifest.jsonl` |
| Live citations resolving | **213 / 213 = 100%** | latest eval run |
| Gold-standard cases passing | **15 / 15** | `mvp/eval/gold/` |
| Academic papers onboarded as L3 skills | **7** (2 MVP — Beneish, Altman; 5 post-MVP) | `data/papers/` |
| Phase status | **All 7 MVP phases complete; final-gate report green; declared MVP-done 2026-04-18** | `BUILD_STATE.json` `mvp_declared_done_at` |
| Final-gate count | **7 / 7 passing** (eval, Enron demo, test suite, natural-agent, clean-clone walkthrough, quality grep, separation contract) | `BUILD_STATE.json` `final_gate_report` |

---

## The Enron 2000 canonical demo (the live "it's real" moment)

A single CLI command runs end-to-end on the canonical Enron case in seconds:

```
.venv/bin/python -m mvp.cli.main run analyze_for_red_flags \
    --cik 0001024401 --year 2000-12-31
```

Output (abbreviated):

```json
{
  "m_score_result": {
    "score": -0.2422,
    "flag": "manipulator_likely",
    "components": {
      "DSRI": 1.3654783625184095, "GMI": 2.1437183276812175,
      "AQI":  0.7713938466374066, "SGI": 2.5126894694854407,
      "DEPI": 1.109775564354571,  "SGAI": 0.42295331225151583,
      "LVGI": 1.353929279864726,  "TATA": 0.009526281239027221
    },
    "citations": [ ...32 line-item citations... ],
    "warnings": ["tata_approximation: ...", "pre_ixbrl_manual_extraction: ..."]
  },
  "z_score_result": {
    "score": 2.50655,
    "flag": "grey_zone",
    "components": { "X1": ..., "X2": ..., "X3": ..., "X4": ..., "X5": ... },
    "citations": [ ...8 line-item citations... ]
  },
  "provenance": { "composite_skill_id": "...", "composite_version": "0.1.0", ... }
}
```

- M-score `-0.2422` → `manipulator_likely`. (Beneish's own paper cites Enron as a canonical positive case.)
- Z-score `2.51` → `grey_zone`. (Enron filed this 10-K 11 months before its November 2001 collapse.)
- 32 + 8 = **40 citations**, all resolving against the doc store.
- Total elapsed time on the Enron demo: under 5 seconds (no LLM in the request path; deterministic templated interpretation).

This is **the demo a reviewer runs in under 30 minutes from a clean clone** — Gate 5 (Clean-Clone Walkthrough) clocked the full sequence at **164 seconds against a 1,800-second bar** (`BUILD_STATE.json` `gate_5_clean_clone_walkthrough.elapsed_seconds`).

---

## Eval results across the 5-issuer corpus

The corpus deliberately mixes 2 positives, 2 negatives, and 1 ambiguous case:

| Issuer | Year | M-score | M-flag | Z-score | Z-flag |
|---|---|---:|---|---:|---|
| Enron | 2000 | −0.2422 | manipulator_likely | 2.5065 | grey_zone |
| WorldCom | 2001 | −2.6284 | manipulator_unlikely † | 1.1016 | distress |
| Apple | 2023 | −2.3839 | manipulator_unlikely | 7.6500 | safe |
| Microsoft | 2023 | −2.4297 | manipulator_unlikely | 9.2390 | safe |
| Carvana | 2022 | null | indeterminate ‡ | null | indeterminate ‡ |

- **WorldCom Beneish (†)** is the documented explainable failure: the MVP's 16-canonical-line-item TATA approximation shifts the score across the −1.78 threshold. The deviation is recorded in the gold file's `known_deviation_explanation` block and in the manifest's `implementation_decisions`. This is exactly the "approximation is acceptable; hiding approximation is not" discipline the playbook formalizes.
- **Carvana indeterminate (‡)** because Carvana's filings don't tag depreciation+amortization as a single concept and don't tag OperatingIncomeLoss — real data-availability gaps surfaced through the `indeterminate` path rather than swept under a fudge.
- **Eval gates per `success_criteria.md` §4.2:** ≥4/5 cases pass on score, flag, and 100% citation resolution for both M and Z. Met as of the final gate run (M: 4/5 within 0.10, 4/5 flag match; Z: 5/5 within 0.10, 5/5 zone match; 213/213 citations resolved).

---

## The post-MVP paper-onboarding loop — proof the machinery compounds

After MVP completion, the team ran a controlled experiment: how long does it take to onboard one new paper (pick the construct, ingest the PDF, write the methodologist notes, ship the manifest, ship the rule template, ship the gold case, get the eval green) using the playbook the MVP build itself produced?

| # | Paper | Skill shipped | Wall-clock (min) |
|---|---|---|---:|
| 1 | Kim, Muhn, Nikolaev & Zhang (2024) — *Learning Fundamentals from Text* | `compute_mdna_upfrontedness` | 210 |
| 2 | Kim & Nikolaev (2024) — *Context-Based Interpretation of Financial Information* | `compute_context_importance_signals` | 165 |
| 3 | Bernard, Cade, Connors & de Kok (2025) — *Information acquisition by small business managers* | `compute_business_complexity_signals` | 140 |
| 4 | de Kok (2024) — *ChatGPT for Textual Analysis?* | `compute_nonanswer_hedging_density` | 125 |
| 5 | Bernard, Blankespoor, de Kok & Toynbee (2025) — *Using GPT to measure business complexity* | `predict_filing_complexity_from_determinants` | 105 |

**The 50% reduction in wall-clock from paper 1 to paper 5 is the data point.** It is not a forecast or an extrapolation — it is the actual five-iteration arc of a single team-internal playbook against a heterogeneous paper corpus (closed-form formulas, ML models with no honest proxy, behavioural studies on private data, deterministic sub-constructs from datasets MVP doesn't cover, OLS regressions with paper-exact coefficients).

The compounding came from concrete reused artifacts the playbook captured along the way:

- `workshop/paper_to_skill/extract_paper.py` — PDF → structured JSON (formulas, thresholds, reported numbers). Landed at paper 1; hardened at paper 2.
- `workshop/paper_to_skill/inspect_canonical.py` — per-issuer line-item-population matrix that catches "is this signal even computable on our substrate?" before the engineer wastes time. Landed at paper 2.
- `workshop/paper_to_skill/draft_manifest.py` — given a methodologist-notes file plus a chosen layer, emits ~70-80% of a final manifest with full provenance, limitations, and examples populated. Landed at paper 3.
- `workshop/paper_to_skill/replication_harness.py` — given a shipped manifest, runs each `examples[]` entry through the registry and produces a per-example pass/fail report. Landed at paper 4.

The playbook itself — `workshop/docs/paper_onboarding_playbook.md` — grew from a Phase-7 retrospective to a 5-branch decision tree covering closed-form formulas, ML-with-honest-proxy, ML-without-proxy (now with two sub-patterns), private-data behavioural studies, and dataset-gap-with-deterministic-sub-construct ports.

**This is the central traction claim:** the team has a measurable, repeatable, compounding playbook for converting published research into shipped skills. It is not one engineer's one-off; it is documented, tooled, tested, and improving.

---

## What works today vs. what's scaffolded

| Capability | Status | Notes |
|---|---|---|
| 12 skills end-to-end with manifests + tests + gold | **Works** | Catalog in §04. |
| Beneish + Altman canonical demo with citations | **Works** | Enron 2000 sub-5-second composite call. |
| MCP catalog + OpenAI tool-spec catalog from one manifest | **Works** | `GET /mcp/tools` and `GET /openai/tools` both return 12. |
| Natural-agent test (cold Claude solves Enron from catalog only) | **Works** | All 4 sub-criteria PASS in `gate_4_natural_agent`. |
| Restatement-aware versioning | **Logged today, auto-rerun deferred** | Restatement events logged to `data/standardize_restatement_log.jsonl`; no auto re-run yet. Post-MVP. |
| Confidence calibration | **Documented, uncalibrated** | Calibration requires ≥50 gold cases; we have 15. Post-MVP. |
| Production auth / multi-tenancy / billing | **Stub** | Localhost FastAPI; full Stage 2 production auth is post-MVP. |
| UI / frontend | **None** | CLI + JSON API only at MVP — by design (P3, agents are the user). |
| Multi-jurisdiction (IFRS, HK, A-shares) | **None** | US GAAP only at MVP; deferred to Year 2+. |
| Coverage beyond 5 sample issuers | **None at MVP** | Coverage expansion is the post-MVP workstream. |

The split is intentional: the things that work *all* trace to specific gates in `success_criteria.md`. The things that are scaffolded are explicitly post-MVP per `mvp_build_goal.md` §14 (out-of-scope items) — not half-built remnants.
