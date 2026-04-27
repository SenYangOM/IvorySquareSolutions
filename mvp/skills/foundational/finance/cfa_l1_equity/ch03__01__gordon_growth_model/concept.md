# Gordon growth model

The Gordon growth model values an equity claim that pays a perpetual,
constantly-growing dividend stream. It is the simplest dividend
discount model.

## Formula

For a stock paying dividend `D_1` next period, growing at a constant
rate `g` forever, with required return `r`:

    P_0 = D_1 / (r - g)        valid only when g < r

`D_1 = D_0 * (1 + g)` if you have the current dividend `D_0` rather
than the next-period dividend.

## Assumptions

- Dividends grow at a constant rate `g` forever.
- The required return `r` is constant and exceeds `g`.
- Dividends are the relevant cash flow.

## Worked example

A stock just paid `D_0 = 2.00`; dividend growth `g = 4%`; required
return `r = 9%`.

    D_1 = 2.00 * 1.04 = 2.08
    P_0 = 2.08 / (0.09 - 0.04) = 2.08 / 0.05 = 41.60

## Limitations

- Fails when `g >= r` (price diverges).
- A single growth rate is rarely realistic; multi-stage variants chain
  high-growth and steady-state phases.
- Sensitive to small changes in `r` and `g`; the denominator amplifies.

## Why code-backed

Even simple Gordon-model arithmetic gets miscomputed when an LLM
arithmetics the wrong dividend (D_0 vs D_1) or denominator (r minus g
vs r plus g). The code reference in `code/gordon.py` removes the
ambiguity.
