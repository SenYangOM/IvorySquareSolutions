"""Deterministic KKT-residual check for inequality + equality constrained problems.

Used by the foundational concept skill
``fnd_or_boyd_cvx_ch05_02_kkt_conditions``.

The residual is an aggregate scalar capturing primal feasibility, dual
feasibility, complementary slackness, and stationarity. A residual of
zero (within tolerance) means the candidate point satisfies KKT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Sequence


@dataclass(frozen=True)
class KKTResidual:
    """Per-condition residuals for a candidate point."""

    primal_inequality: float
    primal_equality: float
    dual_feasibility: float
    complementary_slackness: float
    stationarity: float
    total: float


def kkt_residual(
    *,
    grad_f_at_x: Sequence[float],
    g_at_x: Sequence[float],
    grad_g_at_x: Sequence[Sequence[float]],
    h_at_x: Sequence[float] | None = None,
    grad_h_at_x: Sequence[Sequence[float]] | None = None,
    mu: Sequence[float],
    nu: Sequence[float] | None = None,
) -> KKTResidual:
    """Compute the KKT residual at a candidate point.

    Inputs are scalar/vector evaluations at the candidate ``x`` rather
    than callables, which keeps this module dependency-free and
    deterministic.

    Returns
    -------
    :class:`KKTResidual` with per-condition residuals plus a
    ``total`` field summing them as a scalar diagnostic.
    """
    g_list = list(map(float, g_at_x))
    mu_list = list(map(float, mu))
    if len(g_list) != len(mu_list):
        raise ValueError(
            f"len(g)={len(g_list)} differs from len(mu)={len(mu_list)}"
        )
    if len(g_list) != len(grad_g_at_x):
        raise ValueError(
            f"len(g)={len(g_list)} differs from len(grad_g)={len(grad_g_at_x)}"
        )
    grad_f_list = list(map(float, grad_f_at_x))
    grad_g_lists = [list(map(float, row)) for row in grad_g_at_x]
    h_list = list(map(float, h_at_x or []))
    grad_h_lists = [list(map(float, row)) for row in (grad_h_at_x or [])]
    nu_list = list(map(float, nu or []))
    if len(h_list) != len(nu_list):
        raise ValueError(
            f"len(h)={len(h_list)} differs from len(nu)={len(nu_list)}"
        )
    if len(h_list) != len(grad_h_lists):
        raise ValueError(
            f"len(h)={len(h_list)} differs from len(grad_h)={len(grad_h_lists)}"
        )
    n = len(grad_f_list)
    for row in grad_g_lists + grad_h_lists:
        if len(row) != n:
            raise ValueError(
                f"gradient dimension mismatch: expected {n}, got {len(row)}"
            )

    primal_inequality = max((max(0.0, v) for v in g_list), default=0.0)
    primal_equality = max((abs(v) for v in h_list), default=0.0)
    dual_feasibility = max((max(0.0, -v) for v in mu_list), default=0.0)
    complementary_slackness = max(
        (abs(mu_list[i] * g_list[i]) for i in range(len(g_list))), default=0.0
    )

    stationarity_vec = [grad_f_list[k] for k in range(n)]
    for i, mu_i in enumerate(mu_list):
        for k in range(n):
            stationarity_vec[k] += mu_i * grad_g_lists[i][k]
    for j, nu_j in enumerate(nu_list):
        for k in range(n):
            stationarity_vec[k] += nu_j * grad_h_lists[j][k]
    stationarity = max((abs(v) for v in stationarity_vec), default=0.0)

    total = (
        primal_inequality
        + primal_equality
        + dual_feasibility
        + complementary_slackness
        + stationarity
    )
    return KKTResidual(
        primal_inequality=primal_inequality,
        primal_equality=primal_equality,
        dual_feasibility=dual_feasibility,
        complementary_slackness=complementary_slackness,
        stationarity=stationarity,
        total=total,
    )


__all__ = ["KKTResidual", "kkt_residual"]
