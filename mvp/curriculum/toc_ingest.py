"""TOC ingestion — convert a structured TOC YAML into curriculum graph nodes.

Input format (TOC YAML)
-----------------------

.. code-block:: yaml

    book_id: bertsimas_lp
    branch: or
    title: "Introduction to Linear Optimization"
    authors: "Bertsimas, Tsitsiklis"
    license_note: "TOC structure only; no verbatim textbook content."
    chapters:
      - number: 1
        title: "Introduction"
        sections:
          - number: 1
            title: "Linear programming"
            subsections:
              - id: lp_canonical_form
                title: "Linear program canonical form"
                summary: "Sen-authored summary, ≤2 sentences..."
                tags: [conceptual, definitional]
              - id: standard_form_conversion
                title: "Standard form and slack variables"
                summary: "..."
                tags: [computational, closed_form_candidate]

The summary field is the IvorySquare-authored short paraphrase used by
the prereq resolver and the LLM-baseline question generator. Verbatim
textbook content must NOT appear here.

Output
------
Nodes added to the curriculum graph keyed
``foundational/<branch>/<book_id>/ch<NN>__<NN>__<subsection_id>``.
Default prerequisite edges follow textbook ordering: each subsection
depends on the previous subsection within the same section, and the
first subsection of each section depends on the last subsection of the
previous section in the same chapter. Cross-chapter ordering is treated
as a soft prerequisite only when the next chapter starts within the
same book — :mod:`mvp.curriculum.prereqs` adds richer cross-references.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from mvp.curriculum.graph import (
    CurriculumEdge,
    CurriculumGraph,
    CurriculumNode,
    load_default,
)


@dataclass(frozen=True)
class IngestionResult:
    """Summary of one TOC ingestion call."""

    book_id: str
    branch: str
    nodes_added: int
    nodes_skipped: int
    edges_added: int


def ingest_toc(
    toc_path: Path | str,
    *,
    graph: CurriculumGraph | None = None,
    save: bool = True,
) -> IngestionResult:
    """Parse ``toc_path`` and add nodes + default ordering edges to ``graph``.

    Parameters
    ----------
    toc_path:
        Path to the TOC YAML file.
    graph:
        Optional graph instance to mutate. Defaults to the singleton
        graph at ``mvp/curriculum/graph.yaml``.
    save:
        Whether to persist the graph after ingestion. Defaults to
        ``True``; set ``False`` for tests that want to inspect an
        in-memory graph without writing to disk.

    Returns
    -------
    :class:`IngestionResult` summarising what was added.
    """
    p = Path(toc_path)
    if not p.is_file():
        raise FileNotFoundError(f"TOC YAML not found at {p}")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(
            f"TOC YAML at {p} must be a mapping, got {type(raw).__name__}"
        )

    book_id = _required_string(raw, "book_id", p)
    branch = _required_string(raw, "branch", p)
    chapters = raw.get("chapters")
    if not isinstance(chapters, list) or not chapters:
        raise ValueError(f"TOC YAML at {p} must declare a non-empty chapters list")

    if graph is None:
        graph = load_default()

    nodes_added = 0
    nodes_skipped = 0
    edges_added = 0
    last_added: str | None = None  # for prerequisite chaining
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch_num = int(ch.get("number", 0))
        sections = ch.get("sections") or []
        if not isinstance(sections, list):
            continue
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            sec_num = int(sec.get("number", 0))
            subsections = sec.get("subsections") or []
            if not isinstance(subsections, list):
                continue
            for sub in subsections:
                if not isinstance(sub, dict):
                    continue
                sub_id_raw = str(sub.get("id", "")).strip()
                title = str(sub.get("title", "")).strip()
                if not sub_id_raw or not title:
                    nodes_skipped += 1
                    continue
                node_id = _build_node_id(branch, book_id, ch_num, sec_num, sub_id_raw)
                node = CurriculumNode(
                    id=node_id,
                    branch=branch,
                    book_id=book_id,
                    chapter=ch_num,
                    section=sec_num,
                    subsection=sub_id_raw,
                    title=title,
                )
                pre_count = len(graph.nodes)
                try:
                    graph.add_node(node)
                except ValueError:
                    nodes_skipped += 1
                    continue
                if len(graph.nodes) > pre_count:
                    nodes_added += 1
                if last_added is not None and last_added != node_id:
                    pre_edges = len(graph.edges)
                    try:
                        graph.add_edge(
                            CurriculumEdge(
                                source=last_added,
                                target=node_id,
                                relation="prerequisite",
                                reason="textbook_ordering",
                            )
                        )
                    except ValueError:
                        # Cycle or duplicate — skip silently; prereqs.py handles
                        # cross-references that produce the same edge.
                        pass
                    if len(graph.edges) > pre_edges:
                        edges_added += 1
                last_added = node_id

    if save:
        graph.save()
    return IngestionResult(
        book_id=book_id,
        branch=branch,
        nodes_added=nodes_added,
        nodes_skipped=nodes_skipped,
        edges_added=edges_added,
    )


def _build_node_id(
    branch: str, book_id: str, chapter: int, section: int, subsection: str
) -> str:
    return (
        f"foundational/{branch}/{book_id}/"
        f"ch{chapter:02d}__{section:02d}__{subsection}"
    )


def _required_string(d: dict[str, Any], key: str, src: Path) -> str:
    val = d.get(key)
    if not isinstance(val, str) or not val.strip():
        raise ValueError(
            f"TOC YAML at {src} missing required string field {key!r}"
        )
    return val.strip()


__all__ = ["IngestionResult", "ingest_toc"]
