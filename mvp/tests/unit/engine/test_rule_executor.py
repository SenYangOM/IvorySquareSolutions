"""Tests for engine.rule_executor.

Covers:
- Band matching (condition parser: ``value > N`` and ``N < value <= N``).
- Null-value short-circuit to ``indeterminate_null`` band.
- Header-line substitution in interpretation text.
- citations_required resolution against canonical_statements.
- build_market_data_citation shape.
"""

from __future__ import annotations

from datetime import date

import pytest
import yaml

from mvp.engine.rule_executor import (
    apply_component_rules,
    build_market_data_citation,
)
from mvp.lib.citation import Citation
from mvp.standardize.statements import build_canonical_statements


RULE_TEMPLATE_M = None
RULE_TEMPLATE_Z = None


def _rule_template_m() -> dict:
    global RULE_TEMPLATE_M
    if RULE_TEMPLATE_M is None:
        from pathlib import Path
        path = Path(__file__).resolve().parents[3] / "rules" / "templates" / "m_score_components.yaml"
        RULE_TEMPLATE_M = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RULE_TEMPLATE_M


def _rule_template_z() -> dict:
    global RULE_TEMPLATE_Z
    if RULE_TEMPLATE_Z is None:
        from pathlib import Path
        path = Path(__file__).resolve().parents[3] / "rules" / "templates" / "z_score_components.yaml"
        RULE_TEMPLATE_Z = yaml.safe_load(path.read_text(encoding="utf-8"))
    return RULE_TEMPLATE_Z


@pytest.mark.requires_live_data
def test_simple_band_high_severity_matches() -> None:
    tpl = _rule_template_m()
    stmts_t = build_canonical_statements("0000320193/0000320193-23-000106")
    stmts_p = build_canonical_statements("0000320193/0000320193-22-000108")
    interp = apply_component_rules(
        rule_template=tpl,
        component_name="DSRI",
        value=2.0,  # way above 1.465
        canonical_statements={"t": stmts_t, "t-1": stmts_p},
        fiscal_period_end=date(2023, 9, 30),
    )
    assert interp.band_matched.severity == "high"
    assert interp.band_matched.condition == "value > 1.465"
    assert interp.value == 2.0
    assert "DSRI = 2.0000 (high)" in interp.interpretation_text


@pytest.mark.requires_live_data
def test_ranged_band_medium() -> None:
    tpl = _rule_template_m()
    stmts_t = build_canonical_statements("0000320193/0000320193-23-000106")
    stmts_p = build_canonical_statements("0000320193/0000320193-22-000108")
    interp = apply_component_rules(
        rule_template=tpl,
        component_name="DSRI",
        value=1.3,
        canonical_statements={"t": stmts_t, "t-1": stmts_p},
        fiscal_period_end=date(2023, 9, 30),
    )
    assert interp.band_matched.severity == "medium"


@pytest.mark.requires_live_data
def test_null_value_short_circuits_to_indeterminate_null() -> None:
    tpl = _rule_template_m()
    stmts_t = build_canonical_statements("0000320193/0000320193-23-000106")
    stmts_p = build_canonical_statements("0000320193/0000320193-22-000108")
    interp = apply_component_rules(
        rule_template=tpl,
        component_name="TATA",
        value=None,
        canonical_statements={"t": stmts_t, "t-1": stmts_p},
        fiscal_period_end=date(2023, 9, 30),
    )
    assert interp.value is None
    assert interp.band_matched.severity == "indeterminate_null"
    assert "TATA = null (indeterminate)" in interp.interpretation_text


def test_unknown_component_raises_key_error() -> None:
    tpl = _rule_template_m()
    with pytest.raises(KeyError):
        apply_component_rules(
            rule_template=tpl,
            component_name="NOT_A_COMPONENT",
            value=1.0,
            canonical_statements={"t": [], "t-1": []},
            fiscal_period_end=date(2023, 9, 30),
        )


def test_build_market_data_citation_shape() -> None:
    c = build_market_data_citation(
        cik="0000320193",
        fiscal_year_end=date(2023, 9, 30),
        fixture_excerpt="test",
        market_value_of_equity=1_000_000_000.0,
    )
    assert isinstance(c, Citation)
    assert c.doc_id == "market_data/equity_values"
    assert "market_data::market_value_of_equity_0000320193_2023-09-30" in c.locator
    assert c.value == 1_000_000_000.0


@pytest.mark.requires_live_data
def test_citations_resolved_for_x1() -> None:
    """X1 citations_required → current_assets + current_liabilities + total_assets for year t."""
    tpl = _rule_template_z()
    stmts = build_canonical_statements("0000320193/0000320193-23-000106")
    interp = apply_component_rules(
        rule_template=tpl,
        component_name="X1",
        value=0.1,
        canonical_statements={"t": stmts},
        fiscal_period_end=date(2023, 9, 30),
    )
    canonical_names = {
        c.locator.split("::")[-1] for c in interp.citations
    }
    assert canonical_names == {"current_assets", "current_liabilities", "total_assets"}
