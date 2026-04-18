"""Schema tests for the mdna_upfrontedness_components.yaml rule template.

This template has a different shape from the M-score / Z-score
templates:

- It has ONE component (``upfrontedness_score``), not 8 or 5.
- Its partition is a mix of numeric conditions (e.g. ``value >= 0.5283``)
  and a non-numeric sentinel (``value is null``), because the skill's
  output includes ``score=null`` as a legitimate indeterminate path.
- It does not consume canonical line items from
  :mod:`mvp.standardize.mappings` — its only input is the MD&A text
  from the ``extract_mdna`` skill.

The parametrised tests in ``test_rule_template_schema.py`` are scoped
to the two MVP templates and do not apply here; this module asserts the
upfrontedness template's own contract.
"""

from __future__ import annotations

from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_PATH = (
    PROJECT_ROOT / "rules" / "templates" / "mdna_upfrontedness_components.yaml"
)


def _load() -> dict:
    return yaml.safe_load(TEMPLATE_PATH.read_text(encoding="utf-8"))


def test_upfrontedness_template_loads_and_has_expected_shape() -> None:
    data = _load()
    assert data["template_version"] == "0.1.0"
    assert "Kim" in data["paper"]
    assert data["paper_pdf_sha256"] == (
        "0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5"
    )
    assert len(data["components"]) == 1
    comp = data["components"][0]
    assert comp["component"] == "upfrontedness_score"


def test_upfrontedness_template_has_four_bands_covering_null_case() -> None:
    """The template's four interpretation_rules cover the three paper
    quartile bands plus a dedicated indeterminate (null) case."""
    data = _load()
    rules = data["components"][0]["interpretation_rules"]
    assert len(rules) == 4
    conditions = [r["condition"] for r in rules]
    # The four conditions we expect, in some order.
    assert any(c.startswith("value >= 0.5283") for c in conditions), (
        "missing forthcoming band (value >= 0.5283)"
    )
    assert any("0.5012" in c and "0.5283" in c for c in conditions), (
        "missing typical band (0.5012 <= value < 0.5283)"
    )
    assert any(c == "value < 0.5012" for c in conditions), (
        "missing obfuscating_likely band (value < 0.5012)"
    )
    assert any("null" in c for c in conditions), (
        "missing indeterminate (null) case"
    )


def test_upfrontedness_template_interpretations_are_substantive() -> None:
    data = _load()
    rules = data["components"][0]["interpretation_rules"]
    for rule in rules:
        text = " ".join(rule.get("interpretation", "").split()).strip()
        assert len(text) >= 80, (
            f"rule condition={rule['condition']!r} interpretation is too short "
            f"({len(text)} chars)"
        )


def test_upfrontedness_template_nontrivial_severities_have_followups() -> None:
    data = _load()
    rules = data["components"][0]["interpretation_rules"]
    for rule in rules:
        if rule["severity"] in {"medium", "high", "critical"}:
            qs = rule.get("follow_up_questions") or []
            assert len(qs) >= 2, (
                f"rule condition={rule['condition']!r} severity={rule['severity']} "
                f"has {len(qs)} follow-up questions; contract requires ≥2."
            )


def test_upfrontedness_template_severity_vocabulary() -> None:
    data = _load()
    allowed = {"low", "medium", "high", "critical", "none"}
    rules = data["components"][0]["interpretation_rules"]
    for rule in rules:
        assert rule["severity"] in allowed, (
            f"unknown severity {rule['severity']!r} on rule "
            f"condition={rule['condition']!r}"
        )


def test_upfrontedness_numeric_conditions_partition_zero_to_one() -> None:
    """The three numeric bands (forthcoming / typical / obfuscating_likely)
    must partition [0, 1] with no gap and no overlap. The null-case band
    is excluded from the numeric sweep."""
    data = _load()
    rules = data["components"][0]["interpretation_rules"]
    numeric_conditions = [
        r["condition"] for r in rules if "null" not in r["condition"]
    ]
    assert len(numeric_conditions) == 3
    sweep = [i * 0.001 for i in range(1001)]  # 0.000, 0.001, ..., 1.000
    for v in sweep:
        matches = [
            c
            for c in numeric_conditions
            if bool(eval(c, {"__builtins__": {}}, {"value": v}))
        ]
        assert len(matches) == 1, (
            f"at value={v:.3f} matched {len(matches)} rules ({matches}); "
            f"expected exactly one"
        )


def test_upfrontedness_bands_block_has_paper_quartiles() -> None:
    data = _load()
    bands = data["upfrontedness_bands"]
    assert bands["mean"] == 0.5161
    assert bands["standard_deviation"] == 0.0243
    assert bands["p25"] == 0.5012
    assert bands["p50"] == 0.5143
    assert bands["p75"] == 0.5283
    assert bands["forthcoming_floor"] == 0.5283
    assert bands["obfuscating_likely_ceiling"] == 0.5012
    assert "N=66,757" in bands["paper_source"]
