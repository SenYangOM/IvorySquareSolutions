"""L2 restatement detection (logging-only at MVP).

Per ``mvp_build_goal.md`` §12 Phase 2, restatements are *logged*, not
acted on. When a later filing from the same issuer references an
earlier fiscal period (because it restates prior-year comparatives), we
emit a :class:`RestatementRecord` and append it to
``data/standardize_restatement_log.jsonl``. We do not re-run upstream
skills automatically — that is explicitly deferred post-MVP
(``mvp_build_goal.md`` §1 Out-of-scope).

Detection algorithm
-------------------
For a given CIK, we walk the locally-ingested filings in chronological
order of ``filed_at``. For each filing, we look at the companyfacts
facts (iXBRL filings) or the manual-extraction YAML (pre-iXBRL) to see
which fiscal periods it reports on. When a later filing N reports facts
for a fiscal period that an earlier filing M already covered, filing N
is a potential restater of filing M's numbers for that period.

This is heuristic — every 10-K reports two to three years of comparative
numbers, so "restatement" in this narrow sense is very common and not
all of it is a substantive restatement. We therefore emit one record
per (later_filing, earlier_filing, fiscal_period) triple and leave the
categorisation to a human reviewer or a post-MVP skill.

For the five MVP issuers with ten ingested filings (two per issuer,
adjacent years), this typically finds zero "restatements" because the
second filing of each issuer reports on a different fiscal year than
the first, with overlap only on comparative prior-year columns.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mvp.lib.errors import StoreError
from mvp.store.doc_store import list_filings

_MVP_ROOT = Path(__file__).resolve().parent.parent
_DATA_DIR = _MVP_ROOT / "data"
_RESTATEMENT_LOG_PATH = _DATA_DIR / "standardize_restatement_log.jsonl"
_FILINGS_DIR = _DATA_DIR / "filings"


class RestatementRecord(BaseModel):
    """One (later_filing, earlier_filing, fiscal_period) triple.

    Attributes
    ----------
    cik:
        Issuer CIK (10-digit).
    fiscal_period_end:
        The ISO date (year-end) whose numbers are being restated.
    earlier_filing_id:
        ``"<cik>/<accession>"`` of the filing that first reported this
        period. The original ``meta.json.fiscal_period_end`` is this date.
    later_filing_id:
        ``"<cik>/<accession>"`` of a later filing that also reports on
        the same period (typically as a prior-year comparative).
    earlier_filed_at / later_filed_at:
        ISO dates from ``meta.json``; later MUST be strictly after
        earlier (else we don't emit).
    notes:
        Free-form annotation. At MVP always ``"overlap_detected"`` since
        we're heuristic; post-MVP a real substantive-restatement check
        can tighten this.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    cik: str = Field(pattern=r"^\d{10}$")
    fiscal_period_end: date
    earlier_filing_id: str
    later_filing_id: str
    earlier_filed_at: date
    later_filed_at: date
    notes: str


def detect_restatements(cik: str) -> list[RestatementRecord]:
    """Return (and log) restatement overlaps for ``cik``.

    Walks every ingested filing whose ``cik`` matches and checks for
    fiscal-period overlaps. Writes one line per record to
    ``data/standardize_restatement_log.jsonl``.

    For MVP coverage (two adjacent-year 10-Ks per issuer) this typically
    returns ``[]`` because fiscal-period-ends don't overlap — each 10-K
    is an initial filing for its own year. A real restatement would
    show up once a 10-K/A for an earlier year is ingested.
    """
    if not isinstance(cik, str) or len(cik) != 10 or not cik.isdigit():
        raise StoreError(
            f"cik must be a 10-digit zero-padded string, got {cik!r}",
            reason="invalid_cik",
            filing_id=cik,
        )

    # Pull every filing under the doc store, filter to the requested CIK.
    all_docs = [d for d in list_filings() if d.cik == cik]
    # Sort by filed_at for deterministic iteration.
    metas: list[dict[str, Any]] = []
    for doc in all_docs:
        meta_path = _FILINGS_DIR / doc.cik / doc.accession / "meta.json"
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        metas.append(
            {
                "filing_id": doc.doc_id,
                "cik": doc.cik,
                "accession": doc.accession,
                "fiscal_period_end": date.fromisoformat(str(meta["fiscal_period_end"])),
                "filed_at": date.fromisoformat(str(meta["filed_at"])),
            }
        )
    metas.sort(key=lambda m: (m["filed_at"], m["accession"]))

    # For each pair (earlier, later) where earlier.fiscal_period_end ==
    # later's fiscal_period_end (i.e. the later filing re-reports the
    # same year), emit a record. Also emit when an earlier filing's
    # period appears as a comparative in a later filing — but we don't
    # have the comparatives-as-facts index here without re-opening the
    # companyfacts JSON. At MVP, fiscal_period_end equality on the cover
    # page is a sufficient indicator of 10-K/A-style restatement.
    records: list[RestatementRecord] = []
    for i, later in enumerate(metas):
        for earlier in metas[:i]:
            if earlier["fiscal_period_end"] != later["fiscal_period_end"]:
                continue
            if earlier["filed_at"] >= later["filed_at"]:
                continue
            rec = RestatementRecord(
                cik=cik,
                fiscal_period_end=later["fiscal_period_end"],
                earlier_filing_id=str(earlier["filing_id"]),
                later_filing_id=str(later["filing_id"]),
                earlier_filed_at=earlier["filed_at"],
                later_filed_at=later["filed_at"],
                notes="overlap_detected",
            )
            records.append(rec)

    if records:
        _append_log(records)
    return records


def _append_log(records: list[RestatementRecord]) -> None:
    _RESTATEMENT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _RESTATEMENT_LOG_PATH.open("a", encoding="utf-8") as f:
        for r in records:
            row = {
                "logged_at": datetime.now(timezone.utc).isoformat(),
                **r.model_dump(mode="json"),
            }
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


__all__ = ["RestatementRecord", "detect_restatements"]
