# Income statement structure

The income statement reports a firm's revenue, costs, and profit over a
fiscal period. The order of line items reflects an economic flow from
top-line revenue down to bottom-line net income, with progressively
broader cost categories absorbed at each step.

## Standard line-item order (US GAAP, multistep)

```
   Revenue (also: Sales, Net sales)
 - Cost of goods sold (COGS)
 = Gross profit
 - Selling, general and administrative expenses (SG&A)
 - Research and development expenses (R&D)
 - Depreciation and amortization (D&A; sometimes embedded in COGS/SG&A)
 = Operating income (also: EBIT — Earnings Before Interest and Tax)
 + Interest income / - Interest expense
 + Other non-operating income / expense
 = Pretax income (also: Earnings before tax, EBT)
 - Income tax expense
 = Net income
```

## Single-step vs. multi-step

A *single-step* income statement aggregates all revenues and all
expenses, computing net income in one subtraction. A *multi-step*
statement, used by most US registrants, isolates gross profit and
operating income en route to net income.

## Earnings per share (EPS)

Public companies present basic and diluted EPS at the bottom of the
income statement. Basic EPS uses weighted-average shares; diluted EPS
adjusts for potentially dilutive securities (options, warrants,
convertibles).

## Comprehensive income

Some gains and losses (foreign-currency translation, unrealized
available-for-sale gains under legacy guidance, certain pension
adjustments) bypass net income and flow through *other comprehensive
income (OCI)*. Comprehensive income equals net income plus OCI; it is
reported either on the same statement or in a separate statement.

## Why this matters

Every paper-derived skill that reads an income statement (Beneish
M-Score, Altman Z-Score, accruals decomposition, profitability ratios)
relies on a stable mapping from XBRL tags to these standardized line
items. Knowing the canonical order is the first step in interpreting
any L2 standardization output.

## Why markdown-only (conceptual_high_value)

The bare LLM handles the line-item order correctly the vast majority of
the time. The foundational skill's value is curating the canonical
ordering plus surfacing the non-obvious cases — comprehensive income vs.
net income; single-step vs. multi-step; the ambiguity around where D&A
appears.
