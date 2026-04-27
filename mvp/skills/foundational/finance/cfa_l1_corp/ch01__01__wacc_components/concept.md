# WACC Components

## Core Idea

The **weighted average cost of capital (WACC)** answers a single question: what return must a firm earn on its existing assets to satisfy every provider of capital? Each financing source — common equity, preferred equity, and debt — carries its own required return. WACC blends those returns into one hurdle rate by weighting each source according to its share of the firm's total capital structure.

The general formula is:

```
WACC = w_d · r_d · (1 − t)  +  w_p · r_p  +  w_e · r_e

where:
  w_d  = weight of debt          (market-value basis)
  r_d  = pre-tax cost of debt
  t    = marginal corporate tax rate
  w_p  = weight of preferred equity
  r_p  = cost of preferred equity
  w_e  = weight of common equity
  r_e  = cost of common equity

  w_d + w_p + w_e = 1.0
```

The `(1 − t)` term on debt reflects the **interest tax shield**: because interest is deductible, the government effectively subsidises part of the debt cost.

## Worked Example

A firm's capital structure at market values:

```
Source          Market Value   Weight   Cost    After-tax Cost
─────────────────────────────────────────────────────────────
Debt            $400           0.40     6.0%    6.0% × (1−0.25) = 4.50%
Preferred       $100           0.10     5.5%    5.50%
Common equity   $500           0.50     11.0%   11.00%
─────────────────────────────────────────────────────────────
Total           $1,000         1.00

WACC = 0.40 × 4.50%  +  0.10 × 5.50%  +  0.50 × 11.00%
     = 1.80%  +  0.55%  +  5.50%
     = 7.85%
```

The firm must generate at least **7.85%** on invested capital to leave all capital providers no worse off.

## Why a Closed-Form Reference Matters

WACC feeds directly into discounted cash flow valuation and capital budgeting accept/reject decisions. A one-percentage-point error in any component propagates multiplicatively through every projected period. Because the formula is deterministic — given weights, costs, and a tax rate, the answer is exact — there is no room for interpretive drift. Pinning down each component precisely before combining them prevents compounding errors that would silently distort project rankings or firm valuations.

## Prereqs

- **Time value of money** — understanding discounting and why future cash flows must be adjusted
- **Capital structure overview** — distinguishing debt, preferred equity, and common equity on the balance sheet
- **Marginal tax rate concept** — knowing why the marginal (not average) rate applies to the interest tax shield
- **Market vs. book value** — recognising that weights must reflect current market values, not historical accounting figures
