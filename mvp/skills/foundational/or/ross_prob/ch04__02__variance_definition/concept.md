# Variance and standard deviation

Variance measures the dispersion of a random variable around its mean.
It is the second central moment, and the standard deviation is its
positive square root.

## Definitions

For a random variable `X` with finite mean `mu = E[X]`:

    Var(X) = E[(X - mu)^2]
           = E[X^2] - (E[X])^2

The second form is convenient computationally: compute `E[X^2]` and
`E[X]^2` separately, then subtract.

The standard deviation is `sigma_X = sqrt(Var(X))`. Standard deviation
shares the units of `X`; variance has squared units.

## Sample variance

For a sample `x_1, ..., x_n` with sample mean `xbar = sum(x_i) / n`,
the *sample variance* with Bessel's correction is

    s^2 = sum (x_i - xbar)^2 / (n - 1)

Without Bessel's correction (`n` in denominator) the estimator is the
maximum-likelihood estimator under normality but is biased downward.

## Properties

- Variance is nonnegative: `Var(X) >= 0`, with equality iff `X` is
  almost surely constant.
- For independent `X` and `Y`: `Var(X + Y) = Var(X) + Var(Y)`.
- For any constants `a, b`: `Var(aX + b) = a^2 Var(X)`.
- Variance is NOT linear: `Var(X + Y)` requires the covariance term in
  general.

## Worked example

Discrete random variable `X` taking values `1, 2, 3, 4` each with
probability `1/4`:

    E[X]    = (1 + 2 + 3 + 4) / 4 = 2.5
    E[X^2]  = (1 + 4 + 9 + 16) / 4 = 7.5
    Var(X)  = 7.5 - 2.5^2 = 7.5 - 6.25 = 1.25
    sd(X)   = sqrt(1.25) ≈ 1.118

## Why code-backed

Variance computation off-by-arithmetics in two distinct ways: dropping
the Bessel correction when it should be applied, and subtracting the
mean before squaring instead of after. The code reference in
`code/variance.py` makes both choices explicit.
