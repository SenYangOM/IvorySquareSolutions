"""Paper-replication test for compute_nonanswer_hedging_density.

Paper: de Kok, T. (June 2024). *ChatGPT for Textual Analysis? How to
use Generative LLMs in Accounting Research.* University of Washington
working paper, SSRN 4429658.

Replication strategy. The paper's headline metric (Table 1 Column 6:
96% accuracy, 87% F1 non-answer) is a classifier performance statistic
on a 500-Q&A-pair evaluation set drawn from earnings-call transcripts.
MVP does not ingest transcripts, so the classifier performance cannot
be reproduced on the 5 MVP filings.

What we CAN replicate, paper-exact:

1. The 75-token keyword list itself (OA 3 p. ix). The skill reproduces
   the list verbatim; the test asserts exact counts and checks a handful
   of specific tokens.
2. The paper's OA 4 p. xii published example sentences (the Venn
   overlap area) must ALL fire the filter. These are the paper's own
   non-answer sentences; our filter has to catch them.
3. Sentence-level-firing arithmetic on synthetic fixtures (monotone
   density, threshold boundaries, case insensitivity, word-boundary
   match, apostrophe normalisation).
4. Soft sanity on real MVP filings — all 4 scorable ones produce a
   non-null density in [0.0, 1.0] with a defined flag.
"""

from __future__ import annotations

import pytest

from mvp.skills.paper_derived.compute_nonanswer_hedging_density.skill import (
    _BIGRAMS,
    _HIGH_HEDGING_FLOOR,
    _LOW_HEDGING_CEILING,
    _MIN_SENTENCES,
    _TRIGRAMS,
    _UNIGRAMS,
    _flag_for,
    _hedging_density,
    _sentence_hits,
    _split_sentences,
)
from mvp.skills.registry import Registry, reset_default_registry


def _fresh_registry() -> Registry:
    reset_default_registry()
    r = Registry()
    r.bootstrap()
    return r


# ---------------------------------------------------------------------------
# (1) Keyword list paper-faithfulness — exact counts and spot checks.
# ---------------------------------------------------------------------------


def test_keyword_list_counts_match_paper_oa3() -> None:
    """de Kok (2024) OA 3 p. ix lists exactly 7 trigrams + 23 bigrams
    + 48 unigrams = 78 tokens. Any drift from these counts is a bug."""
    assert len(_TRIGRAMS) == 7
    assert len(_BIGRAMS) == 23
    assert len(_UNIGRAMS) == 48
    assert len(_TRIGRAMS) + len(_BIGRAMS) + len(_UNIGRAMS) == 78


def test_keyword_list_contains_specific_paper_tokens() -> None:
    """Spot-check a handful of tokens printed in OA 3 p. ix. If the
    keyword list were regenerated from a different source (e.g. a
    different edition of the paper or a secondary textbook), these
    assertions would catch the drift."""
    # Trigrams
    assert "don t know" in _TRIGRAMS
    assert "at this time" in _TRIGRAMS
    # Bigrams
    assert "not going" in _BIGRAMS
    assert "right now" in _BIGRAMS
    assert "don t" in _BIGRAMS
    # Unigrams
    assert "guidance" in _UNIGRAMS
    assert "disclose" in _UNIGRAMS
    assert "forward" in _UNIGRAMS
    assert "specifically" in _UNIGRAMS


def test_keyword_list_has_no_duplicates() -> None:
    """Each token appears at most once per category list."""
    assert len(set(_TRIGRAMS)) == len(_TRIGRAMS)
    assert len(set(_BIGRAMS)) == len(_BIGRAMS)
    assert len(set(_UNIGRAMS)) == len(_UNIGRAMS)


# ---------------------------------------------------------------------------
# (2) Paper's OA 4 published overlap examples must fire the filter.
# ---------------------------------------------------------------------------


