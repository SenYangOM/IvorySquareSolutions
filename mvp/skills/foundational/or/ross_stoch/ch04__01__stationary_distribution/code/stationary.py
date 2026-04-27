"""Deterministic stationary distribution solver for finite Markov chains.

Used by the foundational concept skill
``fnd_or_ross_stoch_ch04_01_stationary_distribution``.

Pure-Python (no numpy) so the MVP toolchain stays dependency-light.
For large n the iterative-power method or scipy eigensolvers are more
appropriate; this is the *teaching* reference.
"""

from __future__ import annotations

from typing import Sequence


def _is_stochastic(P: list[list[float]], tol: float = 1e-6) -> bool:
    n = len(P)
    if any(len(row) != n for row in P):
        return False
    for row in P:
        if any(v < -tol for v in row):
            return False
        if abs(sum(row) - 1.0) > tol:
            return False
    return True


def _solve_linear_system(A: list[list[float]], b: list[float]) -> list[float]:
    """Solve A x = b via Gaussian elimination with partial pivoting."""
    n = len(A)
    if any(len(row) != n for row in A):
        raise ValueError("A must be square")
    if len(b) != n:
        raise ValueError("len(b) must equal n")
    aug = [list(map(float, row)) + [float(b[i])] for i, row in enumerate(A)]
    for col in range(n):
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            raise ValueError("singular system; transition matrix may not be ergodic")
        if pivot_row != col:
            aug[col], aug[pivot_row] = aug[pivot_row], aug[col]
        pivot_val = aug[col][col]
        aug[col] = [v / pivot_val for v in aug[col]]
        for r in range(n):
            if r == col:
                continue
            factor = aug[r][col]
            if factor == 0.0:
                continue
            aug[r] = [aug[r][k] - factor * aug[col][k] for k in range(n + 1)]
    return [row[n] for row in aug]


def stationary_distribution(P: Sequence[Sequence[float]]) -> list[float]:
    """Compute the stationary distribution ``pi`` of a finite-state DTMC.

    Solves ``pi (P - I) = 0`` augmented with ``sum(pi) = 1`` by
    replacing the last balance equation with the normalization
    constraint.

    Raises :class:`ValueError` if ``P`` is not row-stochastic or if the
    resulting linear system is singular (chain not ergodic).
    """
    rows = [list(map(float, row)) for row in P]
    n = len(rows)
    if not _is_stochastic(rows):
        raise ValueError("P must be a row-stochastic matrix")
    # Build the linear system A pi = b where rows are constraints:
    # rows 0..n-2 of (P^T - I) plus the normalization row.
    A: list[list[float]] = []
    b: list[float] = []
    for i in range(n - 1):
        row = [rows[j][i] for j in range(n)]
        row[i] -= 1.0
        A.append(row)
        b.append(0.0)
    A.append([1.0] * n)
    b.append(1.0)
    pi = _solve_linear_system(A, b)
    # Snap tiny negatives to zero.
    pi = [max(0.0, v) for v in pi]
    s = sum(pi)
    if s == 0:
        raise ValueError("stationary distribution sums to zero; chain not ergodic")
    return [v / s for v in pi]


def two_state_stationary(p: float, q: float) -> tuple[float, float]:
    """Closed-form stationary distribution of a 2-state DTMC.

    ``p`` is the 0->1 transition probability; ``q`` is the 1->0
    transition probability. Returns ``(pi_0, pi_1)``.
    """
    if not (0 <= p <= 1 and 0 <= q <= 1):
        raise ValueError("p and q must lie in [0, 1]")
    if p + q == 0:
        # Identity transition: every distribution is stationary; default to uniform.
        return (0.5, 0.5)
    pi0 = q / (p + q)
    return (pi0, 1.0 - pi0)


__all__ = ["stationary_distribution", "two_state_stationary"]
