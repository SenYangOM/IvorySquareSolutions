"""workshop.paper_to_skill — the hero workflow for onboarding papers.

See ``workshop/paper_to_skill/README.md`` for the playbook. This
package holds the executable helpers that support the playbook:

- :mod:`extract_paper` — PDF → structured metadata. First drafted
  during paper-onboarding iteration 1 (fundamentals_text.pdf).

More helpers land as subsequent papers surface the need:

- ``draft_manifest.py`` — scaffold a ``manifest.yaml`` from an
  extraction. Post-MVP.
- ``replication_harness.py`` — run a drafted skill against the
  paper's worked examples. Post-MVP.
"""
