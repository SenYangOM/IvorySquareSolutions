# Karush-Kuhn-Tucker (KKT) conditions

The KKT conditions characterize optimality for an inequality- and
equality-constrained problem. For a convex problem satisfying a
constraint qualification (e.g., Slater's condition), KKT is both
necessary and sufficient.

## The problem

Minimize `f(x)` subject to:

    g_i(x) <= 0      for i = 1, ..., m
    h_j(x) = 0       for j = 1, ..., p

with `f` and each `g_i` convex, each `h_j` affine.

## The Lagrangian

    L(x, mu, nu) = f(x) + sum_i mu_i g_i(x) + sum_j nu_j h_j(x)

`mu_i >= 0` are Lagrange multipliers on the inequality constraints;
`nu_j` (unrestricted in sign) are multipliers on the equality
constraints.

## KKT conditions

For convex problems, the KKT conditions at a candidate `(x*, mu*, nu*)`
are:

1. **Primal feasibility:** `g_i(x*) <= 0`, `h_j(x*) = 0`.
2. **Dual feasibility:** `mu*_i >= 0`.
3. **Complementary slackness:** `mu*_i * g_i(x*) = 0`.
4. **Stationarity:** `grad_x L(x*, mu*, nu*) = 0`, equivalently:
   `grad f(x*) + sum_i mu*_i grad g_i(x*) + sum_j nu*_j grad h_j(x*) = 0`.

## Worked example

Minimize `f(x) = x^2`  subject to  `x >= 1`  (i.e., `g(x) = 1 - x <= 0`).

    L(x, mu) = x^2 + mu (1 - x)
    Stationarity:  2x - mu = 0  ⇒  x = mu / 2
    Complementary slackness:  mu * (1 - x) = 0
        Case A: mu = 0  ⇒  x = 0, but g(0) = 1 > 0 violates feasibility.
        Case B: x = 1  ⇒  mu = 2, dual feasible.
    KKT pair: (x*, mu*) = (1, 2). Optimal value 1.

## Why code-backed

KKT residual checks involve coupled dot products and sign tests; an
LLM may cleanly state the four conditions but routinely off-by-arithmetic
when *evaluating* the residual on a specific candidate. The code
reference in `code/kkt.py` evaluates the residual deterministically.
