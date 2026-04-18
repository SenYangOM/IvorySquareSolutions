"""Proj_ongoing MVP package root.

The sub-packages mirror the layered architecture described in
``mvp_build_goal.md`` (§5): ``lib`` for cross-cutting utilities,
``ingestion`` for L0, ``store`` for L1, ``standardize`` for L2, ``engine``
for L3(b), ``rules`` for L3(a) declarative knowledge (YAML only),
``skills`` for L4, ``api``/``cli`` for L5, and ``agents`` for the LLM
persona runtime.
"""

__version__ = "0.0.1"
