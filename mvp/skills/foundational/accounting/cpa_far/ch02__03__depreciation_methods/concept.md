# Depreciation methods

Depreciation allocates the capitalized cost of a long-lived tangible
asset (PP&E) over its useful life. The depreciation method determines
the *time pattern* of expense; total depreciation over the asset's life
equals the depreciable base regardless of method.

## Common methods

For an asset with cost `C`, salvage value `S`, useful life `n` years:

- **Straight-line:**

      Depreciation_t = (C - S) / n     for t = 1, ..., n

  Constant per-period expense.

- **Units of production:**

      Depreciation_t = (C - S) * (units_used_t / total_units)

  Tied to actual usage; matches expense to consumption.

- **Double-declining balance (DDB), an accelerated method:**

      Rate = 2 / n
      Depreciation_t = Rate * (Book value at start of period t)

  Stops once book value reaches salvage value. Front-loads expense.

- **Sum-of-the-years-digits (SYD):**

      SYD denominator = n(n+1)/2
      Depreciation_t = (n - t + 1) / SYD * (C - S)

  Front-loads expense like DDB but smoother decline.

## Worked example

`C = 10000`, `S = 1000`, `n = 5`:

Straight-line: `(10000 - 1000) / 5 = 1800` per year.

DDB rate `= 2 / 5 = 0.40`:

    Year 1: 0.40 * 10000 = 4000  → book value 6000
    Year 2: 0.40 * 6000  = 2400  → book value 3600
    Year 3: 0.40 * 3600  = 1440  → book value 2160
    Year 4: book value would drop below salvage 1000; cap at 1160.
    Year 5: zero (book value already at salvage).

SYD denominator `= 15`:

    Year 1: 5/15 * 9000 = 3000
    Year 2: 4/15 * 9000 = 2400
    Year 3: 3/15 * 9000 = 1800
    Year 4: 2/15 * 9000 = 1200
    Year 5: 1/15 * 9000 =  600

## Tax vs. book

US tax depreciation uses MACRS (Modified Accelerated Cost Recovery
System), which is a separate set of class-life-based schedules with
half-year, mid-quarter, or mid-month conventions. Book depreciation
under GAAP uses one of the methods above. Differences between book and
tax depreciation are a major source of *deferred tax* balances.

## Why code-backed

Each method has a closed-form schedule but the per-year arithmetic is
exactly where LLMs off-by-arithmetic — especially under DDB where the
salvage cap interacts with the doubled rate. The code reference in
`code/depreciation.py` produces a deterministic per-year schedule and
caps book value at salvage automatically.
