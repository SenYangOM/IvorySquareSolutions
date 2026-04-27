# Pension Obligations in Defined Benefit Plans

## Core Idea

A defined benefit (DB) pension plan promises employees a specific retirement payment, typically based on years of service and final salary. Because the employer bears the investment risk, the plan creates a measurable liability on the employer's books. Three obligation measures capture different slices of that liability:

| Measure | Abbreviation | What It Counts |
|---|---|---|
| Accumulated Benefit Obligation | ABO | Benefits earned to date using **current** salary |
| Projected Benefit Obligation | PBO | Benefits earned to date using **projected future** salary |
| Vested Benefit Obligation | VBO | Portion of ABO that employees could keep if they quit today |

For financial reporting under US GAAP, the **PBO** is the authoritative measure. The funded status reported on the balance sheet equals plan assets minus PBO.

## Worked Example

Assume an employee will earn a $1,200/month pension at retirement. The actuary estimates:

```
Projected monthly benefit at retirement  : $1,200
Years of total expected service          : 30
Years of service completed               : 10
Discount rate (annual)                   : 5%
Years until retirement                   : 20

Attribution fraction = 10 / 30 = 0.3333

Benefit attributed to date = $1,200 × 0.3333 = $400/month

Present value factor (annuity, 5%, 20 yrs to discount) applied
to the attributed benefit stream yields the PBO component.
```

The key insight: only the **attributed portion** (one-third here) enters the PBO today. As service years accumulate, the attributed fraction grows, increasing the PBO each period through **service cost**.

## Components That Move the PBO

```
Beginning PBO
  + Service cost          (new benefits earned this year)
  + Interest cost         (PBO × discount rate)
  + Actuarial (gains)/losses
  - Benefits paid
= Ending PBO
```

Each line item feeds directly into net periodic pension cost, making the PBO calculation a closed-form, deterministic chain: given actuarial assumptions, every component is computable without ambiguity. This is why a precise reference definition matters — small changes in discount rate or salary growth assumption produce materially different liability figures, and auditors must trace each input to a documented, reproducible formula.

## Prereqs

- **Time value of money** — present value and annuity discounting underlie PBO measurement
- **Actuarial assumptions** — discount rate, salary growth rate, and mortality tables drive the projection
- **Employee benefit plan basics** — distinction between defined benefit and defined contribution structures
- **Balance sheet fundamentals** — understanding assets, liabilities, and funded status presentation
