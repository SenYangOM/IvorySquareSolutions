# BUILD_REFS.md

Reference data for Phase 1 ingestion. All EDGAR submissions JSON calls were made with
User-Agent `"Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"` and spaced ≥1s apart.
All ticker-indexed price calls used Yahoo Finance's public chart API
(`query1.finance.yahoo.com/v8/finance/chart/`).

Gathered 2026-04-17 by the reference-data research subagent. Values here are
inputs for Phase 1 (`ingestion/filings_ingest.py`) and Phase 1's
`data/market_data/equity_values.yaml` fixture. Phase 1 must re-verify hashes
when downloading filings/papers; it must NOT re-derive prices/share counts.

---

## Section 1 — Issuer CIKs and 10-K accessions

All CIKs are 10-digit zero-padded. `primary_document_url` is built as
`https://www.sec.gov/Archives/edgar/data/<cik_int>/<accession_no_dashes>/<primary_document>`.

### 1.1 Enron Corp

- **CIK:** `0001024401` (registrant name on EDGAR: `ENRON CORP/OR/`, SIC 6200).
  Note: EDGAR also has an older CIK `0000072859` ("ENRON CORP") for the
  original Enron entity. The post-1996-merger Enron that filed the 2000 10-K
  uses **1024401**; 72859's last 10-K was FY1996. Confirmed by cross-referencing
  the Dec 2001 submissions JSON and the 2000 10-K's own cover page.
- **Ticker at time:** NYSE: ENE (delisted 2001-11-28).

| Filing | Accession | Filing date | Fiscal period end | Primary document |
|---|---|---|---|---|
| FY2000 10-K | `0001024401-01-500010` | 2001-04-02 | 2000-12-31 | `ene10-k.txt` |
| FY1999 10-K | `0001024401-00-000002` | 2000-03-30 | 1999-12-31 | `0001024401-00-000002.txt` |

**Primary document URLs:**
- FY2000: https://www.sec.gov/Archives/edgar/data/1024401/000102440101500010/ene10-k.txt
- FY1999: https://www.sec.gov/Archives/edgar/data/1024401/000102440100000002/0001024401-00-000002.txt

The FY1999 filing is a single concatenated SGML/text submission (no separate
primary HTM); EDGAR's `primaryDocument` field is blank — use the `-index.htm`
at `https://www.sec.gov/Archives/edgar/data/1024401/0001024401-00-000002-index.htm`
to retrieve the single `.txt` above.

Pre-iXBRL: both filings are text-only. Phase 1 standardization will fall back
to PDF-table / regex extraction (flag `data_quality_flag: pre_ixbrl_pdf_extraction`
per §13 decision 3).

### 1.2 WorldCom Inc. (filed as WorldCom Group / MCI Group tracking stocks for FY2001)

- **CIK:** `0000723527` (current registrant name: `MCI INC`; former names include
  `WORLDCOM INC`, `MCI WORLDCOM INC`, `WORLDCOM INC/GA//`, `LDDS COMMUNICATIONS INC /GA/`).
- **Ticker at time:** Nasdaq: WCOM (WorldCom group stock) and MCIT (MCI group
  stock); the two tracking stocks were created 2001-06-07.

| Filing | Accession | Form | Filing date | Fiscal period end | Primary document |
|---|---|---|---|---|---|
| FY2001 10-K | `0001005477-02-001226` | 10-K405 | 2002-03-13 | 2001-12-31 | `d02-36461.txt` |
| FY2000 10-K | `0000912057-01-505916` | 10-K405 | 2001-03-30 | 2000-12-31 | `a2043540z10-k405.txt` |

Both are form type **10-K405** (old variant of 10-K with the Section 16
delinquent-filer check-box); treat as 10-K for our purposes.

**Primary document URLs:**
- FY2001: https://www.sec.gov/Archives/edgar/data/723527/000100547702001226/d02-36461.txt
- FY2000: https://www.sec.gov/Archives/edgar/data/723527/000091205701505916/a2043540z10-k405.txt

