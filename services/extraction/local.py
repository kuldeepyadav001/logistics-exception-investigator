"""Controlled extraction layer (Blueprint §20 Document Intelligence).

Local stand-in for Amazon Textract (ADR-001). Reads PDF text via pypdf and
applies a controlled "LABEL: value" parsing pass over the synthetic document
layout. Authoritative extraction is NEVER delegated to an LLM: every field
is tied to the raw line it came from, with an explicit confidence and
location. Unrecognized formats produce warnings — never invented values
(Blueprint §27).

When an AWS account is available, TextractExtractor (AnalyzeExpense /
AnalyzeDocument) implements the same ExtractionResult contract.
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field


@dataclass
class ExtractedField:
    field_name: str
    raw_value: str
    normalized_value: str
    unit: str | None = None
    confidence: float = 1.0
    location: str | None = None  # e.g. "line 7"


@dataclass
class ExtractionResult:
    status: str  # SUCCEEDED | PARTIAL | FAILED
    fields: list[ExtractedField] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_LABEL_MAP: dict[str, tuple[str, str]] = {
    "PURCHASE ORDER NUMBER": ("po_number", "identifier"),
    "PO NUMBER": ("po_number", "identifier"),
    "PO NO": ("po_number", "identifier"),
    "PO NO.": ("po_number", "identifier"),
    "SHIPMENT REFERENCE": ("shipment_reference", "identifier"),
    "SHIPMENT REF": ("shipment_reference", "identifier"),
    "SHIPMENT REF.": ("shipment_reference", "identifier"),
    "BOL REFERENCE": ("shipment_reference", "identifier"),
    "INVOICE NUMBER": ("invoice_number", "identifier"),
    "INVOICE NO": ("invoice_number", "identifier"),
    "INVOICE NO.": ("invoice_number", "identifier"),
    "CARRIER": ("carrier_id", "identifier"),
    "CARRIER NAME": ("carrier_id", "identifier"),
    "VENDOR": ("vendor_id", "identifier"),
    "VENDOR NAME": ("vendor_id", "identifier"),
    "BILL TO": ("vendor_id", "identifier"),
    "ORIGIN": ("origin", "identifier"),
    "DESTINATION": ("destination", "identifier"),
    "QUANTITY": ("quantity_kg", "weight"),
    "GROSS WEIGHT": ("quantity_kg", "weight"),
    "DELIVERED QUANTITY": ("quantity_kg", "weight"),
    "BILLED QUANTITY": ("quantity_kg", "weight"),
    "ORDERED QUANTITY": ("quantity_kg", "weight"),
    "TOTAL AMOUNT": ("amount", "money"),
    "AMOUNT": ("amount", "money"),
    "INVOICE AMOUNT": ("amount", "money"),
    "TOTAL": ("amount", "money"),
    "UNIT PRICE": ("unit_price", "money"),
    "UNIT PRICE (PER KG)": ("unit_price", "money"),
    "UNIT RATE": ("unit_price", "money"),
    "SHIP DATE": ("ship_date", "date"),
    "DELIVERY DATE": ("delivery_date", "date"),
    "DATE OF DELIVERY": ("delivery_date", "date"),
    "INVOICE DATE": ("invoice_date", "date"),
    "EXPECTED DELIVERY DATE": ("expected_delivery_date", "date"),
}

_LINE_RE = re.compile(r"^\s*([A-Z][A-Z0-9 ()/&.\-]{1,45})\s*:\s*(.+?)\s*$")
_SKIP_TOKENS = ("SYNTHETIC", "GENERATED FOR", "DO NOT", "CONFIDENTIAL")


def _read_text(data: bytes, filename: str) -> tuple[str | None, str | None]:
    """Return (text, error). Works for PDF, TXT, MD."""
    lower = filename.lower()
    if lower.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(data))
            parts = [p.extract_text() or "" for p in reader.pages]
            return "\n".join(parts), None
        except Exception as e:  # noqa: BLE001 — surface, do not invent
            return None, f"PDF parsing failed: {e}"
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as e:
        return None, f"Text decoding failed: {e}"


def _normalize_field(kind: str, raw: str):
    """Return (normalized_value, unit) or (None, None)."""
    from services.reconciliation.normalize import (
        normalize_date,
        normalize_identifier,
        normalize_weight,
        parse_money,
    )

    if kind == "identifier":
        v = normalize_identifier(raw)
        return (v, None) if v else (None, None)
    if kind == "weight":
        kg, unit = normalize_weight(raw)
        return (f"{kg:.3f}".rstrip("0").rstrip("."), unit) if kg is not None else (None, None)
    if kind == "money":
        num, currency = parse_money(raw)
        if num is None:
            return None, None
        return (f"{num:.2f}", currency)
    if kind == "date":
        v = normalize_date(raw)
        return (v, None) if v else (None, None)
    return None, None


class LocalExtractor:
    """Deterministic controlled parser. See module docstring for the contract."""

    name = "local-controlled-parser"

    def extract(self, data: bytes, filename: str) -> ExtractionResult:
        text, err = _read_text(data, filename)
        if err:
            return ExtractionResult(status="FAILED", errors=[err])

        fields: list[ExtractedField] = []
        warnings: list[str] = []
        seen: set[str] = set()

        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(tok in line.upper() for tok in _SKIP_TOKENS):
                continue
            m = _LINE_RE.match(line)
            if not m:
                continue
            label = m.group(1).strip().upper()
            value = m.group(2).strip()
            spec = _LABEL_MAP.get(label)
            if spec is None:
                continue
            field_name, kind = spec
            if field_name in seen:
                warnings.append(f"duplicate label '{label}' ignored (line {lineno})")
                continue
            normalized, unit = _normalize_field(kind, value)
            if normalized is None:
                warnings.append(
                    f"unrecognized value for '{label}': {value!r} (line {lineno}) — field skipped, not guessed"
                )
                continue
            seen.add(field_name)
            fields.append(
                ExtractedField(
                    field_name=field_name,
                    raw_value=value,
                    normalized_value=normalized,
                    unit=unit,
                    confidence=1.0,
                    location=f"line {lineno}",
                )
            )

        if not fields:
            return ExtractionResult(
                status="PARTIAL",
                warnings=["no recognized fields found — document layout may be unsupported"],
            )
        return ExtractionResult(status="SUCCEEDED", fields=fields, warnings=warnings)
