# ASC 842 Lessee Classification: Finance vs. Operating

## Core Idea

Under ASC 842, every lessee lease is classified as either a **finance lease** or an **operating lease** at commencement. The classification drives how expenses appear on the income statement and how the right-of-use (ROU) asset amortizes over time. A lease is a finance lease if **any one** of five criteria is met; otherwise it defaults to operating.

## The Five Finance Lease Criteria

| # | Criterion | Common Shorthand |
|---|-----------|-----------------|
| 1 | Ownership transfers to lessee by end of lease | Transfer of title |
| 2 | Lessee holds a purchase option it is **reasonably certain** to exercise | Bargain purchase |
| 3 | Lease term covers **major part** of remaining economic life (≥ 75% is a bright-line guide) | Economic life |
| 4 | Present value of lease payments equals **substantially all** of fair value (≥ 90% guide) | PV test |
| 5 | Asset is so specialized it has **no alternative use** to the lessor at end of term | Specialized asset |

If none of the five apply, the lease is an **operating lease**.

## Income Statement Effect — ASCII Snapshot

```
FINANCE LEASE                    OPERATING LEASE
─────────────────────────────    ─────────────────────────────
Interest expense  (on liability) Single straight-line
+ Amortization    (on ROU asset) lease cost
= Front-loaded total expense     = Level total expense
```

Finance leases produce higher expense early in the term because interest is largest when the liability balance is highest. Operating leases spread a single lease cost evenly, keeping the income statement pattern flat.

## Balance Sheet — Both Types

Both classifications put an ROU asset and a lease liability on the balance sheet. The difference is **presentation and amortization method**, not recognition itself. Finance lease ROU assets are amortized separately (usually straight-line over the shorter of lease term or useful life), while operating lease ROU assets are reduced by the plug needed to keep total lease cost straight-line.

## Why a Deterministic Reference Matters

Classification is a closed-form decision tree: evaluate each criterion in order, stop at the first "yes." Because the outcome is fully determined by measurable inputs (lease term, asset life, PV of payments, fair value), a precise reference prevents inconsistent judgment calls across similar contracts and supports audit defensibility.

## Prereqs

- **Present value of an annuity** — needed to apply the 90% PV test
- **Right-of-use asset and lease liability recognition** — establishes what is being classified
- **Lease term determination under ASC 842** — lease term feeds directly into criteria 3 and 4
- **Lessee vs. lessor scope** — confirms which party applies these criteria