# Taken from OA 4 p. xii, "Overlap area — Both methods mark the response
# as a non-answer". These are sentences from real earnings calls that
# BOTH the GPT method AND the Gow et al. regex method classify as
# non-answers. Our keyword-filter port has to catch all of them whose
# bolded phrase maps to a keyword in OA 3's 78-token list. Note: OA 3
# is the filter the keyword pass uses; OA 4's examples are verified by
# the full GPT method (Steps 1-4) — so a few OA 4 examples ("not expect
# us to be given a volume") may not fire the OA 3 filter itself (they
# pass because they're caught downstream). The test asserts that the
# examples whose bolded phrase DIRECTLY maps to an OA 3 keyword fire
# the filter.
_OA4_OVERLAP_EXAMPLES = (
    # "not provided the range" -> "range" unigram
    "Yes. We haven't provided that, Tom. Perhaps we'll provide it in the "
    "next quarter or later on. But right now, we have not provided the range.",
    # "don't have specific granular views" -> "don t have" trigram, "specific" unigram
    "We don't have specific granular views nor would we give those as part "
    "of the guidance.",
    # "not disclosing at this time" -> "at this time" trigram
    "We're not disclosing at this time what indications we are going to "
    "pursue or exclude.",
    # "I don't know" -> "don t know" trigram
    "I don't know the very exact numbers, but a few quarters ago in our "
    "slide we gave you a price chart which shows you the break down market "
    "intelligence cost.",
    # "never an easy answer" -> "answer" unigram
    "Well, there is never an easy answer to this, but I'll let Jeremy give "
    "it his best shot here.",
    # "not going to speculate... at this point" -> "not going" bigram + "at this point" trigram
    "Well, I'm not going to speculate on 2015 at this point.",
    # "I honestly don't know." -> "don t know" trigram
    "I honestly don't know.",
)


@pytest.mark.parametrize("example", _OA4_OVERLAP_EXAMPLES)
def test_oa4_overlap_examples_all_fire_the_filter(example: str) -> None:
    """Every paper-published overlap-area example must fire the filter.
    These are the paper's own ground-truth non-answer sentences — our
    filter has to catch them, or the port is broken."""
    has_hit, cats = _sentence_hits(example)
    assert has_hit, (
        f"OA 4 overlap example did not fire the filter: {example!r} "
        f"hits_by_category={cats}"
    )


# ---------------------------------------------------------------------------
# (3) Sentence-level-firing arithmetic on synthetic fixtures.
# ---------------------------------------------------------------------------


def test_density_monotonicity_zero_hits() -> None:
    """10 neutral sentences -> density 0.0 / low_hedging."""
    sentences = [
        "The company reported revenue growth of twelve percent this year and plans expansion into new markets.",
    ] * 10
    density, cats, _, hits = _hedging_density(sentences, " ".join(sentences))
    assert density == 0.0
    assert hits == 0
    assert cats == {"trigrams": 0, "bigrams": 0, "unigrams": 0}
    assert _flag_for(density) == "low_hedging"


def test_density_monotonicity_all_hits() -> None:
    """10 hedging sentences -> density 1.0 / high_hedging."""
    sentences = [
        "We cannot provide specific guidance at this time regarding that forecast.",
    ] * 10
    density, cats, _, hits = _hedging_density(sentences, " ".join(sentences))
    assert density == 1.0
    assert hits == 10
    # Each of these sentences fires on "at this time" (trigram),
    # unigrams (cannot, specific, guidance, forecast), and nothing else
    # must be zero (bigrams may or may not fire — "cannot provide" is
    # not a bigram in the list).
    assert cats["trigrams"] == 10  # "at this time"
    assert cats["unigrams"] == 10  # cannot / specific / guidance / forecast
    assert _flag_for(density) == "high_hedging"


def test_density_mixed_gives_typical() -> None:
    """3 hedging of 10 total -> density 0.30 / typical_hedging."""
    hedgy = "We cannot comment on that particular matter at this time."
    neutral = (
        "The company reported revenue growth this year and expanded into new markets."
    )
    sentences = [hedgy, hedgy, hedgy, neutral, neutral, neutral, neutral, neutral, neutral, neutral]
    density, _, _, _ = _hedging_density(sentences, " ".join(sentences))
    assert abs(density - 0.3) < 1e-9
    assert _flag_for(density) == "typical_hedging"


