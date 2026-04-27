"""Unit tests for ``mvp.curriculum.prereqs``."""

from __future__ import annotations

from pathlib import Path

from mvp.curriculum.graph import CurriculumEdge, CurriculumGraph, CurriculumNode
from mvp.curriculum.prereqs import apply_proposals, propose_cross_reference_edges


def _node(book_id: str, ch: int, sec: int, sub: str, *, branch: str = "or") -> CurriculumNode:
    return CurriculumNode(
        id=f"foundational/{branch}/{book_id}/ch{ch:02d}__{sec:02d}__{sub}",
        branch=branch,
        book_id=book_id,
        chapter=ch,
        section=sec,
        subsection=sub,
        title=f"{book_id} {ch}.{sec} {sub}",
    )


def test_propose_cross_reference_edges_links_known_concepts(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    src = _node("bertsimas_lp", 1, 1, "lp_canonical_form")
    tgt = _node("boyd_cvx", 5, 1, "lagrangian_dual")
    g.add_node(src)
    g.add_node(tgt)
    summaries = {
        tgt.id: "lagrangian dual function for a linear program with constraints",
    }
    proposals = propose_cross_reference_edges(g, summaries=summaries)
    keywords = {p.matched_keyword for p in proposals}
    assert "linear program" in keywords
    sources = {p.source for p in proposals if p.matched_keyword == "linear program"}
    assert src.id in sources


def test_apply_proposals_skips_cycles(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    a = _node("bertsimas_lp", 1, 1, "lp_canonical_form")
    b = _node("boyd_cvx", 5, 1, "lagrangian_dual")
    g.add_node(a)
    g.add_node(b)
    g.add_edge(CurriculumEdge(source=b.id, target=a.id))  # b -> a
    summaries = {a.id: "linear program intro"}
    # propose_cross_reference_edges would add b -> a again (already exists)
    # AND a -> a is impossible. We craft summaries to provoke a cycle test.
    summaries[a.id] = "lagrangian description"  # would add b -> a duplicate via 'lagrangian'
    proposals = propose_cross_reference_edges(g, summaries=summaries)
    added = apply_proposals(g, proposals)
    # All proposals are dups or cycles -> 0 added.
    assert added == 0


def test_propose_returns_empty_for_unmatched_summaries(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    n = _node("ross_prob", 2, 1, "sample_space_axioms")
    g.add_node(n)
    proposals = propose_cross_reference_edges(
        g, summaries={n.id: "no recognized cross-ref keyword present here"}
    )
    assert proposals == []
