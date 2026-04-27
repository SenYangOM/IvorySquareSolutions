"""Deterministic single-step simplex pivot reference (pure-Python).

Closed-form deterministic implementation of one simplex iteration in
standard form. Inputs are nested lists; outputs are the new basis,
new BFS, and the objective value, plus diagnostics for pivot rule
choice and unboundedness detection.

Used by the foundational concept skill
``fnd_or_bertsimas_lp_ch03_01_simplex_pivot_rule`` to provide
deterministic computation backing the bare-LLM concept page.

Implemented in pure Python (no numpy dependency) because the MVP
toolchain stays light. For production-scale LPs use ``scipy.optimize``;
this module is the *teaching* reference, not the production solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class PivotResult:
    """Result of one simplex pivot step."""

    new_basis: tuple[int, ...]
    new_bfs: tuple[float, ...]
    new_objective: float
    entered: int
    left: int | None
    unbounded: bool


def reduced_cost(c_j: float, c_B: Sequence[float], B_inv_A_j: Sequence[float]) -> float:
    """Compute the reduced cost ``c_bar_j = c_j - c_B^T B^{-1} A_j``."""
    if len(c_B) != len(B_inv_A_j):
        raise ValueError(
            f"len(c_B)={len(c_B)} differs from len(B_inv_A_j)={len(B_inv_A_j)}"
        )
    dot = sum(float(a) * float(b) for a, b in zip(c_B, B_inv_A_j))
    return float(c_j) - dot


def _matvec(M: list[list[float]], v: list[float]) -> list[float]:
    if any(len(row) != len(v) for row in M):
        raise ValueError(
            f"matrix-vector shape mismatch: rows {[len(r) for r in M]} vs len(v)={len(v)}"
        )
    return [sum(M[i][k] * v[k] for k in range(len(v))) for i in range(len(M))]


def _matmat(A: list[list[float]], B: list[list[float]]) -> list[list[float]]:
    n_cols_b = len(B[0]) if B else 0
    if any(len(row) != len(B) for row in A):
        raise ValueError("matmat shape mismatch")
    return [
        [sum(A[i][k] * B[k][j] for k in range(len(B))) for j in range(n_cols_b)]
        for i in range(len(A))
    ]


def _invert(M: list[list[float]]) -> list[list[float]]:
    """Gauss-Jordan inversion of a square matrix. Raises on singular input."""
    n = len(M)
    if any(len(row) != n for row in M):
        raise ValueError(f"_invert expects a square matrix; got {n}x{[len(r) for r in M]}")
    aug = [list(row) + [1.0 if i == j else 0.0 for j in range(n)] for i, row in enumerate(M)]
    for col in range(n):
        # Partial pivot for numerical stability.
        pivot_row = max(range(col, n), key=lambda r: abs(aug[r][col]))
        if abs(aug[pivot_row][col]) < 1e-12:
            raise ValueError("matrix is singular; cannot invert")
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
            aug[r] = [aug[r][k] - factor * aug[col][k] for k in range(2 * n)]
    return [row[n:] for row in aug]


def _solve(M: list[list[float]], b: list[float]) -> list[float]:
    """Solve ``M x = b`` via the inverse. M must be square and nonsingular."""
    M_inv = _invert(M)
    return _matvec(M_inv, b)


def _column(matrix: list[list[float]], j: int) -> list[float]:
    return [row[j] for row in matrix]


def _matrix_rank_full(M: list[list[float]]) -> bool:
    """Return ``True`` when ``M`` has full row rank. Cheap rank check via inversion."""
    if not M:
        return True
    n = len(M)
    if any(len(row) != n for row in M):
        return False
    try:
        _invert(M)
    except ValueError:
        return False
    return True


def reduced_costs_all_nonbasic(
    c: Sequence[float],
    A: Sequence[Sequence[float]],
    basis: Sequence[int],
) -> dict[int, float]:
    """Return ``{j: reduced_cost_j}`` for every nonbasic column ``j``."""
    A_list = [list(map(float, row)) for row in A]
    c_list = list(map(float, c))
    basis_idx = list(basis)
    if len(set(basis_idx)) != len(basis_idx):
        raise ValueError(f"basis indices must be unique, got {basis_idx!r}")
    if len(A_list) != len(basis_idx):
        raise ValueError(
            f"basis size {len(basis_idx)} does not match A rows {len(A_list)}"
        )
    B = [[A_list[i][j] for j in basis_idx] for i in range(len(A_list))]
    if not _matrix_rank_full(B):
        raise ValueError("basis matrix B is rank-deficient; supply a valid basis")
    B_inv = _invert(B)
    c_B = [c_list[j] for j in basis_idx]
    out: dict[int, float] = {}
    n_cols = len(A_list[0])
    for j in range(n_cols):
        if j in basis_idx:
            continue
        col = _column(A_list, j)
        d_j = _matvec(B_inv, col)
        out[j] = c_list[j] - sum(c_B[i] * d_j[i] for i in range(len(c_B)))
    return out


def minimum_ratio_test(
    x_B: Sequence[float], direction: Sequence[float]
) -> tuple[int | None, float | None]:
    """Run the simplex minimum-ratio test.

    Returns ``(leaving_basis_position, ratio)``. ``leaving_basis_position``
    is ``None`` and ``ratio`` is ``None`` when every direction component
    is nonpositive (LP unbounded along this edge).
    """
    x = list(map(float, x_B))
    d = list(map(float, direction))
    if len(x) != len(d):
        raise ValueError(f"x_B length {len(x)} differs from direction length {len(d)}")
    best_ratio: float | None = None
    leaving: int | None = None
    for i in range(len(x)):
        if d[i] <= 0:
            continue
        r = x[i] / d[i]
        if best_ratio is None or r < best_ratio:
            best_ratio = r
            leaving = i
    return leaving, best_ratio


def simplex_step(
    c: Sequence[float],
    A: Sequence[Sequence[float]],
    b: Sequence[float],
    basis: Sequence[int],
    *,
    rule: str = "dantzig",
) -> PivotResult:
    """Perform one simplex iteration on the LP.

    Parameters
    ----------
    c, A, b:
        LP coefficients in standard form
        (``minimize c^T x s.t. A x = b, x >= 0``).
    basis:
        Indices of currently basic variables (length equals number of
        rows of ``A``; values are unique column indices).
    rule:
        ``"dantzig"`` (most negative reduced cost) or ``"bland"``
        (smallest index with negative reduced cost). Default
        ``"dantzig"``.

    Returns
    -------
    :class:`PivotResult`. When the current basis is already optimal,
    ``entered`` is set to ``-1`` and ``left`` to ``None`` and
    ``new_basis`` equals ``basis``.
    """
    A_list = [list(map(float, row)) for row in A]
    b_list = list(map(float, b))
    c_list = list(map(float, c))
    basis_list = list(basis)

    rc = reduced_costs_all_nonbasic(c=c_list, A=A_list, basis=basis_list)
    negative = {j: r for j, r in rc.items() if r < 0}
    if not negative:
        B = [[A_list[i][j] for j in basis_list] for i in range(len(A_list))]
        x_B = _solve(B, b_list)
        n_cols = len(c_list)
        full = [0.0] * n_cols
        for pos, j in enumerate(basis_list):
            full[j] = x_B[pos]
        objective = sum(c_list[j] * full[j] for j in range(n_cols))
        return PivotResult(
            new_basis=tuple(basis_list),
            new_bfs=tuple(full),
            new_objective=objective,
            entered=-1,
            left=None,
            unbounded=False,
        )

    if rule == "dantzig":
        entering = min(negative.items(), key=lambda kv: kv[1])[0]
    elif rule == "bland":
        entering = min(negative.keys())
    else:
        raise ValueError(f"unknown pivot rule {rule!r}; use 'dantzig' or 'bland'")

    B = [[A_list[i][j] for j in basis_list] for i in range(len(A_list))]
    B_inv = _invert(B)
    direction = _matvec(B_inv, _column(A_list, entering))
    x_B = _matvec(B_inv, b_list)
    leaving_pos, _ratio = minimum_ratio_test(x_B, direction)
    if leaving_pos is None:
        n_cols = len(c_list)
        full = [0.0] * n_cols
        for pos, j in enumerate(basis_list):
            full[j] = x_B[pos]
        objective = sum(c_list[j] * full[j] for j in range(n_cols))
        return PivotResult(
            new_basis=tuple(basis_list),
            new_bfs=tuple(full),
            new_objective=objective,
            entered=entering,
            left=None,
            unbounded=True,
        )

    new_basis = list(basis_list)
    new_basis[leaving_pos] = entering
    new_B = [[A_list[i][j] for j in new_basis] for i in range(len(A_list))]
    new_x_B = _solve(new_B, b_list)
    n_cols = len(c_list)
    full = [0.0] * n_cols
    for pos, j in enumerate(new_basis):
        full[j] = new_x_B[pos]
    new_obj = sum(c_list[j] * full[j] for j in range(n_cols))
    return PivotResult(
        new_basis=tuple(new_basis),
        new_bfs=tuple(full),
        new_objective=new_obj,
        entered=entering,
        left=basis_list[leaving_pos],
        unbounded=False,
    )


__all__ = [
    "PivotResult",
    "minimum_ratio_test",
    "reduced_cost",
    "reduced_costs_all_nonbasic",
    "simplex_step",
]
