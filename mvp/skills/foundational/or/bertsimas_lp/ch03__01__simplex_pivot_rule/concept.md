# Simplex pivot and reduced cost

The simplex method walks vertices of the feasible polyhedron of a
linear program in standard form, swapping one basic variable for one
nonbasic variable at each step. The swap is a "pivot." The rules that
pick the entering and leaving variables determine both correctness and
termination.

## Setup

Take an LP in standard form:

    minimize    c^T x
    subject to  A x = b
                x >= 0

with `A` an `m x n` matrix of full row rank `m < n`. A *basic feasible
solution* (BFS) splits the variables into `m` basic variables `x_B` and
`n - m` nonbasic variables `x_N`. Setting `x_N = 0` and solving
`B x_B = b` yields the BFS, where `B` is the `m x m` submatrix of `A`
indexed by the basic columns.

## Reduced cost

For a nonbasic column `j`, the *reduced cost* is

    c_bar_j = c_j - c_B^T B^{-1} A_j

where `c_B` is the basic cost vector and `A_j` is column `j` of `A`.
The reduced cost measures how the objective changes per unit increase
in `x_j` while staying feasible (other nonbasics held at zero).

If `c_bar_j >= 0` for every nonbasic `j`, the current BFS is optimal
(this is the optimality criterion for minimization). If at least one
`c_bar_j < 0`, the algorithm picks an entering variable.

## Entering variable

Standard rules:

- **Dantzig's rule (most-negative-reduced-cost):** pick the nonbasic
  `j` minimizing `c_bar_j`. Greedy, fast in practice, can cycle on
  degenerate problems.
- **Bland's rule:** pick the smallest-index nonbasic with negative
  reduced cost. Slower per-step but provably terminating.

## Leaving variable (minimum-ratio test)

Once an entering column `q` is chosen, compute the *direction*

    d = B^{-1} A_q

If every `d_i <= 0`, the LP is unbounded along this edge.

Otherwise, the leaving variable index `p` minimises the ratio test:

    p = argmin_{i : d_i > 0}  (x_B[i] / d_i)

Ties are broken by lex-min or Bland's rule. After the pivot, basic
variable `p` is replaced by entering variable `q`; the basis matrix
updates by replacing column `p` with column `q`.

## Worked example (ASCII diagram)

Consider:

    minimize  -3 x1 - 2 x2
    subject to  x1 + x2 + s1 = 4
                x1 +     s2 = 3
                       x2 + s3 = 2
                x1, x2, s1, s2, s3 >= 0

Initial basis: `(s1, s2, s3)`, BFS = `(x1, x2, s1, s2, s3) = (0, 0, 4, 3, 2)`.

    reduced costs:  c_bar_x1 = -3   c_bar_x2 = -2

Dantzig's rule picks `x1` to enter. Direction `d = (1, 1, 0)`. Ratios
`(4/1, 3/1)` ignoring zeros — `s2` leaves at ratio 3.

After one pivot: basis becomes `(s1, x1, s3)`, BFS = `(3, 0, 1, 0, 2)`,
objective = `-9`. Iterate; at the second pivot `x2` enters and reaches
the optimum.

## Why this matters for the curriculum

The simplex pivot is one of two canonical examples in the foundational
curriculum where a bare LLM may or may not get the arithmetic right.
A code-backed reference makes the per-step computation deterministic;
the LLM's role is to *recognize* "this is a simplex problem" and
delegate, not to compute.

## Prereqs

- `lp_canonical_form` (Bertsimas LP §1.1)
- `standard_form_conversion` (Bertsimas LP §1.1)
- `polyhedron_definition` (Bertsimas LP §2.1)
