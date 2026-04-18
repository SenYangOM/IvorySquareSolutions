"""Schema tests for all four YAML-based Phase 3 deliverables.

Enforces the §8 negative gate from `success_criteria.md`:
  "Either rule template file is empty, mostly placeholders, or written
  in a way an accounting expert wouldn't recognize as their kind of
  artifact."

Specifically, for each rule template this module asserts:
- Non-empty interpretation string (>=30 chars) for every rule.
- Non-empty follow-up question list for severity >= medium.
- Condition partitions that leave no gap over a reasonable value range.
- Every canonical line item cited is one of the 16 canonical names from
  mvp/standardize/mappings.py.
- All four persona YAMLs load and validate.
- The ontology YAML loads and has the required top-level keys.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from mvp.agents.persona_runtime import load_persona
from mvp.standardize.mappings import CONCEPT_MAPPINGS


PROJECT_ROOT = Path(__file__).resolve().parents[3]
RULES_DIR = PROJECT_ROOT / "rules"
TEMPLATES_DIR = RULES_DIR / "templates"


SEVERITY_VALUES = {"low", "medium", "high", "critical"}
CANONICAL_LINE_ITEMS = set(CONCEPT_MAPPINGS.keys())


# ---------------------------------------------------------------------------
# Helpers — loading YAMLs
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _evaluate_condition(cond: str, value: float) -> bool:
    """Evaluate a rule's condition string at a specific value.

    Uses Python's ``eval`` inside a tightly-restricted namespace with
    only ``value`` bound. The rule-authoring guide restricts the DSL to
    comparison and logical operators over numeric literals, so this is
    safe and faithful.
    """
    return bool(eval(cond, {"__builtins__": {}}, {"value": value}))


# ---------------------------------------------------------------------------
# Rule-template structural tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,expected_components",
    [
        ("m_score_components.yaml", {"DSRI", "GMI", "AQI", "SGI", "DEPI", "SGAI", "LVGI", "TATA"}),
        ("z_score_components.yaml", {"X1", "X2", "X3", "X4", "X5"}),
    ],
)
def test_rule_template_has_expected_components(
    filename: str, expected_components: set[str]
) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    assert data["template_version"], "template_version is required"
    assert data["paper"], "paper citation is required"
    names = {c["component"] for c in data["components"]}
    assert names == expected_components, (
        f"{filename} missing components: {expected_components - names}; "
        f"unexpected: {names - expected_components}"
    )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_every_interpretation_is_substantive(filename: str) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    for comp in data["components"]:
        for rule in comp["interpretation_rules"]:
            text = rule.get("interpretation", "")
            stripped = " ".join(text.split()).strip()
            assert len(stripped) >= 30, (
                f"{filename}:{comp['component']} condition={rule['condition']!r} has a "
                f"too-short interpretation ({len(stripped)} chars). Minimum 30."
            )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_severity_is_from_allowed_vocabulary(filename: str) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    for comp in data["components"]:
        for rule in comp["interpretation_rules"]:
            assert rule["severity"] in SEVERITY_VALUES, (
                f"{filename}:{comp['component']} condition={rule['condition']!r} has "
                f"severity {rule['severity']!r} which is not in {SEVERITY_VALUES}"
            )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_medium_or_higher_severity_has_followups(filename: str) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    for comp in data["components"]:
        for rule in comp["interpretation_rules"]:
            if rule["severity"] in {"medium", "high", "critical"}:
                qs = rule.get("follow_up_questions") or []
                assert len(qs) >= 2, (
                    f"{filename}:{comp['component']} condition={rule['condition']!r} "
                    f"has severity {rule['severity']} but only {len(qs)} follow-up "
                    f"questions — contract requires ≥2."
                )
                for q in qs:
                    assert isinstance(q, str) and len(q) >= 10, (
                        f"{filename}:{comp['component']} has a trivial follow-up: {q!r}"
                    )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_conditions_partition_reasonable_range(filename: str) -> None:
    """Every component's conditions cover a 1,001-point sweep over [-10, 10] with
    no gaps (exactly one rule matches at each sample point)."""
    data = _load_yaml(TEMPLATES_DIR / filename)
    sweep = [(-10 + 0.02 * i) for i in range(1001)]
    for comp in data["components"]:
        conditions = [r["condition"] for r in comp["interpretation_rules"]]
        for v in sweep:
            matches = [c for c in conditions if _evaluate_condition(c, v)]
            assert len(matches) == 1, (
                f"{filename}:{comp['component']} at value={v:.3f} matched {len(matches)} "
                f"conditions ({matches}); expected exactly one. Gap or overlap in partition."
            )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_citations_required_use_canonical_names(filename: str) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    # Permit a small set of non-canonical inputs that are handled by the
    # skill engine rather than the standardization layer (notably the
    # exogenous market_value_of_equity for Altman X4 — it comes from the
    # equity_values.yaml fixture, not mappings.py).
    exogenous = {"market_value_of_equity_t", "market_value_of_equity"}
    pattern = re.compile(r"^([a-z_]+)\s*\(period=")
    for comp in data["components"]:
        for rule in comp["interpretation_rules"]:
            for entry in rule.get("citations_required", []) or []:
                m = pattern.match(entry)
                if not m:
                    continue  # non-line-item form (e.g., just 'total_liabilities (period=t)')
                name = m.group(1)
                assert name in CANONICAL_LINE_ITEMS or name in exogenous, (
                    f"{filename}:{comp['component']} condition={rule['condition']!r} "
                    f"cites unknown canonical line item {name!r}. "
                    f"Allowed: {sorted(CANONICAL_LINE_ITEMS)} or exogenous {sorted(exogenous)}."
                )


@pytest.mark.parametrize(
    "filename", ["m_score_components.yaml", "z_score_components.yaml"]
)
def test_canonical_inputs_use_canonical_names(filename: str) -> None:
    data = _load_yaml(TEMPLATES_DIR / filename)
    pattern = re.compile(r"^([a-z_]+)\b")
    exogenous = {"market_value_of_equity_t", "market_value_of_equity"}
    for comp in data["components"]:
        for entry in comp["canonical_inputs"]:
            # Skip commented entries (entries containing '#' are just notes)
            if entry.strip().startswith("#") or "  #" in entry:
                entry = entry.split("  #")[0].strip()
            m = pattern.match(entry)
            if not m:
                continue
            name = m.group(1)
            assert name in CANONICAL_LINE_ITEMS or name in exogenous, (
                f"{filename}:{comp['component']} canonical_inputs entry {entry!r} "
                f"references unknown name {name!r}"
            )


# ---------------------------------------------------------------------------
# Ontology structural test
# ---------------------------------------------------------------------------


def test_ontology_has_required_sections() -> None:
    data = _load_yaml(RULES_DIR / "ontology.yaml")
    assert "ontology_version" in data
    assert "domains" in data and {"earnings_quality", "distress_risk"} <= set(data["domains"])
    assert "sub_concepts" in data and len(data["sub_concepts"]) >= 6
    assert "financial_statement_roles" in data
    roles = data["financial_statement_roles"]
    assert {"income_statement", "balance_sheet", "cash_flow_statement"} <= set(roles)
    # Every canonical line item in mappings.py is named somewhere in the ontology.
    all_names = set()
    for role_block in roles.values():
        for item in role_block["line_items"]:
            all_names.add(item["name"])
    missing = CANONICAL_LINE_ITEMS - all_names
    assert not missing, f"Ontology missing canonical line items: {missing}"
    assert "value_interpretation_severities" in data
    assert set(data["value_interpretation_severities"].keys()) == SEVERITY_VALUES


def test_ontology_sub_concept_descriptions_are_substantive() -> None:
    data = _load_yaml(RULES_DIR / "ontology.yaml")
    for name, block in data["sub_concepts"].items():
        desc = " ".join(block["description"].split())
        assert len(desc) >= 60, (
            f"sub_concept {name!r} description is too short ({len(desc)} chars)"
        )


# ---------------------------------------------------------------------------
# Persona YAMLs — they all load via the runtime's validator
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "persona_id",
    ["accounting_expert", "quant_finance_methodologist", "evaluation_agent", "citation_auditor"],
)
def test_persona_yaml_loads(persona_id: str) -> None:
    persona = load_persona(persona_id)
    assert persona.id == persona_id
    assert persona.model in {"claude-opus-4-7", "claude-sonnet-4-6"}
    assert len(persona.system_prompt) >= 500
    assert len(persona.replacement_note) >= 50


# ---------------------------------------------------------------------------
# Composite threshold blocks
# ---------------------------------------------------------------------------


def test_m_score_threshold_block_present() -> None:
    data = _load_yaml(TEMPLATES_DIR / "m_score_components.yaml")
    block = data["m_score_threshold"]
    assert block["value"] == -1.78
    assert "flag_logic" in block
    assert "coefficient_table" in block
    coeffs = block["coefficient_table"]
    assert coeffs["DSRI"] == 0.920
    assert coeffs["TATA"] == 4.679
    assert coeffs["intercept"] == -4.840


def test_z_score_threshold_block_present() -> None:
    data = _load_yaml(TEMPLATES_DIR / "z_score_components.yaml")
    block = data["z_score_thresholds"]
    assert block["distress_threshold"] == 1.81
    assert block["safe_threshold"] == 2.99
    assert block["optimal_midpoint_cutoff"] == 2.675
    zones = {z["zone"] for z in block["zones"]}
    assert zones == {"distress", "grey_zone", "safe"}
    assert "flag_logic" in block
