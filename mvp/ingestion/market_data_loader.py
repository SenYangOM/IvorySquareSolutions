"""Loader and validator for ``data/market_data/equity_values.yaml``.

This YAML is the Altman Z-Score input fixture for the 5 Phase 1 sample
issuers. It is engineering-owned (per ``mvp_build_goal.md`` §9 and P1) — an
accounting expert would not edit share counts or prices. The loader's job
is to catch typos and mis-keyed numbers **before** they reach the Altman
skill in Phase 4.

The on-disk consistency rule we enforce is:

    |shares_outstanding * share_price_usd − market_value_of_equity_usd|
                     / market_value_of_equity_usd  ≤  0.01

i.e. 1% tolerance. This is a deliberately loose bound — WorldCom's record
is a tracking-stock aggregate where the implied blended price is back-
calculated from a published aggregate MVE — but even there the residual is
<0.1%. Anything outside 1% is almost certainly a typo.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, Field, model_validator

from mvp.lib.errors import IngestionError

_MVP_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_PATH = _MVP_ROOT / "data" / "market_data" / "equity_values.yaml"

_RELATIVE_TOLERANCE = 0.01  # 1%


class EquityValueEntry(BaseModel):
    """A single issuer's fiscal-year-end market value of equity.

    Field names mirror the YAML exactly. Optional flags
    (``market_cap_source``, ``shares_source_flag``) are carried through
    untouched so downstream skills can lower confidence on flagged rows.
    """

    cik: str = Field(pattern=r"^\d{10}$")
    issuer: str
    fiscal_year_end: str  # ISO yyyy-mm-dd
    shares_outstanding: int
    share_price_usd: float
    market_value_of_equity_usd: float
    price_source: str
    shares_source: str
    notes: str = ""
    market_cap_source: str | None = None
    shares_source_flag: str | None = None

    @model_validator(mode="after")
    def _validate_positive(self) -> "EquityValueEntry":
        if self.shares_outstanding <= 0:
            raise ValueError(
                f"shares_outstanding must be positive, got {self.shares_outstanding}"
            )
        if self.share_price_usd <= 0:
            raise ValueError(
                f"share_price_usd must be positive, got {self.share_price_usd}"
            )
        if self.market_value_of_equity_usd <= 0:
            raise ValueError(
                "market_value_of_equity_usd must be positive, got "
                f"{self.market_value_of_equity_usd}"
            )
        return self

    @model_validator(mode="after")
    def _validate_consistency(self) -> "EquityValueEntry":
        implied = self.shares_outstanding * self.share_price_usd
        diff = abs(implied - self.market_value_of_equity_usd)
        rel = diff / self.market_value_of_equity_usd
        if rel > _RELATIVE_TOLERANCE:
            raise ValueError(
                (
                    f"{self.issuer} ({self.fiscal_year_end}): shares * price = "
                    f"{implied:,.2f} but market_value_of_equity_usd = "
                    f"{self.market_value_of_equity_usd:,.2f} (|Δ| / MVE = "
                    f"{rel * 100:.3f}%), exceeds 1% tolerance"
                )
            )
        return self

    @model_validator(mode="after")
    def _validate_fiscal_year_end(self) -> "EquityValueEntry":
        parts = self.fiscal_year_end.split("-")
        if len(parts) != 3 or not all(p.isdigit() for p in parts):
            raise ValueError(
                f"fiscal_year_end must be ISO yyyy-mm-dd, got {self.fiscal_year_end!r}"
            )
        y, m, d = (int(p) for p in parts)
        if not (1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31):
            raise ValueError(
                f"fiscal_year_end components out of range: {self.fiscal_year_end!r}"
            )
        return self


def load_equity_values(path: Path | None = None) -> list[EquityValueEntry]:
    """Load and validate ``equity_values.yaml``.

    Parameters
    ----------
    path:
        Optional path override. Defaults to
        ``mvp/data/market_data/equity_values.yaml``.

    Returns
    -------
    list[EquityValueEntry]
        In document order. Callers who need per-issuer lookup should
        build an index themselves (the list is small, 5 entries at MVP).

    Raises
    ------
    IngestionError
        - ``reason="yaml_not_found"`` if the file is missing.
        - ``reason="yaml_invalid"`` on YAML syntax errors or an unexpected
          root structure.
        - ``reason="entry_validation"`` on any per-entry Pydantic
          validation failure (positive numbers, MVE consistency, date
          format). The original message is surfaced verbatim so an
          engineer sees exactly which row tripped which rule.
        - ``reason="duplicate_cik"`` if two entries share the same
          ``(cik, fiscal_year_end)``.
    """
    target = path if path is not None else _DEFAULT_PATH
    if not target.exists():
        raise IngestionError(
            f"equity_values.yaml not found at {target}",
            reason="yaml_not_found",
            target=str(target),
        )
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise IngestionError(
            f"yaml parse error in {target}: {exc}",
            reason="yaml_invalid",
            target=str(target),
        ) from exc
    if not isinstance(raw, dict):
        raise IngestionError(
            f"{target} root must be a YAML mapping, got {type(raw).__name__}",
            reason="yaml_invalid",
            target=str(target),
        )
    entries_raw = raw.get("entries")
    if not isinstance(entries_raw, list) or not entries_raw:
        raise IngestionError(
            f"{target} must define a non-empty 'entries' list",
            reason="yaml_invalid",
            target=str(target),
        )

    entries: list[EquityValueEntry] = []
    seen: set[tuple[str, str]] = set()
    for idx, item in enumerate(entries_raw):
        if not isinstance(item, dict):
            raise IngestionError(
                f"{target} entry #{idx} is not a mapping",
                reason="yaml_invalid",
                target=str(target),
            )
        try:
            entry = EquityValueEntry(**item)
        except Exception as exc:  # pydantic.ValidationError or nested ValueError
            raise IngestionError(
                f"{target} entry #{idx} failed validation: {exc}",
                reason="entry_validation",
                target=str(target),
            ) from exc

        key = (entry.cik, entry.fiscal_year_end)
        if key in seen:
            raise IngestionError(
                (
                    f"{target} entry #{idx} duplicates "
                    f"(cik={entry.cik}, fiscal_year_end={entry.fiscal_year_end})"
                ),
                reason="duplicate_cik",
                target=str(target),
            )
        seen.add(key)
        entries.append(entry)

    return entries
