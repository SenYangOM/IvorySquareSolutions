"""Curriculum DAG store — nodes are subsection skill_ids, edges are prerequisite arcs.

The graph is YAML-backed at ``mvp/curriculum/graph.yaml`` so a domain
expert can audit and edit prerequisite relationships without touching
Python (operating principle P1).

Schema (YAML on disk)
---------------------

.. code-block:: yaml

    version: 1
    nodes:
      - id: foundational/or/bertsimas_lp/ch01__01__lp_canonical_form
        branch: or
        book_id: bertsimas_lp
        chapter: 1
        section: 1
        subsection: lp_canonical_form
        title: "Linear program canonical form"
        materialization_reason: null            # set after llm_baseline runs
        materialization_status: candidate       # candidate | dropped | materialized
        layer: foundational
    edges:
      - source: foundational/or/bertsimas_lp/ch01__01__lp_canonical_form
        target: foundational/or/bertsimas_lp/ch01__02__feasibility
        relation: prerequisite
        reason: "textbook_ordering"

Public API
----------

- :class:`CurriculumGraph` — load/save + add_node/add_edge/topo_sort/render_dot.
- :func:`load_default` — returns the singleton graph backed by
  ``mvp/curriculum/graph.yaml``. Created on first read if absent.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

import yaml


_GRAPH_VERSION = 1
_DEFAULT_GRAPH_PATH = Path(__file__).resolve().parent / "graph.yaml"


@dataclass
class CurriculumNode:
    """One subsection node in the curriculum graph."""

    id: str
    branch: str
    book_id: str
    chapter: int
    section: int
    subsection: str
    title: str
    materialization_reason: str | None = None
    materialization_status: str = "candidate"
    layer: str = "foundational"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CurriculumNode":
        return cls(
            id=str(data["id"]),
            branch=str(data["branch"]),
            book_id=str(data["book_id"]),
            chapter=int(data["chapter"]),
            section=int(data["section"]),
            subsection=str(data["subsection"]),
            title=str(data["title"]),
            materialization_reason=data.get("materialization_reason"),
            materialization_status=str(data.get("materialization_status", "candidate")),
            layer=str(data.get("layer", "foundational")),
        )


@dataclass
class CurriculumEdge:
    """A prerequisite arc — ``source`` must be understood before ``target``."""

    source: str
    target: str
    relation: str = "prerequisite"
    reason: str = "textbook_ordering"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CurriculumEdge":
        return cls(
            source=str(data["source"]),
            target=str(data["target"]),
            relation=str(data.get("relation", "prerequisite")),
            reason=str(data.get("reason", "textbook_ordering")),
        )


@dataclass
class CurriculumGraph:
    """In-memory curriculum DAG with YAML persistence."""

    path: Path = field(default_factory=lambda: _DEFAULT_GRAPH_PATH)
    nodes: dict[str, CurriculumNode] = field(default_factory=dict)
    edges: list[CurriculumEdge] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Persistence.
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> "CurriculumGraph":
        """Load the graph from ``path``. Creates an empty graph file on first read."""
        p = Path(path) if path is not None else _DEFAULT_GRAPH_PATH
        graph = cls(path=p)
        if not p.is_file():
            graph.save()
            return graph
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(
                f"curriculum graph YAML at {p} must be a mapping, "
                f"got {type(raw).__name__}"
            )
        for n in raw.get("nodes") or []:
            node = CurriculumNode.from_dict(n)
            graph.nodes[node.id] = node
        for e in raw.get("edges") or []:
            graph.edges.append(CurriculumEdge.from_dict(e))
        return graph

    def save(self) -> None:
        """Write the graph back to disk in canonical form (sorted nodes/edges)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.id)
        sorted_edges = sorted(self.edges, key=lambda e: (e.source, e.target))
        payload = {
            "version": _GRAPH_VERSION,
            "nodes": [asdict(n) for n in sorted_nodes],
            "edges": [asdict(e) for e in sorted_edges],
        }
        text = yaml.safe_dump(payload, sort_keys=False, allow_unicode=True)
        self.path.write_text(text, encoding="utf-8")

    # ------------------------------------------------------------------
    # Mutation.
    # ------------------------------------------------------------------

    def add_node(self, node: CurriculumNode, *, overwrite: bool = False) -> None:
        if node.id in self.nodes and not overwrite:
            existing = self.nodes[node.id]
            # Idempotent re-add with identical fields is OK.
            if asdict(existing) == asdict(node):
                return
            raise ValueError(
                f"node {node.id!r} already exists with different fields; "
                "pass overwrite=True to replace"
            )
        self.nodes[node.id] = node

    def add_edge(self, edge: CurriculumEdge) -> None:
        if edge.source not in self.nodes:
            raise ValueError(f"edge source {edge.source!r} is not a registered node")
        if edge.target not in self.nodes:
            raise ValueError(f"edge target {edge.target!r} is not a registered node")
        if edge.source == edge.target:
            raise ValueError(f"self-loop not allowed: {edge.source!r}")
        # Idempotent re-add.
        for existing in self.edges:
            if (
                existing.source == edge.source
                and existing.target == edge.target
                and existing.relation == edge.relation
            ):
                return
        # Cycle check before commit.
        candidate_edges = self.edges + [edge]
        if _has_cycle(self.nodes.keys(), candidate_edges):
            raise ValueError(
                f"adding edge {edge.source} -> {edge.target} would create a cycle"
            )
        self.edges.append(edge)

    def update_materialization(
        self,
        node_id: str,
        *,
        reason: str | None,
        status: str,
    ) -> None:
        if node_id not in self.nodes:
            raise KeyError(f"node {node_id!r} not in graph")
        n = self.nodes[node_id]
        self.nodes[node_id] = CurriculumNode(
            id=n.id,
            branch=n.branch,
            book_id=n.book_id,
            chapter=n.chapter,
            section=n.section,
            subsection=n.subsection,
            title=n.title,
            materialization_reason=reason,
            materialization_status=status,
            layer=n.layer,
        )

    # ------------------------------------------------------------------
    # Queries.
    # ------------------------------------------------------------------

    def topo_sort(self) -> list[str]:
        """Topologically sort nodes so prerequisites come before dependents.

        Tie-breaks lexicographically on node id for determinism.
        """
        in_degree: dict[str, int] = {nid: 0 for nid in self.nodes}
        adj: dict[str, list[str]] = {nid: [] for nid in self.nodes}
        for e in self.edges:
            adj[e.source].append(e.target)
            in_degree[e.target] += 1
        ready = sorted([nid for nid, d in in_degree.items() if d == 0])
        out: list[str] = []
        while ready:
            cur = ready.pop(0)
            out.append(cur)
            for nxt in sorted(adj[cur]):
                in_degree[nxt] -= 1
                if in_degree[nxt] == 0:
                    ready.append(nxt)
            ready.sort()
        if len(out) != len(self.nodes):
            raise ValueError(
                "graph contains a cycle; topological sort impossible"
            )
        return out

    def prereqs_of(self, node_id: str) -> list[str]:
        """Direct prerequisites of ``node_id`` (sources of incoming edges)."""
        return sorted(e.source for e in self.edges if e.target == node_id)

    def dependents_of(self, node_id: str) -> list[str]:
        """Direct dependents of ``node_id`` (targets of outgoing edges)."""
        return sorted(e.target for e in self.edges if e.source == node_id)

    def render_dot(self) -> str:
        """Render the graph as Graphviz DOT.

        Status colors: candidate=lightgrey, dropped=darkgrey,
        materialized=lightgreen. Code-backed materialized nodes
        (closed_form_determinism) are bold-bordered.
        """
        lines: list[str] = ["digraph curriculum {"]
        lines.append('  rankdir=LR;')
        lines.append('  node [shape=box, fontname="Helvetica", fontsize=10];')
        for node in sorted(self.nodes.values(), key=lambda n: n.id):
            color = _color_for(node)
            penwidth = 2 if node.materialization_reason == "closed_form_determinism" else 1
            label = _dot_label(node)
            lines.append(
                f'  "{node.id}" [label="{label}", style=filled, '
                f'fillcolor="{color}", penwidth={penwidth}];'
            )
        for edge in sorted(self.edges, key=lambda e: (e.source, e.target)):
            style = "solid" if edge.relation == "prerequisite" else "dashed"
            lines.append(
                f'  "{edge.source}" -> "{edge.target}" [style={style}];'
            )
        lines.append("}")
        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Module-level helpers.
