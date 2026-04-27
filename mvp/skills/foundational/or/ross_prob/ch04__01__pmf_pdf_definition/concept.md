# PMFs, PDFs, and CDFs

Random variables come in two flavours, each with its own characterizing
function:

- **Discrete** random variables take values in a countable set; their
  distribution is described by a *probability mass function* (PMF).
- **Continuous** random variables take values in an uncountable set
  (typically an interval of `R`); their distribution is described by a
  *probability density function* (PDF).

Both share a common cumulative description: the *cumulative
distribution function* (CDF).

## Probability mass function (PMF)

For a discrete random variable `X`:

    p(x) = P(X = x)
    sum_x p(x) = 1
    p(x) >= 0

Example: a fair die has PMF `p(k) = 1/6` for `k = 1, ..., 6`.

## Probability density function (PDF)

For a continuous random variable `X`:

    f(x) >= 0
    integral over all R of f(x) dx = 1

Crucially, `f(x)` is NOT a probability — `P(X = x) = 0` for any single
point. Probabilities come from integrating:

    P(a <= X <= b) = integral from a to b of f(x) dx

Example: the uniform distribution on `[0, 1]` has PDF `f(x) = 1` for
`x in [0, 1]`, zero otherwise.

## Cumulative distribution function (CDF)

For any random variable:

    F(x) = P(X <= x)

Properties of every CDF:

- Nondecreasing.
- `F(-infinity) = 0`, `F(+infinity) = 1`.
- Right-continuous.

For a continuous variable, `F(x) = integral from -infinity to x of f(t) dt`,
and `f(x) = F'(x)` where `F` is differentiable.

For a discrete variable, `F` is a step function with jumps `p(x_k)` at
each support point.

## Worked example

Exponential distribution with rate `lambda`:

    f(x) = lambda * e^{-lambda x}    for x >= 0
    F(x) = 1 - e^{-lambda x}          for x >= 0

Compute `P(0 <= X <= 1)` for `lambda = 0.5`:

    F(1) - F(0) = (1 - e^{-0.5}) - 0 = 1 - 0.6065 = 0.3935

## Why markdown-only (conceptual_high_value)

The bare LLM correctly distinguishes PMF / PDF / CDF the vast majority
of the time. The foundational skill's value is curating the canonical
definitions and surfacing the common gotcha that `f(x)` is a density,
not a probability.
