# Bayes' rule

Bayes' rule inverts a conditional probability — given the likelihood
`P(B | A)` and prior `P(A)`, it computes the posterior `P(A | B)`.

## Formula

For events `A` and `B` with `P(B) > 0`:

    P(A | B) = P(B | A) * P(A) / P(B)

When `A` is one of mutually exclusive partition events `A_1, ..., A_n`:

    P(A_k | B) = P(B | A_k) * P(A_k) / sum_i [ P(B | A_i) * P(A_i) ]

The denominator is the *total probability of B*, computed via the law
of total probability.

## Worked example (medical test)

Suppose a disease has prevalence `P(D) = 0.01`. A test has sensitivity
`P(+ | D) = 0.99` and specificity `P(- | not D) = 0.95` (so false-
positive rate is 0.05).

A patient tests positive. What is `P(D | +)`?

    P(+) = P(+ | D) P(D) + P(+ | not D) P(not D)
         = 0.99 * 0.01 + 0.05 * 0.99
         = 0.0099 + 0.0495
         = 0.0594

    P(D | +) = P(+ | D) P(D) / P(+)
             = 0.0099 / 0.0594
             ≈ 0.1667 = 16.67%

The base-rate fallacy: even with a sensitive test, a positive result is
~83% false-positive when the disease is rare.

## Why code-backed

Bayes-rule computations are particularly prone to LLM arithmetic
errors:

- Confusing `P(B | A)` with `P(A | B)` (the inversion the formula
  exists to do).
- Dropping the marginalization over the partition events when computing
  `P(B)`.
- Numerical errors when probabilities are very small or differ by
  orders of magnitude.

The code reference in `code/bayes.py` makes the computation
deterministic and exposes the partition mechanics explicitly.
