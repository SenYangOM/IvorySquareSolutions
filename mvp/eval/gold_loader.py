"""Gold-case loader — reads YAMLs under eval/gold/<skill>/*.yaml.

The eval runner and citation checker both consume :class:`GoldCase`
objects; this module is the single loader. Kept separate from
``runner.py`` so tests can load fixtures without pulling in the full
runner dependency graph.

Gold YAML shape
---------------
See ``mvp/human_layer/gold_authoring_guide.md`` for the authored shape.
The loader accepts both

- the richly-authored Phase 5 shape (``expected.m_score.value`` +
  ``expected.m_score.tolerance`` + ``expected.components.<name>.range``),
  and
- the simpler shape in the guide (``expected.m_score.range`` +
  ``expected.components.<name>.range``),

and normalises to a single :class:`GoldCase`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class ComponentExpectation:
    """Per-component expectation.

    Either ``value`` is set (point value — used for null-matches-null),
    or ``range`` is set (inclusive [min, max] band). ``point_estimate``
    is for human reviewers only; the runner ignores it for pass/fail.
    """

    name: str
    value: float | None
    range: tuple[float, float] | None
    point_estimate: float | None
    rationale: str


@dataclass(frozen=True)
class ScoreExpectation:
    """Expected score — either a value with tolerance, or a (min, max) band."""

    value: float | None
    tolerance: float | None
    range: tuple[float, float] | None
    source_of_truth: str
    rationale: str

    def tolerance_band(self) -> tuple[float, float] | None:
        """Return the effective [min, max] band (``None`` when value is null)."""
        if self.value is None:
            return None
        if self.tolerance is not None:
            return (self.value - self.tolerance, self.value + self.tolerance)
        if self.range is not None:
            return self.range
        return None


@dataclass(frozen=True)
class CitationExpectation:
    min_count: int
    must_resolve: bool
    must_cite: tuple[str, ...]


@dataclass(frozen=True)
class ConfidenceExpectation:
    min: float
    max: float
    rationale: str


@dataclass(frozen=True)
class GoldCase:
    """One gold-standard case parsed from YAML."""

    case_id: str
    skill_id: str
    skill_version: str
    cik: str
    fiscal_year_end: str
    score_expectation: ScoreExpectation
    expected_flag: str
    flag_rationale: str
    components: dict[str, ComponentExpectation]
    citation_expectation: CitationExpectation
    confidence: ConfidenceExpectation
    warnings_must_include: tuple[str, ...]
    known_deviation_explanation: str | None
    source_path: Path
    raw: dict[str, Any] = field(compare=False)

    @property
    def score_key(self) -> str:
        """Output key for the score value.

        Maps ``skill_id`` to the scalar-score field name that gold
        expectations key off. The MVP skills (Beneish, Altman) use
        ``m_score`` / ``z_score`` respectively. Post-MVP additions
        register their own key here as they land.
        """
        return _SCORE_KEYS.get(self.skill_id, "m_score")


def load_gold_cases(gold_root: Path) -> list[GoldCase]:
    """Load every ``*.yaml`` under ``gold_root/<skill_short>/``.

    ``skill_short`` is ``beneish`` or ``altman`` — the immediate
    subdirectory name. Files whose YAML does not include a
    ``skill_id`` line (e.g. README) are skipped silently.
    """
    gold_root = Path(gold_root)
    if not gold_root.is_dir():
        raise FileNotFoundError(f"gold root {gold_root!s} is not a directory")

    out: list[GoldCase] = []
    for sub in sorted(gold_root.iterdir()):
        if not sub.is_dir():
            continue
        for yaml_path in sorted(sub.glob("*.yaml")):
            case = _load_single(yaml_path)
            if case is not None:
                out.append(case)
    return out


def _load_single(path: Path) -> GoldCase | None:
    with path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        return None
    if "skill_id" not in raw or "case_id" not in raw:
        return None

    skill_id = str(raw["skill_id"])
    case_id = str(raw["case_id"])
    skill_version = str(raw.get("skill_version", "0.1.0"))
    inputs = raw.get("inputs") or {}
    cik = str(inputs.get("cik") or raw.get("issuer", {}).get("cik") or "")
    fye = str(
        inputs.get("fiscal_year_end")
        or raw.get("filing", {}).get("fiscal_period_end")
        or ""
    )

    score_key = _SCORE_KEYS.get(skill_id, "m_score")
    expected = raw.get("expected") or {}
    score_raw = expected.get(score_key) or {}
    score_exp = _parse_score_expectation(score_raw)

    flag_raw = expected.get("flag") or {}
    if isinstance(flag_raw, dict):
        expected_flag = str(flag_raw.get("value", ""))
        flag_rationale = str(flag_raw.get("rationale", ""))
    else:
        expected_flag = str(flag_raw)
        flag_rationale = ""

    components_raw = expected.get("components") or {}
    components: dict[str, ComponentExpectation] = {}
    for name, entry in components_raw.items():
        if not isinstance(entry, dict):
            continue
        components[str(name)] = _parse_component(str(name), entry)

    cite_raw = expected.get("citation_expectations") or {}
    citation_exp = CitationExpectation(
        min_count=int(cite_raw.get("min_count", 0)),
        must_resolve=bool(cite_raw.get("must_resolve", True)),
        must_cite=tuple(str(x) for x in cite_raw.get("must_cite") or []),
    )

    conf_raw = expected.get("confidence") or {}
    confidence = ConfidenceExpectation(
        min=float(conf_raw.get("min", 0.0)),
        max=float(conf_raw.get("max", 1.0)),
        rationale=str(conf_raw.get("rationale", "")),
    )

    warnings_must_include = tuple(
        str(x) for x in (expected.get("warnings_must_include") or [])
    )

    kde = raw.get("known_deviation_explanation")
    known_deviation_explanation = (
        str(kde).strip() if kde not in (None, "null", "") else None
    )

    return GoldCase(
        case_id=case_id,
        skill_id=skill_id,
        skill_version=skill_version,
        cik=cik,
        fiscal_year_end=fye,
        score_expectation=score_exp,
        expected_flag=expected_flag,
        flag_rationale=flag_rationale,
        components=components,
        citation_expectation=citation_exp,
        confidence=confidence,
        warnings_must_include=warnings_must_include,
        known_deviation_explanation=known_deviation_explanation,
        source_path=path,
        raw=raw,
    )


def _parse_score_expectation(entry: dict[str, Any]) -> ScoreExpectation:
    raw_value = entry.get("value", _SENTINEL)
    if raw_value is _SENTINEL:
        value = None
    elif raw_value is None:
        value = None
    else:
        value = float(raw_value)

    tol = entry.get("tolerance")
    tolerance = float(tol) if tol is not None else None

    rng_raw = entry.get("range")
    rng: tuple[float, float] | None
    if isinstance(rng_raw, (list, tuple)) and len(rng_raw) == 2:
        rng = (float(rng_raw[0]), float(rng_raw[1]))
    else:
        rng = None

    return ScoreExpectation(
        value=value,
        tolerance=tolerance,
        range=rng,
        source_of_truth=str(entry.get("source_of_truth", "unspecified")),
        rationale=str(entry.get("rationale", "")),
    )


def _parse_component(name: str, entry: dict[str, Any]) -> ComponentExpectation:
    value_raw = entry.get("value", _SENTINEL)
    value: float | None
    if value_raw is _SENTINEL:
        value = None
    elif value_raw is None:
        value = None
    else:
        value = float(value_raw)

    rng_raw = entry.get("range")
    if isinstance(rng_raw, (list, tuple)) and len(rng_raw) == 2:
        rng = (float(rng_raw[0]), float(rng_raw[1]))
    else:
        rng = None

    pe_raw = entry.get("point_estimate")
    point = float(pe_raw) if pe_raw is not None else None

    return ComponentExpectation(
        name=name,
        value=value,
        range=rng,
        point_estimate=point,
        rationale=str(entry.get("rationale", "")),
    )


_SENTINEL = object()


# Maps skill_id → the scalar-score field name in both the gold YAML's
# ``expected.<key>`` block and the skill's output envelope. Adding a new
# scalar-score skill means adding one line here.
_SCORE_KEYS: dict[str, str] = {
    "compute_beneish_m_score": "m_score",
    "compute_altman_z_score": "z_score",
    "compute_mdna_upfrontedness": "upfrontedness_score",
    "compute_context_importance_signals": "context_importance_score",
    "compute_business_complexity_signals": "business_complexity_score",
    "compute_nonanswer_hedging_density": "hedging_density",
    "predict_filing_complexity_from_determinants": "predicted_complexity_level",
}


__all__ = [
    "CitationExpectation",
    "ComponentExpectation",
    "ConfidenceExpectation",
    "GoldCase",
    "ScoreExpectation",
    "load_gold_cases",
]
