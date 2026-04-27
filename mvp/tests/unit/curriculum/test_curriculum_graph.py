"""Unit tests for ``mvp.curriculum.graph``."""

from __future__ import annotations

from pathlib import Path

import pytest

from mvp.curriculum.graph import (
    CurriculumEdge,
    CurriculumGraph,
    CurriculumNode,
)


def _make_node(node_id: str, *, branch: str = "or", book_id: str = "demo") -> CurriculumNode:
    return CurriculumNode(
        id=node_id,
        branch=branch,
        book_id=book_id,
        chapter=1,
        section=1,
        subsection="x",
        title=f"Title {node_id}",
    )


def test_add_node_and_edge_roundtrip(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "graph.yaml")
    g.add_node(_make_node("a"))
    g.add_node(_make_node("b"))
    g.add_edge(CurriculumEdge(source="a", target="b"))
    g.save()

    g2 = CurriculumGraph.load(tmp_path / "graph.yaml")
    assert sorted(g2.nodes) == ["a", "b"]
    assert len(g2.edges) == 1
    assert g2.edges[0].source == "a"


def test_add_node_idempotent(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node("a"))
    g.add_node(_make_node("a"))  # Idempotent re-add
    assert len(g.nodes) == 1


def test_add_node_conflict_requires_overwrite(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node("a"))
    different = CurriculumNode(
        id="a",
        branch="or",
        book_id="demo",
        chapter=2,  # changed
        section=1,
        subsection="x",
        title="Title a",
    )
    with pytest.raises(ValueError):
        g.add_node(different)
    g.add_node(different, overwrite=True)
    assert g.nodes["a"].chapter == 2


def test_add_edge_rejects_unknown_endpoint(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node("a"))
    with pytest.raises(ValueError):
        g.add_edge(CurriculumEdge(source="a", target="missing"))


def test_add_edge_rejects_self_loop(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node("a"))
    with pytest.raises(ValueError):
        g.add_edge(CurriculumEdge(source="a", target="a"))


def test_add_edge_rejects_cycle(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    for nid in ("a", "b", "c"):
        g.add_node(_make_node(nid))
    g.add_edge(CurriculumEdge(source="a", target="b"))
    g.add_edge(CurriculumEdge(source="b", target="c"))
    with pytest.raises(ValueError):
        g.add_edge(CurriculumEdge(source="c", target="a"))


def test_topo_sort_orders_prereqs_first(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    for nid in ("a", "b", "c"):
        g.add_node(_make_node(nid))
    g.add_edge(CurriculumEdge(source="a", target="b"))
    g.add_edge(CurriculumEdge(source="b", target="c"))
    order = g.topo_sort()
    assert order.index("a") < order.index("b") < order.index("c")


def test_render_dot_includes_status_color(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    g.add_node(_make_node("a"))
    g.update_materialization("a", reason="closed_form_determinism", status="materialized")
    dot = g.render_dot()
    assert "digraph curriculum" in dot
    assert "lightgreen" in dot
    assert "penwidth=2" in dot  # closed_form_determinism gets bold border


def test_prereqs_and_dependents(tmp_path: Path) -> None:
    g = CurriculumGraph(path=tmp_path / "g.yaml")
    for nid in ("a", "b", "c"):
        g.add_node(_make_node(nid))
    g.add_edge(CurriculumEdge(source="a", target="b"))
    g.add_edge(CurriculumEdge(source="a", target="c"))
    assert g.prereqs_of("b") == ["a"]
    assert g.dependents_of("a") == ["b", "c"]
