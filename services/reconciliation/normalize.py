"""Field normalization (Blueprint §22, Step 1).

Rules:
- identifiers: trimmed, whitespace-collapsed, upper-cased
- dates: canonical ISO yyyy-mm-dd
- weights: canonical unit kg
- numbers: plain decimal
- unrecognized units/formats return None and surface as warnings — the
  system never guesses (Blueprint §27 Failure Handling).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional, Union

_WEIGHT_TO_KG = {
    "kg": 1.0,
    "kgs": 1.0,
    "kilogram": 1.0,
    "kilograms": 1.0,
    "kilo": 1.0,
    "g": 0.001,
    "gram": 0.001,
    "grams": 0.001,
    "t": 1000.0,
    "tonne": 1000.0,
    "tonnes": 1000.0,
    "metric ton": 1000.0,
    "lb": 0.45359237,
    "lbs": 0.45359237,
}


def normalize_identifier(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    v = re.sub(r"\s+", " ", value.strip()).upper()
    return v or None


def normalize_number(value: Union[str, int, float, None]) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    v = str(value).strip().replace(",", "").replace(" ", "")
    v = re.sub(r"[^\d.\-]", "", v)
    if not v or v in {"-", ".", "-."}:
        return None
    try:
        return float(v)
    except ValueError:
        return None


def normalize_weight(
    value: Union[str, int, float, None], default_unit: str = "kg"
) -> tuple[Optional[float], Optional[str]]:
    """Return (weight_kg, unit) or (None, None) when unparseable."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), default_unit
    s = str(value).strip().lower()
    m = re.match(r"^([\d.,]+)\s*([a-z/ ]+)?$", s)
    if not m:
        return None, None
    num = normalize_number(m.group(1))
    if num is None:
        return None, None
    unit = (m.group(2) or default_unit).strip()
    factor = _WEIGHT_TO_KG.get(unit)
    if factor is None:
        return None, None  # unrecognized unit: refuse, do not guess
    return round(num * factor, 6), "kg"


def normalize_date(value: Union[str, date, datetime, None]) -> Optional[str]:
    """Canonical ISO yyyy-mm-dd, or None when unparseable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    s = str(value).strip()
    for fmt in (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d %b %Y",
        "%B %d, %Y",
    ):
        try:
            return datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def parse_money(
    value: Union[str, int, float, None]
) -> tuple[Optional[float], Optional[str]]:
    """Return (amount, currency_code) from values like 'USD 10,500.00'."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)):
        return float(value), None
    s = str(value).strip()
    cur = re.search(r"\b(USD|EUR|INR|GBP|AED|SGD)\b", s, flags=re.IGNORECASE)
    currency = cur.group(1).upper() if cur else None
    num = normalize_number(re.sub(r"\b(USD|EUR|INR|GBP|AED|SGD)\b", " ", s))
    return num, currency
