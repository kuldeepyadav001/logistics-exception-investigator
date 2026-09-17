"""Unit tests for field normalization (Blueprint §22 Step 1)."""
from services.reconciliation.normalize import (
    normalize_date,
    normalize_identifier,
    normalize_number,
    normalize_weight,
    parse_money,
)


def test_identifier_trim_upper_collapse():
    assert normalize_identifier("  po-2026-0001 ") == "PO-2026-0001"
    assert normalize_identifier("a  b") == "A B"
    assert normalize_identifier(None) is None
    assert normalize_identifier("   ") is None


def test_number_parsing():
    assert normalize_number("1,234.56") == 1234.56
    assert normalize_number(" 800 ") == 800.0
    assert normalize_number("USD 12,400.00") == 12400.0
    assert normalize_number(None) is None
    assert normalize_number("abc") is None
    assert normalize_number("-") is None


def test_weight_kg_passthrough():
    assert normalize_weight("800 kg") == (800.0, "kg")
    assert normalize_weight("800") == (800.0, "kg")
    assert normalize_weight(800) == (800.0, "kg")


def test_weight_conversion():
    assert normalize_weight("0.8 t") == (800.0, "kg")
    assert normalize_weight("2000 g") == (2.0, "kg")
    lb, unit = normalize_weight("10 lbs")
    assert unit == "kg"
    assert lb is not None and abs(lb - 4.5359237) < 1e-5


def test_weight_unrecognized_unit_refused():
    assert normalize_weight("800 stones") == (None, None)
    assert normalize_weight("eight hundred kg") == (None, None)


def test_date_canonical_iso():
    assert normalize_date("2026-09-05") == "2026-09-05"
    assert normalize_date("05/09/2026") == "2026-09-05"
    assert normalize_date("5 Sep 2026") == "2026-09-05"
    assert normalize_date("not a date") is None
    assert normalize_date(None) is None


def test_parse_money():
    assert parse_money("USD 10,500.00") == (10500.0, "USD")
    assert parse_money("10500.00") == (10500.0, None)
    assert parse_money("INR 4,00,000") == (400000.0, "INR")
    assert parse_money("n/a") == (None, None)
