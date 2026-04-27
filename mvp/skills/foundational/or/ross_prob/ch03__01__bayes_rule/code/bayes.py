"""Deterministic Bayes\' rule reference.

Used by the foundational concept skill
``fnd_or_ross_prob_ch03_01_bayes_rule``.
"""

from __future__ import annotations

from typing import Sequence


def bayes_two_event(p_a: float, p_b_given_a: float, p_b_given_not_a: float) -> float:
    """Compute ``P(A | B)`` for the two-event case.

    Inputs:

    - ``p_a``: prior P(A).
    - ``p_b_given_a``: likelihood P(B | A).
    - ``p_b_given_not_a``: P(B | not A).

    Raises :class:`ValueError` when any input is outside [0, 1] or when
    the marginal P(B) is zero.
    """
    for name, val in (
        ("p_a", p_a),
        ("p_b_given_a", p_b_given_a),
        ("p_b_given_not_a", p_b_given_not_a),
    ):
        if not 0 <= val <= 1:
            raise ValueError(f"{name}={val!r} must lie in [0, 1]")
    p_a_f = float(p_a)
    p_b = p_b_given_a * p_a_f + p_b_given_not_a * (1.0 - p_a_f)
    if p_b == 0:
        raise ValueError("P(B) is zero; posterior is undefined")
    return (p_b_given_a * p_a_f) / p_b


def bayes_partition(
    priors: Sequence[float],
    likelihoods: Sequence[float],
) -> list[float]:
    """Compute the posterior over a partition.

    ``priors[i] = P(A_i)`` (must sum to 1, within tolerance).
    ``likelihoods[i] = P(B | A_i)``.

    Returns a list ``posteriors`` with ``posteriors[i] = P(A_i | B)``.
    """
    if len(priors) != len(likelihoods):
        raise ValueError(
            f"len(priors)={len(priors)} differs from len(likelihoods)={len(likelihoods)}"
        )
    p = list(map(float, priors))
    l = list(map(float, likelihoods))
    if any(v < 0 or v > 1 for v in p):
        raise ValueError("priors must lie in [0, 1]")
    if any(v < 0 or v > 1 for v in l):
        raise ValueError("likelihoods must lie in [0, 1]")
    s = sum(p)
    if not 0.999 <= s <= 1.001:
        raise ValueError(f"priors must sum to 1 (got {s!r})")
    p_b = sum(p[i] * l[i] for i in range(len(p)))
    if p_b == 0:
        raise ValueError("marginal P(B) is zero; posteriors undefined")
    return [(p[i] * l[i]) / p_b for i in range(len(p))]


__all__ = ["bayes_partition", "bayes_two_event"]
