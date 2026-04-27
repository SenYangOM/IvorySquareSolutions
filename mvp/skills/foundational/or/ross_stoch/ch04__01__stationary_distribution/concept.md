# Stationary distribution of a Markov chain

A *stationary distribution* of a discrete-time Markov chain with
transition matrix `P` is a probability vector `pi` satisfying

    pi P = pi          (left eigenvector with eigenvalue 1)
    sum_i pi_i = 1
    pi_i >= 0

Equivalently, `pi^T = pi^T P`. The chain "looks the same" at every
future time when started from `pi`.

## Existence and uniqueness

For an *irreducible aperiodic* finite chain (also called *ergodic*):

- A stationary distribution exists.
- It is unique.
- The n-step transition probabilities converge to it: for every `i, j`,
  `P^n[i, j] → pi_j` as `n → ∞`.

For periodic chains the long-run averages still converge to `pi`, but
the n-step matrix oscillates.

For reducible chains, multiple stationary distributions can exist (one
per recurrent class), and the limiting distribution depends on the
starting state.

## Solving for `pi`

Solve the linear system

    pi (P - I) = 0
    sum_i pi_i = 1

Equivalently: pick any `n - 1` of the `n` balance equations, replace
one with the normalization constraint, and solve. For a 2-state chain
with transition probabilities `p` and `q`:

    pi_0 = q / (p + q)
    pi_1 = p / (p + q)

For larger chains, solve via matrix inversion or eigenvector extraction.

## Worked example

Two-state weather chain with `P = [[0.9, 0.1], [0.5, 0.5]]`:

    pi_0 = 0.5 / (0.1 + 0.5) = 5/6 ≈ 0.833
    pi_1 = 0.1 / (0.1 + 0.5) = 1/6 ≈ 0.167

Verify: `[5/6, 1/6] · P = [5/6 * 0.9 + 1/6 * 0.5, 5/6 * 0.1 + 1/6 * 0.5]`
`= [0.75 + 0.0833, 0.0833 + 0.0833]` = `[0.833, 0.167]` ✓

## Why code-backed

Solving for the stationary distribution is a linear-algebra closed
form. An LLM can state the conditions correctly but routinely
miscompute eigenvectors of larger matrices. The code reference in
`code/stationary.py` solves the system deterministically.
