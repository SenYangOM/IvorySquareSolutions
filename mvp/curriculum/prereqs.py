"""Prerequisite resolver — propose extra prerequisite edges beyond textbook ordering.

The TOC ingester adds an edge from the previous subsection to the next
within a book to encode reading order. This module supplements those
default edges with cross-references — e.g., a ``feasibility_set`` node
in *Convex Optimization* has the LP canonical form node from Bertsimas
as a prerequisite when its summary mentions "linear programs."

Inputs come from the subsection ``summary`` field on the TOC. We keep
the analyzer deterministic and offline — it does not call an LLM. The
matcher is keyword-based with a small curated map of cross-references
from concept-name → known book/section identifier; expanding the map
is a future iteration.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from mvp.curriculum.graph import CurriculumEdge, CurriculumGraph


# Curated cross-reference map: keyword (lower-cased substring) → list of
# canonical foundational concept node-id suffixes that, when present in
# the graph, are inferred as prerequisites for any node whose summary
# mentions the keyword.
_CROSS_REFS: dict[str, list[str]] = {
    "linear program": ["bertsimas_lp/ch01__01__lp_canonical_form"],
    "convex set": ["boyd_cvx/ch02__01__convex_sets_definition"],
    "convex function": ["boyd_cvx/ch03__01__convex_function_definition"],
    "lagrangian": ["boyd_cvx/ch05__01__lagrangian_dual"],
    "kkt": ["boyd_cvx/ch05__02__kkt_conditions"],
    "duality": ["boyd_cvx/ch05__01__lagrangian_dual"],
    "probability axiom": ["ross_prob/ch02__01__sample_space_axioms"],
    "conditional probability": ["ross_prob/ch03__01__conditional_definition"],
    "markov chain": ["ross_stoch/ch04__01__markov_chain_definition"],
    "expectation": ["ross_prob/ch04__02__expectation_definition"],
    "free cash flow": ["cfa_l1_corp/ch02__01__fcfe_fcff_definition"],
    "discount rate": ["cfa_l1_corp/ch01__02__cost_of_capital"],
    "income statement": ["cfa_l1_fsa/ch02__01__income_statement_structure"],
    "balance sheet": ["cfa_l1_fsa/ch03__01__balance_sheet_structure"],
    "accruals": ["cfa_l1_fsa/ch05__02__accrual_quality_basics"],
    "depreciation": ["cpa_far/ch02__03__depreciation_methods"],
    "deferred tax": ["cpa_far/ch04__01__deferred_tax_basics"],
}


@dataclass(frozen=True)
class ProposedEdge:
    """A candidate prerequisite edge plus the reason and matched keyword."""

    source: str
    target: str
    reason: str
    matched_keyword: str


def propose_cross_reference_edges(
    graph: CurriculumGraph,
    *,
    summaries: dict[str, str],
) -> list[ProposedEdge]:
    """Return prerequisite edges suggested by keyword matches in summaries.

    Parameters
    ----------
    graph:
        The curriculum graph (used to resolve concept-name suffixes
        against actual node ids).
    summaries:
        Mapping of node_id → free-text summary (the ``summary`` field
        from the TOC YAML, kept off-graph because the graph YAML is
        intentionally compact).

    The returned list is filtered against the graph: only edges whose
    source AND target both exist as nodes are kept. Self-loops and
    edges that would close a cycle are dropped.
    """
    proposals: list[ProposedEdge] = []
    # Suffix index: "<book_id>/chXX__YY__sub" → full node id. The full
    # node id format is ``foundational/<branch>/<book_id>/chXX__YY__sub``,
    # so we drop the first two segments to get the suffix that matches
    # the entries in :data:`_CROSS_REFS`.
    full_suffix_to_id: dict[str, str] = {}
    for nid in graph.nodes:
        parts = nid.split("/", 3)
        if len(parts) == 4:
            tail = f"{parts[2]}/{parts[3]}"  # book_id/chXX__YY__sub
            full_suffix_to_id[tail] = nid

    for target_id, summary in summaries.items():
        if target_id not in graph.nodes:
            continue
        normalized = re.sub(r"\s+", " ", summary.lower())
        for kw, suffixes in _CROSS_REFS.items():
            if kw not in normalized:
                continue
            for sfx in suffixes:
                src = full_suffix_to_id.get(sfx)
                if src is None or src == target_id:
                    continue
                proposals.append(
                    ProposedEdge(
                        source=src,
                        target=target_id,
                        reason="cross_reference_keyword",
                        matched_keyword=kw,
                    )
                )
    # Deduplicate.
    seen: set[tuple[str, str]] = set()
    unique: list[ProposedEdge] = []
    for p in proposals:
        key = (p.source, p.target)
        if key in seen:
            continue
        seen.add(key)
        unique.append(p)
    return unique


def apply_proposals(
    graph: CurriculumGraph,
    proposals: Iterable[ProposedEdge],
) -> int:
    """Add proposals to ``graph`` as prerequisite edges. Returns the count added.

    Counts only proposals that actually grow the edge list; duplicates and
    no-op silent returns from :meth:`CurriculumGraph.add_edge` are not
    counted (the graph deduplicates by ``(source, target, relation)``).
    """
    added = 0
    for p in proposals:
        before = len(graph.edges)
        try:
            graph.add_edge(
                CurriculumEdge(
                    source=p.source,
                    target=p.target,
                    relation="prerequisite",
                    reason=f"{p.reason}:{p.matched_keyword}",
                )
            )
        except ValueError:
            # Cycle, missing node — skip.
            continue
        if len(graph.edges) > before:
            added += 1
    return added


__all__ = ["ProposedEdge", "apply_proposals", "propose_cross_reference_edges"]
