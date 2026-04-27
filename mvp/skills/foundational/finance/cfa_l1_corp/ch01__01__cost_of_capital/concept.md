# Cost of Capital

## Core Idea

The **cost of capital** is the minimum rate of return a firm must earn on its investments to satisfy all providers of funds — debt holders, preferred shareholders, and common equity holders. Think of it as the "price tag" attached to every dollar the firm deploys: if a project earns less than this hurdle, it destroys value even if it generates positive cash flows.

Because a firm typically draws from multiple funding sources simultaneously, the relevant measure is the **Weighted Average Cost of Capital (WACC)**, which blends each component's cost in proportion to its share of the total capital structure.

## The Three Components

| Component | Symbol | What It Represents |
|-----------|--------|--------------------|
| Cost of Debt | k_d | After-tax yield demanded by lenders |
| Cost of Preferred Stock | k_p | Dividend yield required by preferred holders |
| Cost of Equity | k_e | Return demanded by common shareholders |

## WACC Formula

```
WACC = w_d · k_d · (1 - t)  +  w_p · k_p  +  w_e · k_e

where:
  w_d, w_p, w_e = market-value weights of debt, preferred, equity
  t             = marginal corporate tax rate
  w_d + w_p + w_e = 1.0
```

Debt receives a tax shield — interest is deductible — so its effective cost is scaled by `(1 - t)`. Preferred and equity carry no such shield.

## Worked Example

```
Capital structure (market values):
  Debt          $400M   w_d = 0.40
  Preferred      $50M   w_p = 0.05
  Common equity $550M   w_e = 0.55

Rates:
  k_d = 6%,  t = 25%,  k_p = 5%,  k_e = 11%

WACC = 0.40 × 6% × (1 - 0.25)
     + 0.05 × 5%
     + 0.55 × 11%

     = 0.40 × 4.50%  +  0.05 × 5.00%  +  0.55 × 11.00%
     = 1.80%         +  0.25%          +  6.05%
     = 8.10%
```

Any project returning above 8.10% adds firm value; below it destroys value.

## Why Deterministic Reference Matters

WACC is a **closed-form calculation**: given fixed inputs, it yields one unambiguous number. Analysts, auditors, and regulators rely on this reproducibility to benchmark capital budgeting decisions, value businesses, and assess economic profit. A precise, formula-driven definition prevents subjective drift and ensures that every stakeholder is pricing capital on the same basis.

## Prereqs

- Time value of money (present value, discount rates)
- Basic corporate balance sheet structure (debt vs. equity)
- Concept of marginal tax rate and interest tax shield
- Market value vs. book value of capital components
