"""Foundational skill layer — textbook-subsection-granular concept skills.

This is the basics layer that sits *below* the paper-derived skills in
the IvorySquare skill graph. Every node here is one subsection of a
textbook (CFA L1 outline, CPA FAR, Bertsimas LP, Boyd convex
optimization, Ross stochastic processes, Ross probability) that the
bare LLM cannot handle reliably OR that involves closed-form numerical
calculation where deterministic code is required regardless of LLM
pass rate.

Each skill ships with:
- ``concept.md`` — short paraphrased summary, intuition, examples (no
  verbatim textbook content).
- ``prereqs.yaml`` — explicit list of prerequisite skill_ids.
- ``eval/question_bank.yaml`` — 10-25 textbook-style questions with
  expected answers.
- ``eval/llm_baseline.json`` — bare-LLM pass-rate snapshot.
- ``manifest.yaml`` — standard IvorySquare manifest with
  ``layer: foundational`` and ``materialization_reason`` set to one of
  ``llm_fails``, ``closed_form_determinism``, or
  ``conceptual_high_value``.
- ``README.md`` — public-facing one-paragraph summary.
- ``code/`` (optional, required when
  ``materialization_reason == closed_form_determinism``) — a deterministic
  reference implementation with unit tests under
  ``mvp/tests/test_<skill_id>.py``.
"""

__all__: list[str] = []