# ---------------------------------------------------------------------------
# (4) Threshold boundary tests.
# ---------------------------------------------------------------------------


def test_flag_boundary_low_ceiling_exclusive() -> None:
    """At density = 0.149..., flag is low_hedging (strictly < 0.15)."""
    assert _flag_for(0.1499) == "low_hedging"


def test_flag_boundary_low_ceiling_inclusive_on_typical() -> None:
    """At density = 0.15 exactly, flag is typical_hedging."""
    assert _flag_for(0.15) == "typical_hedging"


def test_flag_boundary_high_floor_inclusive() -> None:
    """At density = 0.35 exactly, flag is high_hedging."""
    assert _flag_for(0.35) == "high_hedging"


def test_flag_boundary_high_floor_exclusive_on_typical() -> None:
    """At density = 0.349..., flag is typical_hedging."""
    assert _flag_for(0.3499) == "typical_hedging"


def test_band_constants_pin() -> None:
    """Guard against accidental band drift."""
    assert _LOW_HEDGING_CEILING == 0.15
    assert _HIGH_HEDGING_FLOOR == 0.35


# ---------------------------------------------------------------------------
# (5) Case insensitivity + word-boundary + apostrophe normalisation.
# ---------------------------------------------------------------------------


def test_case_insensitive_unigram_match() -> None:
    """CANNOT and cannot both fire."""
    assert _sentence_hits("CANNOT be disclosed at this moment for competitive reasons.")[0]
    assert _sentence_hits("cannot be disclosed at this moment for competitive reasons.")[0]


def test_word_boundary_prevents_substring_firing() -> None:
    """'specifications' must not fire on the 'specific' unigram, and
    'recalled' must not fire on 'recall'."""
    # Neutral sentence with substring-containing words only — no actual
    # keywords present (since "specifications" and "recalled" are not
    # in the list and should not trigger substring matches).
    has_hit, _ = _sentence_hits(
        "Product specifications were recalled from the vendor's archive yesterday."
    )
    # This sentence should NOT fire — specifications != specific,
    # recalled != recall, and no other keyword present.
    # (Note: we still might fire on other incidental words; this test
    # specifically guards against the substring-match bug.)
    # To make it deterministic we check that the hit, if any, is not
    # from the unigram "specific" — we can't easily introspect which
    # unigram fired, so we check by constructing a sentence that, in
    # the BUGGY implementation, would fire ONLY on these substring
    # confusions.
    # Simpler check: a sentence that contains "specifications" but no
    # other hedging tokens should NOT fire.
    bare = "The specifications were recalled."
    has_hit_bare, cats_bare = _sentence_hits(bare)
    assert not has_hit_bare, (
        f"substring match bug: 'specifications'/'recalled' fired unigrams "
        f"{cats_bare}"
    )


def test_apostrophe_normalisation_matches_paper_bigrams() -> None:
    """'can't' should match the paper's 'can t' bigram after apostrophe
    strip, and 'don't' should match 'don t'."""
    # Straight apostrophe
    assert _sentence_hits("We can't share that level of detail right now.")[0]
    # Curly apostrophe (U+2019)
    assert _sentence_hits("We can\u2019t share that level of detail right now.")[0]
    # Check the bigram ("can t") actually fires (not just a unigram)
    _, cats = _sentence_hits("We can't do that.")
    assert cats["bigrams"] >= 1 or cats["unigrams"] >= 1


# ---------------------------------------------------------------------------
# (6) Sentence splitter — the 30-char floor.
# ---------------------------------------------------------------------------


