"""Variance calculation (Blueprint §22, Step 4).

absolute_variance = observed - reference
percentage_variance = absolute_variance / reference * 100  (when reference != 0)

The caller is responsible for recording WHICH records were compared
(reference_source / observed_source on the finding) — never report a
variance without the compared records being explicit.
"""
from __future__ import annotations

from typing import Optional


def compute_variance(observed: float, reference: float) -> tuple[float, Optional[float]]:
    abs_var = round(observed - reference, 6)
    pct = round((abs_var / reference) * 100.0, 4) if reference != 0 else None
    return abs_var, pct
