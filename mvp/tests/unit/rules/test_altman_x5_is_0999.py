"""Guard the paper-exact Altman X5 coefficient.

Altman (1968) Equation (I) prints the coefficient on X5 as 0.999. Most
textbooks round to 1.0; the MVP intentionally preserves the paper value.
This test prevents regression to the rounded form.
"""

from __future__ import annotations

from pathlib import Path

import yaml


def test_x5_coefficient_is_exactly_0_999() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "z_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    x5 = next(c for c in data["components"] if c["component"] == "X5")
    assert x5["coefficient"] == 0.999, (
        "Altman (1968) Equation (I) prints X5 coefficient as 0.999. "
        "Textbooks commonly round to 1.0; the MVP preserves 0.999 per BUILD_REFS.md §5.1."
    )
    assert x5["practitioner_coefficient"] == 0.999, (
        "X5's practitioner form uses the same 0.999 because X5 is already in decimal-ratio "
        "form in the paper's original equation (X1-X4 have their coefficients multiplied by "
        "100 for the practitioner form, but X5 does not)."
    )


def test_x5_notes_record_the_rounding_divergence() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "z_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    x5 = next(c for c in data["components"] if c["component"] == "X5")
    assert "1.0" in x5["coefficient_notes"]
    assert "0.999" in x5["coefficient_notes"]


def test_altman_thresholds_match_paper() -> None:
    template = Path(__file__).resolve().parents[3] / "rules" / "templates" / "z_score_components.yaml"
    with template.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    block = data["z_score_thresholds"]
    assert block["distress_threshold"] == 1.81
    assert block["safe_threshold"] == 2.99
    assert block["optimal_midpoint_cutoff"] == 2.675
