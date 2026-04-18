"""Guard the paper-faithful Beneish threshold.

Beneish (1999) Table 5 / §"The Model as a Classification Tool" reports
the threshold as -1.78 at the 20:1-30:1 error-cost ratio. The -2.22
value sometimes seen in tertiary sources (and cited in the project's
original scope doc) comes from Beneish, Lee & Nichols (2013), not the
1999 paper. This test prevents regression to -2.22.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_m_score_threshold_equals_neg_178() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "m_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    assert data["m_score_threshold"]["value"] == -1.78, (
        "Beneish (1999) threshold must be -1.78 (paper p. 16, §'The Model as a "
        "Classification Tool'). The -2.22 figure is from Beneish et al. (2013) — a "
        "later paper. See BUILD_REFS.md §4.2 for the correction history."
    )


def test_m_score_threshold_notes_document_the_2013_divergence() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "m_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    notes = data["m_score_threshold"]["notes"]
    assert "-2.22" in notes
    assert "2013" in notes


def test_m_score_flag_logic_uses_178() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "m_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    flag_logic = data["m_score_threshold"]["flag_logic"]
    joined = " ".join(flag_logic)
    assert "-1.78" in joined
    assert "-2.22" not in joined
