# Deferred Tax Valuation Allowance

## Core Idea

A deferred tax asset (DTA) represents future tax savings — but only if the company will actually have taxable income to absorb them. When it is **more likely than not** (probability > 50 %) that some or all of a DTA will not be realized, a **valuation allowance** must be recorded to reduce the DTA to its expected recoverable amount. The allowance is a contra-asset that sits directly against the gross DTA on the balance sheet.

## Why It Exists

Deferred tax assets arise from temporary differences and carryforwards (e.g., net operating loss carryforwards). A company with a history of losses or insufficient future taxable income projections cannot guarantee it will use those assets. The valuation allowance enforces conservatism: report only what is realistically collectible.

## Closed-Form Calculation

```
Gross DTA                          $120,000
Less: Valuation Allowance          ( 45,000)
                                  ----------
Net DTA (balance sheet)            $ 75,000
```

**Step-by-step logic:**

1. Identify gross DTA from all sources.
2. Assess available positive evidence (future reversals, tax-planning strategies, projected taxable income) vs. negative evidence (cumulative losses, expiring carryforwards).
3. Estimate the portion that is **more likely than not** to go unrealized → that amount becomes the allowance.
4. Record the entry:

```
Dr  Income Tax Expense        45,000
    Cr  Valuation Allowance       45,000
```

If conditions improve in a later period, the allowance is **reversed**, reducing tax expense:

```
Dr  Valuation Allowance       20,000
    Cr  Income Tax Expense        20,000
```

## Deterministic Reference Matters Here

Because the valuation allowance directly feeds into reported net income and the effective tax rate, the calculation must be **reproducible and auditable**. A deterministic reference — a fixed, step-by-step procedure tied to the "more likely than not" threshold — ensures that two preparers working from the same evidence reach the same allowance amount. Ambiguity in this computation would create material misstatements and audit findings. The closed-form nature (threshold → estimate → journal entry) makes it possible to verify, challenge, and reperform the figure without subjective drift.

## Key Judgment Factors

- Cumulative pre-tax losses in recent years (strong negative evidence)
- Existence of taxable temporary differences that will reverse in time to absorb the DTA
- Feasibility of tax-planning strategies
- Length of carryforward periods before expiration

## Prereqs

- **Deferred Tax Assets and Liabilities** — understanding how temporary differences create DTAs
- **Temporary vs. Permanent Differences** — distinguishing items that generate DTAs from those that do not
- **Net Operating Loss Carryforwards** — primary source of large DTAs requiring allowance analysis
- **Income Tax Expense Presentation** — how the allowance flows through the income statement
