"""predict_filing_complexity_from_determinants — Bernard, Blankespoor,
de Kok & Toynbee (2025) Table 3 Column 2 determinants-regression port.

Re-exports ``SKILL`` for :mod:`mvp.skills.registry` auto-discovery.
"""

from .skill import SKILL  # noqa: F401

__all__ = ["SKILL"]
