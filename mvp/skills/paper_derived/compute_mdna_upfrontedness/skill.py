"""compute_mdna_upfrontedness — Kim, Muhn, Nikolaev & Zhang (2024)
firm-level Information Positioning score over a 10-K MD&A.

Two paper equations are implemented:

* Equation 8 (paragraph position, paper p. 25)::

      Paragraph_Position_k = 1 − rank_k / N

  where ``rank_k ∈ {1..N}`` is the paragraph's 1-indexed position
  and ``N`` is the total paragraph count. This is deterministic and
  paper-exact.

* Equation 9 (firm-level Information Positioning, also called
  "Upfrontedness" in Appendix D)::

      Upfrontedness = Σ_k [ (1 − rank_k/N) × Paragraph_Importance_k ]

  The paper's ``Paragraph_Importance_k`` comes from a released-nowhere
  attention model. We ship a documented proxy: each paragraph's share
  of total MD&A character length — ``length_k / Σ_k length_k``.
  Every call carries ``warning=paragraph_importance_proxy_used`` so
  a caller cannot miss the approximation.

The skill delegates MD&A extraction to ``extract_mdna`` through the
registry (never a direct import — see §5 modularity contract).

No LLM, no stochasticity: identical inputs produce identical outputs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mvp.ingestion.filings_ingest import find_filing
from mvp.lib.citation import Citation, build_locator
from mvp.lib.errors import ErrorCategory, LibError
from mvp.lib.hashing import hash_excerpt
from mvp.skills._base import Skill


# ---------------------------------------------------------------------------
# Paper-derived constants (Kim et al. 2024 Appendix D Panel A).
# ---------------------------------------------------------------------------

# Appendix D Panel A, Upfrontedness distribution over N=66,757 firm-years.
_PAPER_P25: float = 0.5012
_PAPER_P75: float = 0.5283

# The paper's regression sample floor ("drop items with less than five
# paragraphs" in §IV.B; ≥10 paragraphs in the Upfrontedness analysis,
# consistent with §VI.A). We use 10 as the floor below which the
# positional ranking is not a meaningful signal.
_MIN_PARAGRAPHS: int = 10

# Paragraph-filter floor: paragraphs with stripped length under this
# many characters are dropped (headers, list fragments that survive
# extract_mdna's HTML strip).
_MIN_PARAGRAPH_CHARS: int = 20

# Pre-iXBRL (SGML-era) confidence penalty. Matches the −0.15 pattern
# other paper-derived skills use for data-quality flags.
_PRE_IXBRL_CONFIDENCE_PENALTY: float = 0.15

# Base confidence — capped at 0.7 while the importance proxy is in use.
# A future attention-model-backed variant could raise this to 0.9+.
_BASE_CONFIDENCE: float = 0.7

# The set of filing ids that come from pre-iXBRL SGML manual
# extractions. Matches other skills' tagging of the same filings via
# data_quality_flag; we don't have access to that flag for text
# filings (extract_mdna doesn't surface it), so we detect pre-iXBRL
# by filing-id prefix against the known SGML CIKs in the MVP sample.
_PRE_IXBRL_CIKS: frozenset[str] = frozenset({"0001024401", "0000723527"})  # Enron, WorldCom


# Paragraph splitter: two-or-more consecutive newlines. Matches the
# behaviour of extract_mdna, which separates paragraphs with "\n\n".
_PARAGRAPH_SPLIT_RE = re.compile(r"\n{2,}")


class ComputeMdnaUpfrontedness(Skill):
    id = "compute_mdna_upfrontedness"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])

        # Sanity-check that the filing is in the MVP sample (gives us
        # a stable unknown_filing error rather than a cryptic downstream
        # failure when extract_mdna is called with an unregistered cik).
        ref = find_filing(cik, fye)
        if ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fye!r}"
            )

        # Delegate MD&A extraction through the registry. Imported here
        # to avoid a circular import at module import time — registry
        # bootstrap walks skills/ and would re-enter this module.
        from mvp.skills.registry import default_registry

        mdna_skill = default_registry().get("extract_mdna")
        mdna_result = mdna_skill.run({"cik": cik, "fiscal_year_end": fye})
        if "error" in mdna_result:
            # extract_mdna already produced a structured envelope — bubble
            # a matching typed error up so our caller receives a
            # compute_mdna_upfrontedness envelope, not the sub-skill's.
            err = mdna_result["error"]
            raise _SubSkillFailed(
                (
                    f"extract_mdna failed for cik={cik!r} fye={fye!r}: "
                    f"{err.get('error_code')}: {err.get('human_message')}"
                )
            )

        section_text = mdna_result.get("section_text")
        is_pre_ixbrl = cik in _PRE_IXBRL_CIKS

        if not isinstance(section_text, str) or not section_text.strip():
            # extract_mdna returned null — propagate indeterminate.
            return _indeterminate_output(
                warnings=[
                    "mdna_section_not_located: extract_mdna returned null for "
                    f"cik={cik} fiscal_year_end={fye}. Cannot compute Upfrontedness."
                ],
                cur_filing_id=f"{ref.cik}/{ref.accession}",
            )

        paragraphs = _split_paragraphs(section_text)
        if len(paragraphs) < _MIN_PARAGRAPHS:
            return _indeterminate_output(
                warnings=[
                    f"mdna_too_short: only {len(paragraphs)} valid paragraph(s) "
                    f"(≥{_MIN_PARAGRAPHS} required per Kim et al. 2024 §VI.A)."
                ],
                cur_filing_id=f"{ref.cik}/{ref.accession}",
            )

        score, diagnostics = _upfrontedness(paragraphs)
        flag = _flag_for(score)

        warnings: list[str] = [
            "paragraph_importance_proxy_used: this skill ships a length-share proxy "
            "for the paper's attention-model-derived paragraph_importance weighting. "
            "The score preserves the paper's economic signal (long paragraphs at "
            "the front → higher score) but is not equivalent to the model-derived "
            "metric. See manifest implementation_decisions[0] and "
            "workshop/paper_to_skill/notes/fundamentals_text.md §f.",
        ]
        if is_pre_ixbrl:
            warnings.append(
                "pre_ixbrl_paragraph_structure: this filing predates iXBRL; "
                "paragraph breaks are less consistent than in modern iXBRL filings. "
                "Confidence is reduced accordingly."
            )

        filing_id = f"{ref.cik}/{ref.accession}"
        citation = _build_mdna_citation(filing_id, section_text)

        confidence = _compute_confidence(pre_ixbrl=is_pre_ixbrl, indeterminate=False)

        return {
            "upfrontedness_score": round(score, 6),
            "flag": flag,
            "paragraph_count": diagnostics["paragraph_count"],
            "components": {
                "mean_paragraph_position": round(
                    diagnostics["mean_paragraph_position"], 6
                ),
                "total_characters": diagnostics["total_characters"],
                "longest_paragraph_position_score": round(
                    diagnostics["longest_paragraph_position_score"], 6
                ),
                "longest_paragraph_index": diagnostics["longest_paragraph_index"],
            },
            "citations": [citation.model_dump(mode="json")],
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "paper_pdf_sha256": (
                    "0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5"
                ),
                "cur_filing_id": filing_id,
                "paper_p25": _PAPER_P25,
                "paper_p75": _PAPER_P75,
                "importance_weighting": "paragraph_length_share_proxy",
            },
        }


# ---------------------------------------------------------------------------
# Paragraph splitting + core arithmetic.
# ---------------------------------------------------------------------------


def _split_paragraphs(section_text: str) -> list[str]:
    """Split MD&A text on blank-line separators and filter short fragments.

    Paragraphs are the pieces of ``section_text`` between two-or-more
    consecutive newlines. Pieces whose ``strip()``'d length is below
    :data:`_MIN_PARAGRAPH_CHARS` are dropped — these are
    typically headers ("Item 7.", "(a)"), bare list markers, or
    whitespace-only survivors of the HTML strip.

    The returned list preserves document order; the first element is
    the first valid paragraph in MD&A.
    """
    parts = _PARAGRAPH_SPLIT_RE.split(section_text)
    return [p.strip() for p in parts if len(p.strip()) >= _MIN_PARAGRAPH_CHARS]


def _upfrontedness(
    paragraphs: list[str],
) -> tuple[float, dict[str, Any]]:
    """Compute Kim et al. (2024) Equation 9 Upfrontedness score.

    ``paragraphs`` must be non-empty and already filtered for the minimum
    paragraph-length floor; caller's responsibility.

    Returns ``(score, diagnostics)`` where diagnostics packages the
    ``components`` block the manifest advertises.
    """
    n = len(paragraphs)
    lengths = [len(p) for p in paragraphs]
    total_length = sum(lengths)
    if total_length == 0:
        # Every paragraph had length zero after stripping — the splitter
        # should have filtered these out, but the guard keeps the
        # division safe.
        raise ValueError("all MD&A paragraphs are empty after stripping")

    # Equation 8: position_score_k = 1 − rank_k / N, where rank is
    # 1-indexed. For k=1 (first paragraph), score = 1 − 1/N = (N-1)/N.
    # For k=N (last paragraph), score = 1 − N/N = 0.
    position_scores = [1.0 - (k + 1) / n for k in range(n)]

    # Equation 9 with length-share proxy for paragraph importance.
    importance_weights = [length / total_length for length in lengths]
    score = sum(
        position_scores[k] * importance_weights[k] for k in range(n)
    )

    mean_position = sum(position_scores) / n

    # Longest paragraph — ties go to the earliest occurrence.
    longest_idx = 0
    longest_len = lengths[0]
    for k in range(1, n):
        if lengths[k] > longest_len:
            longest_len = lengths[k]
            longest_idx = k

    diagnostics = {
        "paragraph_count": n,
        "mean_paragraph_position": mean_position,
        "total_characters": total_length,
        "longest_paragraph_position_score": position_scores[longest_idx],
        "longest_paragraph_index": longest_idx + 1,  # 1-indexed for report
    }
    return score, diagnostics


def _flag_for(score: float) -> str:
    """Map a score to the paper-Appendix-D quartile flag.

    ``forthcoming`` when score ≥ P75; ``typical`` when P25 ≤ score < P75;
    ``obfuscating_likely`` when score < P25.
    """
    if score >= _PAPER_P75:
        return "forthcoming"
    if score >= _PAPER_P25:
        return "typical"
    return "obfuscating_likely"


# ---------------------------------------------------------------------------
# Citation + confidence.
# ---------------------------------------------------------------------------


def _build_mdna_citation(filing_id: str, section_text: str) -> Citation:
    """Build one Citation pointing at the MD&A section.

    Locator matches extract_mdna's own locator shape (we cite the same
    passage extract_mdna was sourced from), so the citation resolves
    against the same doc-store passage.
    """
    return Citation(
        doc_id=filing_id,
        statement_role=None,
        locator=build_locator(filing_id, "mdna", "item_7"),
        excerpt_hash=hash_excerpt(section_text),
        value=None,
        retrieved_at=datetime.now(timezone.utc),
    )


def _compute_confidence(*, pre_ixbrl: bool, indeterminate: bool) -> float:
    """Compute the skill's confidence score.

    Starts at :data:`_BASE_CONFIDENCE` (0.7, capped while the importance
    proxy is active), reduced by :data:`_PRE_IXBRL_CONFIDENCE_PENALTY`
    for pre-iXBRL filings, zeroed when the result is indeterminate.
    """
    if indeterminate:
        return 0.0
    c = _BASE_CONFIDENCE
    if pre_ixbrl:
        c -= _PRE_IXBRL_CONFIDENCE_PENALTY
    if c < 0.0:
        c = 0.0
    if c > 1.0:
        c = 1.0
    return round(c, 4)


def _indeterminate_output(
    *,
    warnings: list[str],
    cur_filing_id: str,
) -> dict[str, Any]:
    """Return the skill's indeterminate-output dict.

    Used in two places: MD&A section not located, and MD&A too short.
    Both produce the same shape — score=null, flag=indeterminate,
    zero components, empty citations, zero confidence, the warning
    enumerating the gap.
    """
    return {
        "upfrontedness_score": None,
        "flag": "indeterminate",
        "paragraph_count": 0,
        "components": {
            "mean_paragraph_position": None,
            "total_characters": None,
            "longest_paragraph_position_score": None,
            "longest_paragraph_index": None,
        },
        "citations": [],
        "confidence": 0.0,
        "warnings": warnings,
        "provenance": {
            "paper_pdf_sha256": (
                "0444ce3fa30dedf450d642fb81f6665a38f312c94584037886cec69e37d64de5"
            ),
            "cur_filing_id": cur_filing_id,
            "paper_p25": _PAPER_P25,
            "paper_p75": _PAPER_P75,
            "importance_weighting": "paragraph_length_share_proxy",
        },
    }


# ---------------------------------------------------------------------------
# Typed errors.
# ---------------------------------------------------------------------------


class _UnknownFiling(LibError):
    error_code = "unknown_filing"
    error_category = ErrorCategory.INPUT_VALIDATION
    retry_safe = False


class _SubSkillFailed(LibError):
    error_code = "sub_skill_failed"
    error_category = ErrorCategory.INTERNAL
    retry_safe = False


SKILL = ComputeMdnaUpfrontedness
