# Profitability ratios

Profitability ratios scale earnings at successive levels of the income
statement by revenue, isolating the costs absorbed at each stage. They
are the simplest cross-firm comparators of operating efficiency, and
they appear as inputs to the Beneish M-Score (GMI) and as a feature in
the Altman Z-Score (X3, EBIT-to-assets, is profitability-related but
defined against assets rather than revenue).

## Definitions

For a single fiscal period:

    Gross margin       = (Revenue - Cost of Goods Sold) / Revenue
    Operating margin   = Operating Income / Revenue
    Net margin         = Net Income / Revenue
    EBITDA margin      = EBITDA / Revenue

Each ratio is a fraction in `[0, 1]` for a profitable firm; it can be
negative when the corresponding earnings level is negative.

## Hierarchy

Each margin captures a successively broader cost base:

    Revenue
    – COGS                  →  Gross profit         →  Gross margin
    – Operating expenses    →  Operating income     →  Operating margin
    – Taxes, interest, etc. →  Net income           →  Net margin

Adding back D&A to operating income gives EBITDA; the EBITDA margin
isolates cash-flow-style profitability before non-cash and capital
structure effects.

## Worked example

Issuer X reports for FY2023:

    Revenue                 1000
    COGS                     600
    SG&A                     200
    D&A                       50
    Interest expense          20
    Tax                       40
    Net income               90

    Gross margin     = (1000 - 600) / 1000     = 0.40 = 40%
    Operating income = 1000 - 600 - 200 - 50   = 150
    Operating margin = 150 / 1000              = 0.15 = 15%
    EBITDA           = 150 + 50                = 200
    EBITDA margin    = 200 / 1000              = 0.20 = 20%
    Net margin       = 90 / 1000               = 0.09 =  9%

## Why code-backed

Margin computation is closed-form arithmetic; LLMs handle the formulas
correctly but routinely mis-bracket parentheses or pull the wrong
revenue denominator from a multi-segment statement. The code reference
in `code/profitability.py` makes the computation deterministic and
exposes typed warnings for null line items.
