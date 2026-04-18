"""workshop — team-internal tooling (not shipped to users).

See ``workshop/README.md`` and ``mvp_build_goal.md`` §15 for the
scope + separation contract. Nothing under this package should be
imported by ``mvp/`` code (enforced by the
``grep -R 'from workshop' mvp/`` CI-style gate).
"""
