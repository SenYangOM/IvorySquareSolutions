# Multistage Dividend Discount Model

## Core Idea

The **multistage dividend discount model (DDM)** values a stock by recognizing that dividend growth rarely stays constant forever. Instead, a firm typically passes through distinct phases — an early high-growth period, a transitional period, and a mature steady-state period. The model prices each phase separately, then sums all present values into a single intrinsic value estimate.

Because every cash flow and discount step follows arithmetic rules with no randomness, the output is **closed-form deterministic**: given fixed inputs, the answer is always the same. This makes a precise, reproducible reference essential for exam and professional settings.

---

## Two-Stage Example

Suppose a stock just paid a dividend D₀ = $2.00. Growth is 15% for years 1–3, then drops permanently to 4%. The required return r = 10%.

**Step 1 — Forecast high-growth dividends**

```
Year  Growth  Dividend
  1    15%    2.00 × 1.15 = $2.30
  2    15%    2.30 × 1.15 = $2.645
  3    15%    2.645 × 1.15 = $3.042
```

**Step 2 — Terminal value at end of Year 3 (Gordon Growth)**

```
TV₃ = D₄ / (r − g)
    = (3.042 × 1.04) / (0.10 − 0.04)
    = 3.164 / 0.06
    = $52.73
```

**Step 3 — Discount everything to today**

```
PV = 2.30/1.10¹ + 2.645/1.10² + 3.042/1.10³ + 52.73/1.10³
   = 2.09  +  2.19  +  2.28  +  39.60
   ≈ $46.16
```

The intrinsic value is **$46.16 per share**.

---

## Why Closed-Form Determinism Matters

Each arithmetic step — compounding dividends, applying the Gordon Growth formula, discounting — produces an exact number. There is no simulation or estimation involved. A deterministic reference page lets practitioners and students verify every intermediate result, catch input errors early, and reproduce the valuation identically across contexts. Ambiguity in any single step propagates into a wrong final price, so precision at each stage is non-negotiable.

---

## Three-Stage Extension

For firms with a longer transition, a linear "fade" in growth rates between Stage 1 and Stage 3 is modeled year by year, with each dividend discounted individually before adding the terminal value. The logic is identical; only the number of rows in the table grows.

---

## Prereqs

- **Gordon Growth Model** — supplies the terminal value formula used at the boundary between stages
- **Time Value of Money** — present-value discounting of each dividend and the terminal value
- **Required Rate of Return (CAPM or build-up)** — determines the discount rate r
- **Dividend Payout and Retention** — explains how growth rates are derived from ROE and plowback ratio