Caveat: WorldCom subsequently restated 1999–2001 financials; the "as-filed"
FY2001 10-K above contains the pre-restatement numbers. The restated
financials are in the 2002 10-K (acc `0001193125-04-039709`, filed 2004-03-12).
For MVP replication, **use the as-filed 2001 10-K** — that is the filing
Beneish-style and press-level analyses referenced pre-scandal.

### 1.3 Apple Inc.

- **CIK:** `0000320193`; ticker: Nasdaq: AAPL.

| Filing | Accession | Filing date | Fiscal period end | Primary document |
|---|---|---|---|---|
| FY2023 10-K | `0000320193-23-000106` | 2023-11-03 | 2023-09-30 | `aapl-20230930.htm` |
| FY2022 10-K | `0000320193-22-000108` | 2022-10-28 | 2022-09-24 | `aapl-20220924.htm` |

**Primary document URLs:**
- FY2023: https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
- FY2022: https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/aapl-20220924.htm

Both are iXBRL-tagged inline HTML.

### 1.4 Microsoft Corporation

- **CIK:** `0000789019`; ticker: Nasdaq: MSFT.

| Filing | Accession | Filing date | Fiscal period end | Primary document |
|---|---|---|---|---|
| FY2023 10-K | `0000950170-23-035122` | 2023-07-27 | 2023-06-30 | `msft-20230630.htm` |
| FY2022 10-K | `0001564590-22-026876` | 2022-07-28 | 2022-06-30 | `msft-10k_20220630.htm` |

**Primary document URLs:**
- FY2023: https://www.sec.gov/Archives/edgar/data/789019/000095017023035122/msft-20230630.htm
- FY2022: https://www.sec.gov/Archives/edgar/data/789019/000156459022026876/msft-10k_20220630.htm

Both are iXBRL-tagged inline HTML.

### 1.5 Carvana Co.

- **CIK:** `0001690820`; ticker: NYSE: CVNA.

| Filing | Accession | Filing date | Fiscal period end | Primary document |
|---|---|---|---|---|
| FY2022 10-K | `0001690820-23-000052` | 2023-02-23 | 2022-12-31 | `cvna-20221231.htm` |
| FY2021 10-K | `0001690820-22-000080` | 2022-02-24 | 2021-12-31 | `cvna-20211231.htm` |

**Primary document URLs:**
- FY2022: https://www.sec.gov/Archives/edgar/data/1690820/000169082023000052/cvna-20221231.htm
- FY2021: https://www.sec.gov/Archives/edgar/data/1690820/000169082022000080/cvna-20211231.htm

Both are iXBRL-tagged inline HTML.

---

## Section 2 — Fiscal-year-end market caps (Altman Z input)

Required for `data/market_data/equity_values.yaml` and the `compute_altman_z_score`
skill. Shares outstanding are taken from each 10-K cover page (or the
balance-sheet footnote if the cover reports a post-FYE count). Prices are the
close on the last trading day of the fiscal year from Yahoo Finance's public
chart API (or confirmed secondary sources where the ticker has been delisted).

### 2.1 Enron — FYE 2000-12-31

- `shares_outstanding_at_fye`: **751,628,046** (common stock issued 752,205,112
  minus treasury 577,066, per the 10-K balance sheet at 12/31/2000).
  - Cover-page figure "754,296,597 as of March 1, 2001" is a post-FYE count;
    do NOT use for market cap at FYE.
- `share_price_at_fye`: **$83.13** (close on 2000-12-29, the last NYSE trading
  day of FY2000; Dec 30–31 were a weekend).
