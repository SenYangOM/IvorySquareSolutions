# Free Cash Flow to the Firm and to Equity

## Core Idea

Free cash flow measures the cash a business generates **after** funding its operating needs and capital investments — cash that is genuinely available for distribution. Two perspectives matter:

- **FCFF (Free Cash Flow to the Firm)** — cash available to *all* capital providers (debt holders and equity holders) before any financing payments.
- **FCFE (Free Cash Flow to Equity)** — cash available to *equity holders only*, after debt obligations have been settled.

The distinction is the financing layer: FCFF sits above it; FCFE sits below it.

---

## Formulas

**Starting from Net Income:**

```
FCFF = Net Income
     + Non-cash Charges (e.g., D&A)
     + Interest Expense × (1 − Tax Rate)
     − Fixed Capital Investment (CapEx)
     − Change in Working Capital (ΔNWC)

FCFE = Net Income
     + Non-cash Charges
     − Fixed Capital Investment
     − Change in Working Capital
     + Net Borrowing
```

**Relationship between the two:**

```
FCFE = FCFF
     − Interest Expense × (1 − Tax Rate)
     + Net Borrowing
```

---

## Worked ASCII Example

Assume a firm reports (all figures in $M):

```
Net Income              =  120
Depreciation            =   30
Interest Expense        =   20   (tax rate 25%)
CapEx                   =   50
ΔNWC                    =   10
Net Borrowing           =   15

FCFF = 120 + 30 + 20×(1−0.25) − 50 − 10
     = 120 + 30 + 15 − 50 − 10
     = 105

FCFE = 105 − 15 + 15
     = 105                    ← coincidence here; verify:
FCFE = 120 + 30 − 50 − 10 + 15
     = 105  ✓
```

Both routes converge, confirming internal consistency.

---

## Why Determinism Matters

FCFF and FCFE are **closed-form** calculations: given a fixed set of accounting inputs, exactly one numerical answer exists. This makes them ideal anchors for valuation models (DDM alternatives, DCF). Any ambiguity in the formula — say, forgetting the after-tax interest add-back — produces a systematically wrong intrinsic value estimate. A precise, memorized reference formula eliminates that drift and ensures reproducible results across exam problems and real analyses.

---

## Prereqs

- **Accounting fundamentals** — reading an income statement and cash flow statement
- **Time value of money** — understanding why future cash flows are discounted
- **Capital structure basics** — debt vs. equity financing and the tax shield on interest
- **Working capital concepts** — current assets, current liabilities, and their changes
- **Dividend discount model (DDM)** — the valuation framework FCFE is designed to extend
