# extract_mdna

**Layer:** `fundamental` (L1)
**Maintainer persona:** `accounting_expert`
**Status:** `alpha` at MVP

Return the verbatim text of **Part II, Item 7 — Management's Discussion and
Analysis of Financial Condition and Results of Operations** from a US public
company's 10-K filing.

## Purpose

MD&A is where a filing's numbers become a narrative. The structured
financial statements (`extract_canonical_statements` output) tell you what
happened; MD&A tells you what management says about why it happened, what
the risks are, what the accounting policies assume, and — with an
accounting reader's eye — where the gap between the two may lie. An
earnings-quality analysis that looks only at ratios and never at MD&A
misses the disclosure texture that often carries the first sign of a
problem (a policy change tucked into a footnote reference, a year-over-year
shift in how segment revenue is characterized, an ambiguous "unusual item"
line).

This skill produces the text; it does not interpret it. Interpretation is a
downstream L2 concern. The extractor is deliberately dumb: locate the
"Item 7" heading, bound the section at the next "Item 7A" / "Item 8"
heading, strip inline HTML, decode entity references, return the
paragraph-wrapped plain text with one Citation record pointing back at the
source. An accounting expert who opens a skill output expects to be able
to read exactly what the filing says, not a rewritten paraphrase.

## Inputs

| Field | Type | Description |
|---|---|---|
| `cik` | `string` (10 digits) | Zero-padded SEC CIK for the issuer. |
| `fiscal_year_end` | `string` (ISO date) | Fiscal year end of the 10-K. |

## Outputs

| Field | Type | Description |
|---|---|---|
| `section_text` | `string \| null` | The MD&A section as a UTF-8 string with HTML stripped and entities decoded. Null when the section bounds cannot be located. |
| `citations` | `array` | One Citation record pointing at `<cik>/<accession>::mdna::item_7`. Empty when `section_text` is null. |
| `start_offset` / `end_offset` | `integer` | Byte offsets in the primary document. 0 when null. |
| `warnings` | `array` | e.g. `"section_bounds_not_located"` when a filing's Item 7 heading cannot be found. |

## Typical call

```bash
mvp run extract_mdna --cik 0000320193 --year 2023-09-30
```

## Typical failure modes

- **Item 7 bounds cannot be located** — some older filings use
  non-standard heading text ("Management's Discussion and Analysis" without
  the "Item 7" prefix). The skill returns `section_text: null` with a
  `section_bounds_not_located` warning rather than guessing. Don't guess;
  MD&A is discursive enough that a mis-bounded section is worse than a
  null.
- **Pre-iXBRL SGML filing with non-ASCII encoding** — the skill decodes
  common entity references and `latin-1` fallbacks; odd characters outside
  ASCII / UTF-8 / latin-1 may survive into the output. Not fatal; the
  downstream reader (an accounting expert or an LLM) handles them
  gracefully.
- **Filing not in the MVP sample set** → `unknown_filing` error, same as
  `extract_canonical_statements`.

## Links

- Manifest: [`manifest.yaml`](manifest.yaml)
- Unit tests: `tests/unit/skills/test_extract_mdna.py`
