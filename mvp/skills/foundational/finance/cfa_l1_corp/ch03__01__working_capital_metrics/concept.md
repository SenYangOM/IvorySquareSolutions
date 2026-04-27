# Working Capital Metrics: Cash Conversion Cycle

## Core Idea

The **cash conversion cycle (CCC)** measures how many days a firm's cash is tied up in the operating cycle before it is recovered through collections. A shorter CCC means the business converts its investments in inventory and receivables into cash more quickly, reducing the need for external financing.

The cycle has three moving parts:

| Component | Abbreviation | What It Measures |
|---|---|---|
| Days Inventory Outstanding | DIO | Days to sell inventory |
| Days Sales Outstanding | DSO | Days to collect receivables |
| Days Payable Outstanding | DPO | Days to pay suppliers |

## Formula

```
CCC  =  DIO  +  DSO  −  DPO

        Inventory          Receivables        Payables
DIO = ─────────────  DSO = ───────────  DPO = ──────────
       COGS / 365          Revenue / 365      COGS / 365
```

DPO is **subtracted** because supplier credit offsets the cash the firm must fund itself.

## Worked Example

A manufacturer reports (in $ millions):

```
Inventory    =  40      Revenue  =  300
Receivables  =  30      COGS     =  240
Payables     =  20      Days in period = 365
```

Step-by-step:

```
DIO = 40 / (240/365) = 40 / 0.658 ≈ 60.8 days
DSO = 30 / (300/365) = 30 / 0.822 ≈ 36.5 days
DPO = 20 / (240/365) = 20 / 0.658 ≈ 30.4 days

CCC = 60.8 + 36.5 − 30.4 = 66.9 days
```

The firm needs roughly **67 days** of self-funded working capital for each operating cycle. Reducing DIO or DSO, or extending DPO (within supplier terms), directly compresses the CCC and frees cash.

## Why Deterministic Reference Matters

Because CCC is a **closed-form calculation**, every analyst using the same financial statement inputs must arrive at the identical number. There is no estimation or model risk. This makes CCC a reliable benchmark for comparing firms across periods or against industry peers — but only when the denominator convention (revenue vs. COGS, 365 vs. 360 days) is applied consistently. IvorySquare standardizes on COGS-based denominators for inventory and payables, and revenue-based for receivables, matching common CFA Institute practice.

## Prereqs

- **Liquidity ratios** — understanding current and quick ratios as baseline working-capital measures
- **Income statement structure** — distinguishing revenue from cost of goods sold
- **Balance sheet components** — identifying inventory, trade receivables, and trade payables line items
- **Time-value intuition** — recognizing why faster cash recovery has economic value
