# Bond Premium and Discount Amortization

## Core Idea

When a bond is issued, the stated (coupon) rate rarely equals the market (effective) rate. The difference creates either a **premium** (issue price > face value, coupon > market rate) or a **discount** (issue price < face value, coupon < market rate). Over the bond's life, this difference must be systematically eliminated so that the carrying amount converges to face value at maturity. The preferred method under U.S. GAAP is the **effective-interest method**, which produces a constant periodic interest rate applied to a changing carrying amount.

## Effective-Interest Method Formula

For each period:

```
Interest Expense  = Carrying Amount (beg) × Effective Rate
Cash Paid         = Face Value × Coupon Rate
Amortization      = Interest Expense − Cash Paid

  Discount:  Interest Expense > Cash Paid  →  amortization increases carrying amount
  Premium:   Interest Expense < Cash Paid  →  amortization decreases carrying amount
```

### Worked Example — Discount Bond

A company issues a $100,000, 5-year bond with a 6% annual coupon when the market rate is 8%. The issue price is $92,015.

```
Period | Beg. Carrying | Interest Exp (×8%) | Cash Paid (×6%) | Amortization | End Carrying
  1    |   92,015      |     7,361           |    6,000        |    1,361     |   93,376
  2    |   93,376      |     7,470           |    6,000        |    1,470     |   94,846
  3    |   94,846      |     7,588           |    6,000        |    1,588     |   96,434
  4    |   96,434      |     7,715           |    6,000        |    1,715     |   98,149
  5    |   98,149      |     7,851*          |    6,000        |    1,851     |  100,000
  (* adjusted for rounding)
```

Each period, the discount balance shrinks and the carrying amount climbs toward $100,000.

## Journal Entry Pattern (Discount)

```
Dr. Interest Expense      7,361
    Cr. Cash                       6,000
    Cr. Discount on Bonds Payable  1,361
```

For a premium, the debit to **Premium on Bonds Payable** reduces the contra-liability balance each period.

## Why Deterministic Reference Matters

Because the amortization schedule is fully determined by three inputs—issue price, coupon rate, and effective rate—every future carrying amount and interest expense figure is calculable without judgment. A closed-form reference table locks in these values, preventing period-to-period inconsistency and ensuring that the carrying amount reaches exactly face value at maturity, a requirement for both financial reporting accuracy and exam reproducibility.

## Prereqs

- Time value of money (present value of annuity and lump sum)
- Bond pricing mechanics (stated vs. effective rate relationship)
- Contra-liability account structure (discount and premium accounts)
- Basic journal entry construction
