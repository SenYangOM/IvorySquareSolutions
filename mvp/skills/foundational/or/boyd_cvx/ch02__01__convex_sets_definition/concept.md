# Convex set — definition

A set `C ⊆ R^n` is *convex* if it contains every line segment whose
endpoints lie in `C`. Formally:

    For all x, y in C and all theta in [0, 1]:
        theta * x + (1 - theta) * y  is in C

The point `theta * x + (1 - theta) * y` is a *convex combination* of
`x` and `y`. The condition extends to convex combinations of any
finite number of points: a convex set contains every weighted
average of its members where the weights are nonnegative and sum to 1.

## Examples

Convex:

- The empty set, single points, and all of `R^n`.
- Halfspaces `{x : a^T x <= b}`.
- Hyperplanes `{x : a^T x = b}`.
- Balls (open or closed) under any norm.
- Polyhedra: finite intersections of halfspaces.
- The probability simplex `{x : x >= 0, sum x_i = 1}`.

Not convex:

- Any donut (annulus): a line segment between two outer points may
  pass through the hole.
- The graph of a strictly concave function (it's a 1-dim curve, not a
  set with interior).
- Boolean indicator sets like `{0, 1}^n`.

## Operations preserving convexity

- Intersections (any number, even infinite).
- Affine maps `f(x) = A x + b` and their inverses.
- Minkowski sums `C_1 + C_2 = {x_1 + x_2 : x_1 in C_1, x_2 in C_2}`.
- Cartesian products.

Unions of convex sets are *not* convex in general.

## Why this matters

Convexity is the structural property that makes optimization tractable:
in convex optimization, every local minimum is a global minimum.
Recognizing whether a feasible set is convex is the first step in
modeling a convex program.

## Why markdown-only (conceptual_high_value)

Bare LLMs handle the convex-set definition correctly the vast majority
of the time. The value of a foundational skill here is curating the
canonical examples and counterexamples, not adding deterministic
arithmetic.
