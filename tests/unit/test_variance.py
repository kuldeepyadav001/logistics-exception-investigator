"""Unit tests for variance calculation (Blueprint §22 Step 4)."""
from services.reconciliation.variance import compute_variance


def test_basic_variance():
    abs_var, pct = compute_variance(observed=840.0, reference=815.0)
    assert abs_var == 25.0
    assert pct == round(25.0 / 815.0 * 100.0, 4)


def test_negative_variance():
    abs_var, pct = compute_variance(observed=600.0, reference=800.0)
    assert abs_var == -200.0
    assert pct == -25.0


def test_zero_reference_has_no_percentage():
    abs_var, pct = compute_variance(observed=5.0, reference=0.0)
    assert abs_var == 5.0
    assert pct is None