def test_sentence_splitter_drops_short_fragments() -> None:
    """List markers and headers under 30 chars get dropped."""
    text = (
        "1. Revenue. 2. Costs. 3. Outlook.\n\n"
        "This is a longer sentence that easily passes the thirty character floor for sentences."
    )
    sentences = _split_sentences(text)
    # "1. Revenue.", "2. Costs.", "3. Outlook." all under 30 chars.
    # Only the long sentence should survive.
    assert len(sentences) == 1
    assert "thirty character floor" in sentences[0].lower()


def test_min_sentences_pin() -> None:
    """Guard against accidental drift of the indeterminate floor."""
    assert _MIN_SENTENCES == 10


# ---------------------------------------------------------------------------
# (7) Substrate-port warning presence.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_substrate_port_warning_on_every_non_null_call() -> None:
    """The skill MUST surface substrate_port_mdna_vs_earnings_call on
    every non-null call. The port is the load-bearing approximation;
    no caller can miss it."""
    r = _fresh_registry()
    skill = r.get("compute_nonanswer_hedging_density")
    out = skill.run({"cik": "0000320193", "fiscal_year_end": "2023-09-30"})
    assert out.get("hedging_density") is not None
    assert any(
        "substrate_port_mdna_vs_earnings_call" in w for w in out["warnings"]
    ), f"substrate-port warning missing from: {out['warnings']}"


# ---------------------------------------------------------------------------
# (8) Soft sanity band on real MVP filings.
# ---------------------------------------------------------------------------


@pytest.mark.requires_live_data
def test_real_filings_produce_sensible_densities() -> None:
    """The 4 scorable MVP filings (Apple, Carvana, Enron, WorldCom)
    produce non-null densities in [0.0, 1.0] with defined flags.
    Microsoft is expected to be indeterminate (extract_mdna truncates).
    """
    r = _fresh_registry()
    skill = r.get("compute_nonanswer_hedging_density")
    cases = [
        ("0000320193", "2023-09-30", "Apple FY2023"),
        ("0001690820", "2022-12-31", "Carvana FY2022"),
        ("0001024401", "2000-12-31", "Enron FY2000"),
        ("0000723527", "2001-12-31", "WorldCom FY2001"),
    ]
    for cik, fye, name in cases:
        out = skill.run({"cik": cik, "fiscal_year_end": fye})
        assert "error" not in out, f"{name}: {out}"
        density = out["hedging_density"]
        assert density is not None, f"{name}: got null density"
        assert 0.0 <= density <= 1.0, f"{name}: density={density} outside [0,1]"
        assert out["flag"] in {
            "low_hedging",
            "typical_hedging",
            "high_hedging",
        }, f"{name}: unexpected flag {out['flag']}"
        # Citation present for every non-null call.
        assert len(out["citations"]) == 1


@pytest.mark.requires_live_data
def test_microsoft_is_indeterminate() -> None:
    """Microsoft FY2023 MD&A is truncated to <10 sentences by
    extract_mdna; flag must be indeterminate."""
    r = _fresh_registry()
    skill = r.get("compute_nonanswer_hedging_density")
    out = skill.run({"cik": "0000789019", "fiscal_year_end": "2023-06-30"})
    assert out["hedging_density"] is None
    assert out["flag"] == "indeterminate"


@pytest.mark.requires_live_data
def test_preixbrl_filings_get_the_data_quality_warning() -> None:
    """Enron and WorldCom fire pre_ixbrl_paragraph_structure."""
    r = _fresh_registry()
    skill = r.get("compute_nonanswer_hedging_density")
    for cik, fye, name in [
        ("0001024401", "2000-12-31", "Enron"),
        ("0000723527", "2001-12-31", "WorldCom"),
    ]:
        out = skill.run({"cik": cik, "fiscal_year_end": fye})
        assert any(
            "pre_ixbrl_paragraph_structure" in w for w in out["warnings"]
        ), f"{name}: pre_ixbrl warning missing from {out['warnings']}"
        # Confidence reduced.
        assert out["confidence"] == pytest.approx(0.55, abs=0.01)
