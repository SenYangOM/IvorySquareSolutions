"""Deterministic variance and standard deviation reference.

Used by the foundational concept skill
``fnd_or_ross_prob_ch04_02_variance_definition``.
"""

from __future__ import annotations

from math import sqrt
from typing import Sequence


def population_variance(values: Sequence[float]) -> float:
    """Population variance (divide by n)."""
    n = len(values)
    if n == 0:
        raise ValueError("cannot compute variance of an empty sample")
    mean = sum(values) / n
    return sum((float(v) - mean) ** 2 for v in values) / n


def sample_variance(values: Sequence[float]) -> float:
    """Sample variance with Bessel's correction (divide by n-1)."""
    n = len(values)
    if n < 2:
        raise ValueError(
            f"sample_variance requires at least two observations, got n={n}"
        )
    mean = sum(values) / n
    return sum((float(v) - mean) ** 2 for v in values) / (n - 1)


def population_std(values: Sequence[float]) -> float:
    """Population standard deviation."""
    return sqrt(population_variance(values))


def sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation with Bessel's correction."""
    return sqrt(sample_variance(values))


def discrete_variance(values: Sequence[float], probabilities: Sequence[float]) -> float:
    """Variance of a discrete random variable.

    ``probabilities`` must be nonnegative and sum to 1 (within tolerance).
    """
    if len(values) != len(probabilities):
        raise ValueError(
            f"len(values)={len(values)} differs from len(probabilities)={len(probabilities)}"
        )
    if any(p < 0 for p in probabilities):
        raise ValueError("probabilities must be nonnegative")
    s = sum(float(p) for p in probabilities)
    if not 0.999 <= s <= 1.001:
        raise ValueError(f"probabilities must sum to 1.0 (got {s!r})")
    mean = sum(float(v) * float(p) for v, p in zip(values, probabilities))
    return sum(float(p) * (float(v) - mean) ** 2 for v, p in zip(values, probabilities))


__all__ = [
    "discrete_variance",
    "population_std",
    "population_variance",
    "sample_std",
    "sample_variance",
]