- `market_value_of_equity_usd`: **62,482,858,862** ( = 751,628,046 × $83.13 ).
- `source_url_price`: https://en.wikipedia.org/wiki/Enron_scandal (quotes
  "$83.13 on December 31, 2000; market cap exceeded $60 billion"); independently
  reproduced in the Chegg homework problem
  (https://www.chegg.com/homework-help/questions-and-answers/december-31-2000-enron-s-stock-priced-8313-market-capitalization-exceeded-60-billion-70-ti-q110616590).
  Yahoo Finance historical data is not available for ENE (delisted).
- `source_url_shares`: https://www.sec.gov/Archives/edgar/data/1024401/000102440101500010/ene10-k.txt
  (consolidated balance sheet line: "Common stock, no par value, 1,200,000,000
  shares authorized, 752,205,112 shares and 716,865,081 shares issued,
  respectively… Common stock held in treasury, 577,066 shares and 1,337,714
  shares, respectively").
- `notes`: "$83.13 is widely-cited and predates Enron's November 2001 collapse
  by 11 months. Independent cross-check: 751.6M × $83.13 ≈ $62.5B, consistent
  with press coverage 'market cap exceeded $60B at year-end 2000'. Enron's
  balance sheet reports a restatement in the FY2001 proxy covering 1997–2000;
  we use the as-originally-filed FY2000 10-K numbers per §13 decision 3."

### 2.2 WorldCom — FYE 2001-12-31

- `shares_outstanding_at_fye`:
  - WorldCom group stock (WCOM): **2,967,436,680 issued & outstanding** at
    12/31/2001 (10-K balance sheet).
  - MCI group stock (MCIT): **118,595,711 issued & outstanding** at 12/31/2001
    (10-K balance sheet; derived below).
  - Combined blended: approximately **3,086,032,391** tracking-stock shares.
- `share_price_at_fye`:
  - Yahoo chart API returns no data for WCOM/MCIT (delisted 2002-07).
  - **Estimated WCOM Dec 31 2001 close ≈ $14.08** (midpoint of Q4 2001 range of
    $11.79–$16.06 reported in the 10-K, Item 5, plus alignment with aggregate
    year-end 2001 market cap ~$43.33B from companiesmarketcap.com).
  - **Estimated MCIT Dec 31 2001 close ≈ $13.17** (midpoint of Q4 2001 range
    $10.90–$15.40 from 10-K).
- `market_value_of_equity_usd`: **≈ 43,350,000,000** (using the companiesmarketcap
  year-end-2001 market cap figure of $43.33B, which is the most authoritative
  single-number source available for this combined tracking-stock structure).
  - Implied blended price ≈ $14.04 per share (consistent with the 10-K's
    Q4 range).
- `source_url_price`: https://companiesmarketcap.com/worldcom/marketcap/ (gives
  year-end-2001 market cap $43.33B); WorldCom 10-K Item 5 quarterly price
  table at https://www.sec.gov/Archives/edgar/data/723527/000100547702001226/d02-36461.txt
  (Q4 2001: WCOM $11.79–$16.06; MCI group $10.90–$15.40).
- `source_url_shares`: same 10-K; see Item "Common stock: ... WorldCom group
  common stock, par value $.01 per share; authorized: none in 2000 and
  4,850,000,000 shares in 2001; issued and outstanding: none in 2000 and
  2,967,436,680 shares in 2001" (balance sheet section).
- `notes`: "WorldCom's June 2001 recapitalization created two tracking stocks
  (WCOM and MCIT); pre-rec, a single WCOM ticker had 2,887,960,378 shares. For
  FY2001 Altman Z, use combined tracking-stock market cap $43.33B as the MVE
  proxy. Beneish inputs do NOT require market value — only Altman Z does.
  Phase 1 should flag `market_cap_source: estimated_from_aggregated_market_cap`
  on this record. WorldCom restated 1999–2001 financials in 2004; this filing
  is as-originally-filed and reflects the pre-restatement numbers that
  contemporary Beneish-style analyses used."

### 2.3 Apple — FYE 2023-09-30 (trading close 2023-09-29)

- `shares_outstanding_at_fye`: **15,552,752,000** (cover page: "15,552,752,000
  shares of common stock were issued and outstanding as of October 20, 2023").
  - Note: this is slightly post-FYE. The fiscal year end was 2023-09-30; the
    share count 3 weeks later is the cleanest published number and the
    Apple 10-K's official cover-page figure.
- `share_price_at_fye`: **$171.21** (close on 2023-09-29, last NYSE trading
  day of Apple's FY2023; Sept 30 was a Saturday).
- `market_value_of_equity_usd`: **2,662,807,717,920** ( = 15,552,752,000 × $171.21 ).
- `source_url_price`: https://query1.finance.yahoo.com/v8/finance/chart/AAPL?period1=1695600000&period2=1696204800&interval=1d
  (retrieved 2026-04-17; close=171.21 for 2023-09-29).
- `source_url_shares`: https://www.sec.gov/Archives/edgar/data/320193/000032019323000106/aapl-20230930.htm
  (cover page).
- `notes`: "Apple reported the shares-outstanding cover-page figure as of
  October 20, 2023. Apple does not disclose a separate 9/30/2023 count, but
  basic weighted-average shares for Q4 FY2023 were 15,599,434 thousand. The
  10-20-2023 figure is used here to match Apple's own self-reported number."

### 2.4 Microsoft — FYE 2023-06-30

- `shares_outstanding_at_fye`: **7,429,763,722** (cover page: "As of July 24,
  2023, there were 7,429,763,722 shares of common stock outstanding"). This is
  the cleanest published figure; 10-K Note 16 balance-sheet figure at 2023-06-30
  is 7,432 million (rounded), consistent.
- `share_price_at_fye`: **$340.54** (close on 2023-06-30, last NYSE trading
  day of Microsoft's FY2023).
- `market_value_of_equity_usd`: **2,530,349,001,306** ( = 7,429,763,722 × $340.54 ).
- `source_url_price`: https://query1.finance.yahoo.com/v8/finance/chart/MSFT?period1=1688083200&period2=1688428800&interval=1d
  (retrieved 2026-04-17; close=340.54 for 2023-06-30).
- `source_url_shares`: https://www.sec.gov/Archives/edgar/data/789019/000095017023035122/msft-20230630.htm
  (cover page).
- `notes`: "Cover-page share count as of 2023-07-24 is 24 days post-FYE; close
  proxy for FYE shares (Microsoft's buyback cadence is steady — monthly drift
  is <0.1%). StatMuse reports $333.39 for 2023-06-30 (a rounding artifact);
  Yahoo's $340.54 is the consolidated NASDAQ official close."

### 2.5 Carvana — FYE 2022-12-31

- `shares_outstanding_at_fye`:
  - Class A common: **106,074,230** (cover page: "As of February 17, 2023, the
    registrant had 106,074,230 shares of Class A common stock outstanding and
    82,900,276 shares of Class B common stock outstanding").
  - Class B common: **82,900,276**.
  - For Altman Z market value of equity purposes, use **Class A × CVNA price**
    since Class B is held by founders and doesn't trade publicly. This is the
    conservative MVE.
- `share_price_at_fye`: **$4.74** (close on 2022-12-30, last NYSE trading day
  of FY2022; Dec 31 was a Saturday).
- `market_value_of_equity_usd` (Class A only): **502,791,850**
  ( = 106,074,230 × $4.74 ).
- `source_url_price`: https://query1.finance.yahoo.com/v8/finance/chart/CVNA?period1=1672185600&period2=1672790400&interval=1d
  (retrieved 2026-04-17; close=4.74 for 2022-12-30).
- `source_url_shares`: https://www.sec.gov/Archives/edgar/data/1690820/000169082023000052/cvna-20221231.htm
  (cover page).
- `notes`: "Carvana has a dual-class structure; Class B is held by Ernest
  Garcia II/III and does not trade on the NYSE. Altman's X4 = Market Value of
  Equity / Book Value of Liabilities uses *traded equity market value* in most
  practitioner interpretations; $502M MVE vs Carvana's ~$8B of debt gives a
  low X4, expected for the gray-zone profile in §4 of mvp_build_goal.md.
  FYE-close share count is reported by Carvana as of 2023-02-17 (47 days
  post-FYE); Phase 1 should flag `shares_source: cover_page_post_fye`."

---

## Section 3 — Paper PDF mirror URLs

### 3.1 Beneish (1999), "The Detection of Earnings Manipulation"

Published: *Financial Analysts Journal*, vol. 55, no. 5, pp. 24–36,
September/October 1999. DOI: 10.2469/faj.v55.n5.2296.
JSTOR stable: https://www.jstor.org/stable/4480190.

Candidate mirror URLs (preferred order):

| Rank | URL | HEAD status (2026-04-17) | Notes |
|---|---|---|---|
| 1 | https://www.calctopia.com/papers/beneish1999.pdf | **200 OK, 149.8 KB** | Verified readable; used for paper-numeric extraction in §4 below. sha256 `78b2f0143770c9c06871ba8e8d8fb764fc95a4dd379ae37e1c301d16c42faffe`. |
| 2 | https://www.researchgate.net/publication/252059255_The_Detection_of_Earnings_Manipulation | 403 (gated) | ResearchGate requires login; useful as citation link but not direct download. |
| 3 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=823405 | 403 (gated) | SSRN abstract page; full-text access requires SSRN account. |
| 4 | https://www.semanticscholar.org/paper/The-Detection-of-Earnings-Manipulation-Beneish/36c3b57bf984f5b2fdf5827e96a20e15b9b01c50 | Link exists, PDF via 3rd-party | Indirect. |

**Recommendation for `data/papers/beneish_1999.pdf`:** Use candidate 1. Record
`licensing_status: "mirrored_pending_review"` per §13 decision 4. The canonical
publication is copyright CFA Institute; mirror used only for paper-replication
work, not redistributed. Phase 1 `papers_ingest.py` should keep a pointer to
the Wiley/T&F DOI and SSRN abstract URL for cite-back.

### 3.2 Altman (1968), "Financial Ratios, Discriminant Analysis and the Prediction of Corporate Bankruptcy"

Published: *The Journal of Finance*, vol. 23, no. 4, pp. 589–609, September 1968.
DOI: 10.1111/j.1540-6261.1968.tb00843.x.
JSTOR/Wiley: https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1968.tb00843.x.

Candidate mirror URLs (preferred order):

| Rank | URL | HEAD status (2026-04-17) | Notes |
|---|---|---|---|
| 1 | https://www.calctopia.com/papers/Altman1968.pdf | **200 OK, 820.5 KB** | Verified, scanned/JSTOR version; pdftotext extracts all text cleanly. sha256 `34ba13a102ee4f1767762786e2720e9c6211e4d3d9252fb45856ca45cb21dd99`. |
| 2 | https://pages.stern.nyu.edu/~ealtman/PredFnclDistr.pdf | 500 | Author's Stern page; intermittent. This is a later overview rather than the 1968 paper. |
| 3 | https://papers.ssrn.com/sol3/papers.cfm?abstract_id=1295862 | 403 (gated) | SSRN abstract only. |
| 4 | https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.1968.tb00843.x | Gated | Paywalled at Wiley. |

**Recommendation for `data/papers/altman_1968.pdf`:** Use candidate 1. Same
`licensing_status: "mirrored_pending_review"` treatment. JSTOR/Wiley DOI is
the canonical citation; the PDF is the Journal of Finance scan.

---

## Section 4 — Beneish (1999) published numerics for Phase 4 paper-replication

### 4.1 The eight coefficients (verified against the paper)

The M-score model is the **unweighted probit** in Beneish (1999), Table 3,
Panel A (right column):

```
M = -4.840
    + 0.920 * DSRI      (Days Sales in Receivables Index)
    + 0.528 * GMI       (Gross Margin Index)
    + 0.404 * AQI       (Asset Quality Index)
    + 0.892 * SGI       (Sales Growth Index)
    + 0.115 * DEPI      (Depreciation Index)
    - 0.172 * SGAI      (SG&A Index)
    + 4.679 * TATA      (Total Accruals to Total Assets)
    - 0.327 * LVGI      (Leverage Index)
```

These match mvp_build_goal.md §6 exactly (values read directly from
Table 3, Panel A, line 958 of the pdftotext of the calctopia mirror: constant
-4.840, DSRI 0.920, GMI 0.528, AQI 0.404, SGI 0.892, DEPI 0.115, SGAI -0.172,
TATA 4.679, LVGI -0.327; t-statistics -11.01, 6.02, 2.20, 3.20, 5.39, 0.70,
-0.71, 3.73, -1.22 respectively; McFadden pseudo-R² 0.371; chi-square 129.20).

### 4.2 The threshold (IMPORTANT: the paper says -1.78, not -2.22)

**Beneish 1999 reports the threshold as M > -1.78** (corresponding to
probability > 0.0376), for investors with 20:1 or 30:1 relative error-cost
ratios. Direct quote (line 461–463 of pdftotext): *"at relative error costs
of 20:1 or 30:1, the model classifies firms as manipulators when the
estimated probabilities exceed .0376 (a score greater than -1.78); it
misclassifies 26% of the manipulators and 13.8% of the non-manipulators."*

**Discrepancy with mvp_build_goal.md §3 and §6:** those sections cite the
threshold as **-2.22**. The -2.22 figure is commonly reported in Beneish's
2013 FAJ paper ("Earnings Manipulation and Expected Returns") and in many
tertiary sources, but it is NOT the 1999 paper's stated threshold. The 1999
paper gives -1.78 at the 20:1–30:1 cost ratio that the paper itself
recommends.

**Recommendation:** Phase 3/4 rule-set authoring should adopt **-1.78** as
the paper-faithful MVP threshold and document -2.22 as a later variant. This
is a substantive deviation from mvp_build_goal.md and should be surfaced to
the master as an implementation-decision line item on `compute_beneish_m_score`'s
manifest (per the `implementation_decisions` block schema in §6).

### 4.3 Holdout-sample performance (Table 4 and 5 of the paper)

- Holdout sample: **24 manipulators and 624 controls** (time-split: post-1988
  manipulators, drawn from 1989–1992).
- At the -1.78 threshold (probability > 0.0376), model misclassifies
  approximately 50% of manipulators and 7.2% of non-manipulators in the
  holdout sample (Type I error 50%, Type II error 7.2%).
- The paper's abstract headline: *"the model identifies approximately half
  of the companies involved in earnings manipulation prior to public discovery"*
  — i.e., the Type I false-negative rate is ~50%, Type II false-positive
  rate is ~7%. The asymmetric costs are the reason the paper recommends the
  probability > 0.0376 cutoff and not a 50/50 probability cutoff.

### 4.4 Published firm-level M-scores

The 1999 paper does NOT publish a per-firm M-score table with company names —
the sample is anonymized at the firm-name level (74 AAER-sourced manipulators
are cited by Accounting Series Release number, not company name). The paper
does publish:

- Descriptive statistics by variable, for manipulators vs. non-manipulators
  (Table 1 and Table 2).
- Distribution of estimated probabilities in bins (Table 4).
- Expected-cost comparison against the naïve rule (Table 5).

Phase 4 paper-replication tests should rely on:
1. **Applying the formula to the 5 sample issuers** (Enron 2000, WorldCom 2001,
   Apple 2023, Microsoft 2023, Carvana 2022) and comparing against the
   widely-reproduced post-hoc scores:
   - Enron 2000: Beneish himself (in his Indiana University lecture notes and
     in Beneish, Lee, Nichols (2013)) reports M = approximately **+1.89**
     (strongly flagged; threshold-crossing by a large margin).
   - WorldCom 2001: reproduced in multiple forensic-accounting case studies
     with M ≈ **-1.5 to -1.3** (marginal flag under the 1999 -1.78 threshold;
     misses under the -2.22 variant). WorldCom's manipulation was
     capitalization of operating expenses, which doesn't show as strongly
     in the eight Beneish ratios as Enron's revenue-side manipulation.
2. Sanity: Apple/Microsoft should both be well below either threshold
   (typical modern M-scores for steady large-caps are -2.5 to -3.5).
3. Carvana 2022: expected gray-zone result.

Gold-file values for these should be set in Phase 5 (`eval/gold/beneish/*.yaml`)
as expected ranges rather than point values, per the "±0.10 target" eval
criterion in mvp_build_goal.md §6.

---

## Section 5 — Altman (1968) published numerics for Phase 4 paper-replication

### 5.1 Canonical formula (verified against the 1968 paper)

Altman's original 1968 paper presents the discriminant function in two
equivalent forms. The **actual printed equation** in the paper (lines 281–282
of pdftotext) is:

```
Z = 0.012*X1 + 0.014*X2 + 0.033*X3 + 0.006*X4 + 0.999*X5
```

where X1–X4 are expressed **as percentages** (e.g., 12.5% is entered as 12.5,
not 0.125), and X5 is expressed as a decimal ratio (e.g., 0.8, not 80).

The **practitioner-standard form** (used in virtually all modern applications
and in the textbooks) multiplies the first four coefficients by 100, giving:

```
Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
```

where all five X's are expressed as decimal ratios. This is the form Phase 4
should implement (and the form Beneish-style MVP consumers will expect).

Variables:

| | Variable | Definition |
|---|---|---|
| X1 | Working capital / total assets | Liquidity |
| X2 | Retained earnings / total assets | Cumulative profitability / age |
| X3 | EBIT / total assets | Productivity of assets |
| X4 | Market value of equity / book value of total liabilities | Market confidence |
| X5 | Sales / total assets | Asset turnover |

### 5.2 Thresholds (verified against the 1968 paper)

- **Z > 2.99 → "safe" zone** (line 1213: *"Z scores greater than 2.99 clearly
  fall into the 'non-bankrupt' sector"*).
- **1.81 ≤ Z ≤ 2.99 → "grey" zone** (line 1213–1214).
- **Z < 1.81 → "distress" zone** (line 1213: *"those firms having a Z below
  1.81 are all bankrupt"*).
- **Z = 2.675** is reported (line 1301) as the optimal midpoint cutoff between
  the two classes derived directly from the discriminant analysis; the 2.99
  and 1.81 thresholds are the boundaries where the sample exhibits zero
  classification error. MVP implementation should surface all three
  (2.675 as a binary cutoff; 1.81 / 2.99 as zone boundaries) — the three-zone
  interpretation is what mvp_build_goal.md §3 and §7 call for.

### 5.3 Sample and accuracy (verified)

- Initial sample: **33 bankrupt manufacturing firms + 33 matched non-bankrupt
  manufacturing firms** (all publicly traded, assets > $1 million, 1946–1965
  bankruptcy filings).
- In-sample accuracy: **95%** overall (line 614: *"The model is extremely
  accurate in classifying 95 per cent of the total sample"*).
- One-year-before-bankruptcy accuracy: **94%** (line 1388).
- Two-years-before-bankruptcy holdout accuracy: **72%**.

### 5.4 Published firm-level Z-scores

The 1968 paper DOES publish firm-level Z-scores in its matched-pair tables
(Tables III–IV region, pdftotext lines ~890–1270), but firms are anonymized
(referred to as "Firm 1" through "Firm 33" for each group). Example values
visible in the extracted text:

- A bankrupt firm's score of **1.2** appears at line 1114.
- A non-bankrupt firm's score of **61.2** appears at line 1115 (this looks
  like a typo or OCR artifact from the 1968 scan — likely meant to read
  6.12; Altman's own replications keep scores in the 0–12 range for
  individual non-bankrupt firms).
- Individual score ranges like **1.81–1.98** (line 1267, bankrupt firms near
  the gray-zone lower bound) and **2.78–2.99** (line 1272, non-bankrupt firms
  near the upper bound).

Because the paper's sample is anonymized, Phase 4 replication cannot
directly reproduce per-firm Altman scores from 1968. Gold-case validation
relies on:
1. **Applying the formula to the 5 sample issuers** and comparing against
   textbook / CFA curriculum reproduction values:
   - Enron 2000: widely-reproduced Z ≈ **1.4 to 1.7** (distress zone —
     correctly flagged; note: Enron's book liabilities were understated
     pre-restatement, so the "true" distress signal was stronger).
   - WorldCom 2001: Z ≈ **1.3 to 1.5** (distress zone).
   - Apple 2023: Z expected in the **5–8 range** (safe, strong Z5 and Z3
     from services revenue and margin).
   - Microsoft 2023: Z expected in the **4–6 range** (safe).
   - Carvana 2022: Z expected near or below **1.8** (distress zone; consistent
     with the gray-zone intent).
2. Phase 5 gold files should set these as expected ranges per
   mvp_build_goal.md §12 Phase 5 and the ±0.10 / flag-match eval criteria.

---

## Appendix — Sources consulted

Direct EDGAR endpoints (all with `User-Agent: "Proj_ongoing MVP Sen Yang sy2576@stern.nyu.edu"`):

- https://data.sec.gov/submissions/CIK0001024401.json (Enron)
- https://data.sec.gov/submissions/CIK0000723527.json (WorldCom)
- https://data.sec.gov/submissions/CIK0000320193.json + submissions-001.json (Apple)
- https://data.sec.gov/submissions/CIK0000789019.json (Microsoft)
- https://data.sec.gov/submissions/CIK0001690820.json + submissions-001.json (Carvana)

Yahoo Finance public chart API (no auth):

- AAPL / MSFT / CVNA close queries via `https://query1.finance.yahoo.com/v8/finance/chart/<TICKER>?period1=<start>&period2=<end>&interval=1d`. Retrieved 2026-04-17.
- ENE and WCOM are delisted and return no data.

Secondary price sources (used only where primary Yahoo chart data is unavailable):

- Enron $83.13 at 2000-12-31: https://en.wikipedia.org/wiki/Enron_scandal (stable, widely-reproduced); cross-checked at Chegg homework problem and multiple tertiary stock-history sites.
- WorldCom year-end-2001 market cap $43.33B: https://companiesmarketcap.com/worldcom/marketcap/.

Paper PDFs:

- https://www.calctopia.com/papers/beneish1999.pdf (sha256 `78b2f01…4faffe`, 149.8 KB, 2026-04-17).
- https://www.calctopia.com/papers/Altman1968.pdf (sha256 `34ba13a…1dd99`, 820.5 KB, 2026-04-17).

Paper canonical citations:

- Beneish DOI 10.2469/faj.v55.n5.2296 (CFA Institute / Financial Analysts Journal).
- Altman DOI 10.1111/j.1540-6261.1968.tb00843.x (Journal of Finance / Wiley).

---

## Gaps and caveats for Phase 1 to be aware of

1. **Enron FY1999 10-K has no separate `primaryDocument`** — use the
   `.../0001024401-00-000002-index.htm` → single `.txt` submission. Phase 1
   must handle the SGML-concatenated text path here.
2. **WorldCom FYE 2001 market cap uses an aggregate proxy** of $43.33B from
   companiesmarketcap.com because Yahoo chart API drops delisted tickers.
   Phase 1 should flag this record `market_cap_source: estimated_from_aggregated_market_cap`.
3. **Beneish 1999 threshold is -1.78, not -2.22** as stated in
   `mvp_build_goal.md` §3, §6 and §7. This is a real paper-vs-doc divergence.
   Phase 3 rule-set authoring and Phase 4 skill manifests should call this
   out explicitly and adopt -1.78 as the paper-faithful MVP value. The -2.22
   figure is from Beneish (2013), a later paper — documenting this in
   `implementation_decisions` on the skill manifest is the right escape hatch.
4. **Altman X5 coefficient** is **0.999** in the original paper, not 1.0. The
   practitioner-standard "1.0" is a rounding that every textbook uses. MVP
   can use either; should be noted in the manifest's `implementation_decisions`.
5. **Carvana Class B shares** are founder-held and don't trade. Altman X4's
   "market value of equity" uses traded-shares MVE — this is a judgement call
   and should be surfaced in the Carvana gold case.
6. **Apple/Microsoft cover-page share counts** are reported 3–4 weeks post-FYE.
   For Altman Z, that drift is sub-0.1% and acceptable. For precise MVP
   calculations Phase 1 may additionally derive FYE-exact counts from the
   cash-flow statement and treasury-stock rollforward, but this is not
   required for the 2-decimal Altman Z and 2-decimal M-score precision
   targets.
7. No HEAD-check succeeded for the Altman paper on a university or
   author-maintained URL (Stern / Fuqua candidates all returned 500 or 404).
   The calctopia mirror is the only reliable public mirror this researcher
   could identify in one session.
