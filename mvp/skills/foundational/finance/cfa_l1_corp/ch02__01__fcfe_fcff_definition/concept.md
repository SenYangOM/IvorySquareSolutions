# Free Cash Flow to the Firm and Free Cash Flow to Equity

## Core Idea

Free cash flow measures the cash a business generates after funding the investments needed to sustain and grow operations. Two variants serve different analytical purposes:

**FCFF (Free Cash Flow to the Firm)** represents cash available to *all* capital providers — both debt holders and equity holders — before any financing payments are made.

**FCFE (Free Cash Flow to Equity)** represents cash available to *equity holders only*, after debt obligations (interest and net borrowing) have been settled.

The distinction matters because FCFF is capital-structure-neutral, making it the right input for enterprise valuation, while FCFE feeds directly into equity valuation models.

---

## Canonical Formulas

Starting from net income:

```
FCFF = NI + NCC + Int(1 - t) - FCInv - WCInv

FCFE = NI + NCC - FCInv - WCInv + Net Borrowing
```

Where:

```
NI          = Net Income
NCC         = Non-cash charges (e.g., depreciation, amortization)
Int(1 - t)  = After-tax interest expense added back
FCInv       = Fixed capital investment (capex net of asset sale proceeds)
WCInv       = Working capital investment (change in non-cash working capital)
Net Borrow  = New debt issued minus debt repaid
```

A quick bridge between the two:

```
FCFE = FCFF - Int(1 - t) + Net Borrowing
```

This bridge makes the relationship explicit: moving from the firm level to the equity level strips out the debt-holder claim and adds back any new net financing from lenders.

---

## Worked ASCII Example

```
Net Income              =  800
+ Depreciation          =  150
+ Interest × (1 - 0.30) =   70   [Interest = 100, tax rate = 30%]
- Capital Expenditures  = (300)
- ΔWorking Capital      =  (50)
─────────────────────────────
FCFF                    =  670

- Interest × (1 - 0.30) =  (70)
+ Net Borrowing         =  120
─────────────────────────────
FCFE                    =  720
```

---

## Why Deterministic Reference Matters

Because FCFF and FCFE feed directly into discounted cash flow models, every input must resolve to a single, reproducible number given the same financial statements. Ambiguity in definitions — for example, whether to include short-term debt changes in net borrowing — produces different valuations from identical data. A closed-form, agreed-upon definition eliminates that variance and makes model outputs auditable and comparable across analysts.

---

## Prereqs

- **Income statement structure** — understanding net income and its components
- **Capital expenditure and depreciation concepts** — distinguishing cash from non-cash charges
- **Working capital mechanics** — computing changes in operating current accounts
- **Tax shield on interest** — after-tax cost of debt logic
- **Enterprise value vs. equity value** — why capital structure affects which cash flow is relevant
