"""compute_nonanswer_hedging_density — de Kok (2024) keyword-filter
hedging-language density applied to a 10-K MD&A.

Paper: de Kok, T. (June 2024). *ChatGPT for Textual Analysis? How to
use Generative LLMs in Accounting Research.* University of Washington
working paper, SSRN 4429658. pdf_sha256
``2650e3e5c853a8ca1d7dae8e14622c64617e295e75b9d4407f0e84bccd79ba4a``.

The paper's Case Study (Section 4) builds a 4-step GPT method for
identifying non-answers in earnings conference calls. Step 1 of the
funnel method (Online Appendix 3, p. ix) is a deterministic
keyword filter built from Gow et al. (2021)'s regex list plus manual
extensions. The keyword list is printed in full in OA 3:
7 trigrams + 23 bigrams + 48 unigrams = 78 tokens.

This skill ports the paper's keyword filter to a DIFFERENT substrate:
the MD&A section of a 10-K. MVP does not ingest earnings-call
transcripts, but the linguistic pattern the keywords detect (hedging,
non-disclosure, forward-looking caveat) generalises to MD&A
narrative. Every non-null call emits
``substrate_port_mdna_vs_earnings_call`` so the port is visible.

The metric. Given MD&A text T:

* Sentence-tokenise T (``[.!?]\\s+`` split, ≥30-char floor).
* For each sentence, match case-insensitively against the 78 keywords
  (unigrams as whole words; bigrams/trigrams as whitespace-normalised
  word sequences after apostrophe strip).
* ``hedging_density = (sentences with ≥1 hit) / total sentences``.
* ``matches_per_1000_words = 1000 × (sentences with ≥1 hit) /
  total_word_count`` (a length-normalised secondary).
* ``hits_by_category = {trigram, bigram, unigram: int}`` trace.

Flags (presentation bands — NOT paper thresholds; see manifest
implementation_decisions[6]): ``low_hedging`` (density < 0.15),
``typical_hedging`` (0.15 ≤ density < 0.35), ``high_hedging``
(density ≥ 0.35), ``indeterminate`` (MD&A not found or <10 valid
sentences).

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
# Paper-derived constants: the 78-token keyword list (de Kok 2024 OA 3).
# ---------------------------------------------------------------------------

# Source: Online Appendix OA 3 p. ix, "Step 1: Keyword filter". Reproduced
# verbatim. The paper renders the bigrams/trigrams with underscore
# separators (``don_t_know``); the actual pattern is a 2- or 3-word
# whitespace-separated sequence. We store them as the real bigram/trigram
# text so the test harness can verify them literally against the paper
# listing.

_TRIGRAMS: tuple[str, ...] = (
    "call it out",
    "at this time",
    "at this point",
    "at this moment",
    "break it out",
    "don t have",
    "don t know",
)

_BIGRAMS: tuple[str, ...] = (
    "not going",
    "will not",
    "won t",
    "by region",
    "get into",
    "that level",
    "are not",
    "don t",
    "do not",
    "give you",
    "break out",
    "splice out",
    "tell you",
    "too early",
    "can t",
    "can not",
    "not ready",
    "right now",
    "no idea",
    "not give",
    "not sure",
    "wouldn t",
    "haven t",
)

_UNIGRAMS: tuple[str, ...] = (
    "cannot",
    "comment",
    "commenting",
    "comments",
    "unable",
    "guidance",
    "guide",
    "guiding",
    "forward",
    "hard",
    "talk",
    "range",
    "disclose",
    "report",
    "privately",
    "forecast",
    "forecasts",
    "forecasting",
    "specific",
    "specifics",
    "detail",
    "details",
    "public",
    "publicly",
    "provide",
    "breakout",
    "statement",
    "statements",
    "update",
    "announcement",
    "announcements",
    "answer",
    "answers",
    "quantify",
    "share",
    "sharing",
    "information",
    "discuss",
    "mention",
    "sorry",
    "apologies",
    "apologize",
    "recall",
    "remember",
    "without",
    "specifically",
    "difficult",
    "officially",
)

# Flag bands (presentation convention, NOT paper thresholds).
_HIGH_HEDGING_FLOOR: float = 0.35
_LOW_HEDGING_CEILING: float = 0.15

# Minimum valid sentences to compute a meaningful density.
_MIN_SENTENCES: int = 10

# Minimum stripped-sentence length (drops list-markers, headers).
_MIN_SENTENCE_CHARS: int = 30

# Pre-iXBRL penalty (matches other paper-derived skills' convention).
_PRE_IXBRL_CONFIDENCE_PENALTY: float = 0.15

# Confidence cap while the substrate-port approximation is active.
_BASE_CONFIDENCE: float = 0.7

# Filings that come from pre-iXBRL SGML manual extractions.
_PRE_IXBRL_CIKS: frozenset[str] = frozenset({"0001024401", "0000723527"})

# Paper pdf sha256 (reproduced from the ingest manifest).
_PAPER_SHA256: str = (
    "2650e3e5c853a8ca1d7dae8e14622c64617e295e75b9d4407f0e84bccd79ba4a"
)


# ---------------------------------------------------------------------------
# Compiled matchers — built once at import time.
# ---------------------------------------------------------------------------


def _build_unigram_matcher(unigrams: tuple[str, ...]) -> re.Pattern[str]:
    # Whole-word match, case-insensitive. ``\b`` word boundary prevents
    # ``specific`` from firing on ``specifications`` and ``recall`` from
    # firing on ``recalled``.
    escaped = [re.escape(u) for u in unigrams]
    pattern = r"\b(?:" + "|".join(escaped) + r")\b"
    return re.compile(pattern, flags=re.IGNORECASE)


_UNIGRAM_MATCHER: re.Pattern[str] = _build_unigram_matcher(_UNIGRAMS)

# Sentence splitter. Simple punctuation-based split; paper doesn't specify
# tokenisation (it operates at the Q&A-pair level).
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

# Apostrophe / curly-quote normaliser. Real MD&A text contains
# "don't"/"can't"; the paper lists the bigrams as "don t" / "can t".
# We strip both straight and curly apostrophes to a space BEFORE running
# the bigram/trigram match so contractions match cleanly.
_APOSTROPHE_RE = re.compile(r"[\u2019\u2018'`]")

# Whitespace collapser.
_WS_RE = re.compile(r"\s+")


class ComputeNonanswerHedgingDensity(Skill):
    id = "compute_nonanswer_hedging_density"
    MANIFEST_PATH = Path(__file__).with_name("manifest.yaml")

    def _execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        cik = str(inputs["cik"])
        fye = str(inputs["fiscal_year_end"])

        ref = find_filing(cik, fye)
        if ref is None:
            raise _UnknownFiling(
                f"no sample filing for cik={cik!r} fiscal_year_end={fye!r}"
            )

        # Delegate MD&A extraction through the registry (imported late to
        # avoid a bootstrap re-entry).
        from mvp.skills.registry import default_registry

        mdna_skill = default_registry().get("extract_mdna")
        mdna_result = mdna_skill.run({"cik": cik, "fiscal_year_end": fye})
        if "error" in mdna_result:
            err = mdna_result["error"]
            raise _SubSkillFailed(
                (
                    f"extract_mdna failed for cik={cik!r} fye={fye!r}: "
                    f"{err.get('error_code')}: {err.get('human_message')}"
                )
            )

        section_text = mdna_result.get("section_text")
        is_pre_ixbrl = cik in _PRE_IXBRL_CIKS
        filing_id = f"{ref.cik}/{ref.accession}"

        if not isinstance(section_text, str) or not section_text.strip():
            return _indeterminate_output(
                warnings=[
                    "mdna_section_not_located: extract_mdna returned null for "
                    f"cik={cik} fiscal_year_end={fye}. Cannot compute "
                    "hedging density."
                ],
                filing_id=filing_id,
            )

        sentences = _split_sentences(section_text)
        if len(sentences) < _MIN_SENTENCES:
            return _indeterminate_output(
                warnings=[
                    f"mdna_too_short: only {len(sentences)} valid sentence(s) "
                    f"(≥{_MIN_SENTENCES} required to compute density)."
                ],
                filing_id=filing_id,
            )

        density, hits_by_category, matches_per_1000, total_hits = (
            _hedging_density(sentences, section_text)
        )
        flag = _flag_for(density)

        warnings: list[str] = [
            (
                "substrate_port_mdna_vs_earnings_call: this skill applies de "
                "Kok (2024) OA 3's 78-token non-answer keyword filter to 10-K "
                "MD&A text. The paper's headline dataset is Finnhub earnings-"
                "call Q&A pairs; our MVP corpus does not include transcripts. "
                "MD&A has a different base rate of hedging language (boilerplate "
                "safe-harbor clauses fire the filter regularly). Treat the "
                "density as a textual-hedging screen, not a reproduction of "
                "the paper's 96% classifier accuracy. See manifest "
                "implementation_decisions[0] and "
                "workshop/paper_to_skill/notes/dekok_2024_gllm_nonanswers.md."
            ),
        ]
        if is_pre_ixbrl:
            warnings.append(
                "pre_ixbrl_paragraph_structure: this filing predates iXBRL; "
                "sentence segmentation is less consistent than in modern "
                "iXBRL filings. Confidence is reduced accordingly."
            )

        citation = _build_mdna_citation(filing_id, section_text)
        confidence = _compute_confidence(
            pre_ixbrl=is_pre_ixbrl, indeterminate=False
        )

        return {
            "hedging_density": round(density, 6),
            "flag": flag,
            "sentence_count": len(sentences),
            "hedging_sentence_count": total_hits,
            "components": {
                "matches_per_1000_words": round(matches_per_1000, 4),
                "hits_by_category": hits_by_category,
                "keyword_counts": {
                    "trigrams": len(_TRIGRAMS),
                    "bigrams": len(_BIGRAMS),
                    "unigrams": len(_UNIGRAMS),
                    "total": len(_TRIGRAMS) + len(_BIGRAMS) + len(_UNIGRAMS),
                },
            },
            "citations": [citation.model_dump(mode="json")],
            "confidence": confidence,
            "warnings": warnings,
            "provenance": {
                "paper_pdf_sha256": _PAPER_SHA256,
                "cur_filing_id": filing_id,
                "high_hedging_floor": _HIGH_HEDGING_FLOOR,
                "low_hedging_ceiling": _LOW_HEDGING_CEILING,
                "keyword_source": (
                    "de Kok (2024) Online Appendix OA 3 p. ix, Step 1: "
                    "Keyword filter"
                ),
            },
        }


# ---------------------------------------------------------------------------
# Sentence splitting + keyword matching.
# ---------------------------------------------------------------------------


def _split_sentences(text: str) -> list[str]:
    """Split ``text`` into sentences on ``[.!?]`` + whitespace.

    Drops fragments shorter than :data:`_MIN_SENTENCE_CHARS` so list
    markers ("1.", "(a)") and section headers don't inflate the
    denominator. Whitespace is left intact inside sentences for
    downstream word counting; apostrophe normalisation happens at
    match time.
    """
    # Replace newlines with spaces first — MD&A is multi-paragraph, but
    # sentences that span a line break shouldn't be split on the newline.
    flat = text.replace("\n", " ")
    parts = _SENTENCE_SPLIT_RE.split(flat)
    return [p.strip() for p in parts if len(p.strip()) >= _MIN_SENTENCE_CHARS]


def _normalize_for_ngram_match(text: str) -> str:
    """Lowercase, apostrophe-strip, collapse whitespace.

    The paper's bigrams/trigrams use underscore separators in the PDF
    rendering; the actual linguistic tokens are whitespace-separated
    word sequences. Stripping apostrophes lets real-world contractions
    (``don't``, ``can't``) match the paper's ``don t`` / ``can t`` forms
    after normalisation.
    """
    lowered = text.lower()
    # Strip straight ' curly ' `, replace with space so "don't" → "don t".
    without_apos = _APOSTROPHE_RE.sub(" ", lowered)
    return _WS_RE.sub(" ", without_apos).strip()


def _sentence_hits(sentence: str) -> tuple[bool, dict[str, int]]:
    """Return (has_any_hit, hits_by_category) for one sentence.

    ``hits_by_category`` keys: ``trigrams``, ``bigrams``, ``unigrams``.
    A sentence can hit multiple categories; each hit is counted once
    per category per sentence (a sentence with two unigram matches
    counts as 1 unigram-hit for this sentence — we measure sentence-
    level firing, not token-level frequency).
    """
    hits = {"trigrams": 0, "bigrams": 0, "unigrams": 0}
    normalized = _normalize_for_ngram_match(sentence)

    # Trigram/bigram: whitespace-normalised substring match on normalized
    # sentence. Each category flags once per sentence.
    for tri in _TRIGRAMS:
        if tri in normalized:
            hits["trigrams"] = 1
            break
    for bi in _BIGRAMS:
        if bi in normalized:
            hits["bigrams"] = 1
            break

    # Unigram: whole-word match using the compiled regex. Runs against the
    # apostrophe-stripped form so "can't" → "can t" tokens don't split a
    # unigram like "cannot" incorrectly (they don't overlap, but the
    # normalisation is consistent with the bigram/trigram path).
    if _UNIGRAM_MATCHER.search(normalized):
        hits["unigrams"] = 1

    has_any = hits["trigrams"] + hits["bigrams"] + hits["unigrams"] > 0
    return has_any, hits


def _hedging_density(
    sentences: list[str], full_text: str
) -> tuple[float, dict[str, int], float, int]:
    """Compute hedging density, category trace, words-normalised rate,
    and total-hit count for a list of sentences.

    Returns a 4-tuple ``(density, hits_by_category, matches_per_1000_words,
    total_hits)``. ``density`` is the proportion of sentences that fired
    the filter; ``hits_by_category`` is the total count of firing
    sentences broken down by the earliest category that fired (a
    sentence that fires on both a unigram and a bigram contributes 1 to
    each category's count). ``matches_per_1000_words`` normalises by
    the full-text word count. ``total_hits`` is the count of
    hedging-flagged sentences.
    """
    total_hits = 0
    hits_by_category = {"trigrams": 0, "bigrams": 0, "unigrams": 0}
    for s in sentences:
        has_any, cats = _sentence_hits(s)
        if has_any:
            total_hits += 1
        for k in ("trigrams", "bigrams", "unigrams"):
            hits_by_category[k] += cats[k]

    density = total_hits / len(sentences)

    # Word-count normalisation uses the full post-strip text (not the
    # dropped fragments).
    word_count = len(full_text.split())
    if word_count == 0:
        matches_per_1000 = 0.0
    else:
        matches_per_1000 = 1000.0 * total_hits / word_count

    return density, hits_by_category, matches_per_1000, total_hits


def _flag_for(density: float) -> str:
    """Map a density in [0, 1] to the 3-band flag."""
    if density >= _HIGH_HEDGING_FLOOR:
        return "high_hedging"
    if density >= _LOW_HEDGING_CEILING:
        return "typical_hedging"
    return "low_hedging"


# ---------------------------------------------------------------------------
# Citation + confidence + indeterminate shape.
# ---------------------------------------------------------------------------


def _build_mdna_citation(filing_id: str, section_text: str) -> Citation:
    """Build one Citation pointing at the MD&A section."""
    return Citation(
        doc_id=filing_id,
        statement_role=None,
        locator=build_locator(filing_id, "mdna", "item_7"),
        excerpt_hash=hash_excerpt(section_text),
        value=None,
        retrieved_at=datetime.now(timezone.utc),
    )


def _compute_confidence(*, pre_ixbrl: bool, indeterminate: bool) -> float:
    """Confidence = base (0.7, substrate-port cap), minus pre-iXBRL
    penalty, zero on indeterminate."""
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
    filing_id: str,
) -> dict[str, Any]:
    """Shape for MD&A-missing / MD&A-too-short."""
    return {
        "hedging_density": None,
        "flag": "indeterminate",
        "sentence_count": 0,
        "hedging_sentence_count": 0,
        "components": {
            "matches_per_1000_words": None,
            "hits_by_category": {"trigrams": 0, "bigrams": 0, "unigrams": 0},
            "keyword_counts": {
                "trigrams": len(_TRIGRAMS),
                "bigrams": len(_BIGRAMS),
                "unigrams": len(_UNIGRAMS),
                "total": len(_TRIGRAMS) + len(_BIGRAMS) + len(_UNIGRAMS),
            },
        },
        "citations": [],
        "confidence": 0.0,
        "warnings": warnings,
        "provenance": {
            "paper_pdf_sha256": _PAPER_SHA256,
            "cur_filing_id": filing_id,
            "high_hedging_floor": _HIGH_HEDGING_FLOOR,
            "low_hedging_ceiling": _LOW_HEDGING_CEILING,
            "keyword_source": (
                "de Kok (2024) Online Appendix OA 3 p. ix, Step 1: "
                "Keyword filter"
            ),
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


SKILL = ComputeNonanswerHedgingDensity
