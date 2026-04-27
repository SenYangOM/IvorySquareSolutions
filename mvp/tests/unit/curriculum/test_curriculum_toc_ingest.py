"""Unit tests for ``mvp.curriculum.toc_ingest``."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from mvp.curriculum.graph import CurriculumGraph
from mvp.curriculum.toc_ingest import ingest_toc


_TOY_TOC = {
    "book_id": "tinybook",
    "branch": "or",
    "title": "Tiny Book",
    "chapters": [
        {
            "number": 1,
            "title": "Intro",
            "sections": [
                {
                    "number": 1,
                    "title": "Basics",
                    "subsections": [
                        {"id": "concept_a", "title": "Concept A", "summary": "..."},
                        {"id": "concept_b", "title": "Concept B", "summary": "..."},
                    ],
                },
                {
                    "number": 2,
                    "title": "More basics",
                    "subsections": [
                        {"id": "concept_c", "title": "Concept C", "summary": "..."},
                    ],
                },
            ],
        }
    ],
}


def _write_toc(path: Path, payload: dict) -> Path:
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")
    return path


def test_ingest_adds_nodes_and_default_edges(tmp_path: Path) -> None:
    toc_path = _write_toc(tmp_path / "tinybook.yaml", _TOY_TOC)
    graph = CurriculumGraph(path=tmp_path / "graph.yaml")
    result = ingest_toc(toc_path, graph=graph, save=False)
    assert result.book_id == "tinybook"
    assert result.branch == "or"
    assert result.nodes_added == 3
    # Default edges chain in textbook order: A -> B -> C.
    assert result.edges_added == 2
    ids = sorted(graph.nodes)
    assert ids == [
        "foundational/or/tinybook/ch01__01__concept_a",
        "foundational/or/tinybook/ch01__01__concept_b",
        "foundational/or/tinybook/ch01__02__concept_c",
    ]


def test_ingest_idempotent(tmp_path: Path) -> None:
    toc_path = _write_toc(tmp_path / "tinybook.yaml", _TOY_TOC)
    graph = CurriculumGraph(path=tmp_path / "graph.yaml")
    ingest_toc(toc_path, graph=graph, save=False)
    second = ingest_toc(toc_path, graph=graph, save=False)
    assert second.nodes_added == 0  # no new nodes


def test_ingest_rejects_missing_required_field(tmp_path: Path) -> None:
    bad = dict(_TOY_TOC)
    bad.pop("book_id")
    toc_path = _write_toc(tmp_path / "bad.yaml", bad)
    graph = CurriculumGraph(path=tmp_path / "graph.yaml")
    with pytest.raises(ValueError):
        ingest_toc(toc_path, graph=graph, save=False)


def test_ingest_skips_malformed_subsection(tmp_path: Path) -> None:
    payload = {
        "book_id": "tinybook",
        "branch": "or",
        "chapters": [
            {
                "number": 1,
                "sections": [
                    {
                        "number": 1,
                        "subsections": [
                            {"id": "good", "title": "Good"},
                            {"id": "", "title": "Bad"},  # empty id
                            {"title": "Missing id"},
                        ],
                    }
                ],
            }
        ],
    }
    toc_path = _write_toc(tmp_path / "x.yaml", payload)
    graph = CurriculumGraph(path=tmp_path / "g.yaml")
    result = ingest_toc(toc_path, graph=graph, save=False)
    assert result.nodes_added == 1
    assert result.nodes_skipped == 2