# ---------------------------------------------------------------------------


def load_default() -> CurriculumGraph:
    """Load (or initialise) the singleton curriculum graph at ``mvp/curriculum/graph.yaml``."""
    return CurriculumGraph.load(_DEFAULT_GRAPH_PATH)


def _has_cycle(node_ids: Iterable[str], edges: Iterable[CurriculumEdge]) -> bool:
    nodes = list(node_ids)
    adj: dict[str, list[str]] = {n: [] for n in nodes}
    in_degree: dict[str, int] = {n: 0 for n in nodes}
    for e in edges:
        if e.source not in adj or e.target not in adj:
            continue
        adj[e.source].append(e.target)
        in_degree[e.target] += 1
    ready = [n for n, d in in_degree.items() if d == 0]
    visited = 0
    while ready:
        cur = ready.pop()
        visited += 1
        for nxt in adj[cur]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                ready.append(nxt)
    return visited != len(nodes)


def _color_for(node: CurriculumNode) -> str:
    if node.materialization_status == "materialized":
        return "lightgreen"
    if node.materialization_status == "dropped":
        return "darkgrey"
    return "lightgrey"


def _dot_label(node: CurriculumNode) -> str:
    # Truncate long titles for DOT readability; full title is in YAML.
    title = node.title.replace('"', "'")
    if len(title) > 48:
        title = title[:45] + "..."
    short_id = f"{node.book_id} {node.chapter}.{node.section}"
    return f"{short_id}\\n{title}"


__all__ = [
    "CurriculumEdge",
    "CurriculumGraph",
    "CurriculumNode",
    "load_default",
]
