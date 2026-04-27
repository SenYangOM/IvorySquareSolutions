# Deferred Tax Basics

## Core Idea

A deferred tax item arises whenever the amount of income a company reports on its **financial statements** differs from the amount it reports on its **tax return** in the same period. Because these two sets of rules—GAAP and the Internal Revenue Code—treat certain revenues and expenses differently, a timing gap opens up. That gap creates either a future tax obligation or a future tax benefit, recorded on the balance sheet as a **deferred tax liability (DTL)** or a **deferred tax asset (DTA)**.

- **Deferred Tax Liability** — taxable income will be *higher* in a future period than book income (you owe more tax later).  
- **Deferred Tax Asset** — taxable income will be *lower* in a future period than book income (you save tax later).

## The Mechanics

The calculation is straightforward once you know the **temporary difference** and the **enacted future tax rate**:

```
Temporary Difference  =  Book Basis  −  Tax Basis
                                  (of an asset or liability)

Deferred Tax Amount   =  Temporary Difference  ×  Enacted Tax Rate

Sign convention
───────────────
Asset  basis  >  Tax  basis  →  future deductible  →  DTA
Tax    basis  >  Asset basis  →  future taxable     →  DTL
```

### Worked Example

A company buys equipment for $100,000. For books it uses straight-line depreciation (5 years, $20,000/yr). For taxes it uses MACRS and deducts $33,000 in Year 1.

```
                    Book     Tax
Gross cost        100,000  100,000
Year-1 depr.      (20,000) (33,000)
                  ───────  ───────
Ending basis       80,000   67,000

Temporary difference = 80,000 − 67,000 = 13,000  (excess book basis)
Tax rate = 21%
DTL = 13,000 × 0.21 = $2,730
```

The company will owe *more* tax in future years when MACRS deductions shrink, so a DTL is recorded now.

## Why Determinism Matters Here

Deferred tax amounts are **closed-form**: given a temporary difference and an enacted rate, the balance sheet figure is uniquely determined with no estimation. This makes the calculation auditable and reproducible—any two preparers with the same inputs must reach the same number. A precise reference standard prevents the silent introduction of judgment where none is warranted.

## Prereqs

- **Accrual basis accounting** — understanding that revenues and expenses are recognized when earned/incurred, not when cash moves
- **Income tax expense vs. taxes payable** — distinguishing the GAAP expense line from the actual tax owed to the government
- **Temporary vs. permanent differences** — knowing which book-tax gaps reverse over time and which never do
- **Enacted tax rate concept** — using the rate already signed into law for future-period calculations
