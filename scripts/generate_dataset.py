"""Synthetic shipment document dataset generator (Blueprint §26).

Generates internally consistent document families (PO / BOL / POD / INVOICE)
per shipment, with controlled contradictions for exception cases. Every case
emits a machine-readable ground-truth record for reproducible evaluation.

All documents are clearly labeled SYNTHETIC (dossier §13, §33 principle 10).

Usage:
    .venv/bin/python -m scripts.generate_dataset
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
SYNTHETIC_DIR = ROOT / "data" / "synthetic"
GROUND_TRUTH_DIR = ROOT / "data" / "ground_truth"

CARRIER = "BLUELINE LOGISTICS"
VENDOR = "ACME FREIGHT CO"
ORIGIN = "MUMBAI"
DESTINATION = "DELHI"


@dataclass
class CaseSpec:
    case_id: str
    description: str
    ordered_qty: float = 800.0
    bol_qty: float = 800.0
    pod_qty: float = 800.0
    invoice_qty: float = 800.0
    unit_price: float = 12.5
    invoice_amount: float | None = None  # default = unit_price * invoice_qty
    include_pod: bool = True
    second_invoice: bool = False
    second_invoice_date: str | None = None  # resubmission date (makes the doc distinct in bytes)
    currency: str = "USD"
    bol_qty_display: str | None = None  # raw display value for the BOL quantity line
    invoice_po_number: str | None = None  # default matches PO
    ship_date: str = "2026-09-05"
    delivery_date: str = "2026-09-09"
    invoice_date: str = "2026-09-12"
    expected_exception_types: list[str] = field(default_factory=list)
    expected_affected_fields: list[str] = field(default_factory=list)
    requires_human_review: bool = True
    notes: str = ""


def _pdf(title: str, lines: list[tuple[str, str]], case_id: str) -> bytes:
    """Render a controlled-layout document PDF and return real bytes.

    bytes (not bytearray): multipart upload helpers (httpx, browsers) expect
    immutable bytes for binary part content.
    """
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)
    pdf.set_font("Helvetica", size=11)
    for label, value in lines:
        pdf.cell(0, 7, f"{label}: {value}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_font("Helvetica", "I", 8)
    pdf.cell(
        0,
        6,
        f"SYNTHETIC DATA - case {case_id} - generated for controlled evaluation - NOT real shipment data",
        new_x="LMARGIN", new_y="NEXT",
    )
    return bytes(pdf.output())


def _qty_str(v: float) -> str:
    return f"{v:.0f} kg" if float(v).is_integer() else f"{v} kg"


def _money(v: float, currency: str = "USD") -> str:
    return f"{currency} {v:,.2f}"


def build_case(spec: CaseSpec) -> dict:
    n = int(spec.case_id[-2:]) if spec.case_id[-2:].isdigit() else 0
    po_number = f"PO-2026-{n:04d}"
    shipment_ref = f"SHI-2026-{n:04d}"
    invoice_number = f"INV-2026-{n:04d}"
    invoice_amount = (
        spec.invoice_amount
        if spec.invoice_amount is not None
        else spec.unit_price * spec.invoice_qty
    )

    docs: dict[str, list[tuple[str, str]]] = {
        "PO": [
            ("PURCHASE ORDER NUMBER", po_number),
            ("SHIPMENT REFERENCE", shipment_ref),
            ("VENDOR", VENDOR),
            ("CARRIER", CARRIER),
            ("ORIGIN", ORIGIN),
            ("DESTINATION", DESTINATION),
            ("ORDERED QUANTITY", _qty_str(spec.ordered_qty)),
            ("UNIT PRICE (PER KG)", _money(spec.unit_price, spec.currency)),
            ("EXPECTED DELIVERY DATE", spec.delivery_date),
        ],
        "BOL": [
            ("SHIPMENT REFERENCE", shipment_ref),
            ("PURCHASE ORDER NUMBER", po_number),
            ("CARRIER", CARRIER),
            ("GROSS WEIGHT", spec.bol_qty_display or _qty_str(spec.bol_qty)),
            ("SHIP DATE", spec.ship_date),
        ],
        "POD": [
            ("SHIPMENT REFERENCE", shipment_ref),
            ("PURCHASE ORDER NUMBER", po_number),
            ("DELIVERED QUANTITY", _qty_str(spec.pod_qty)),
            ("DATE OF DELIVERY", spec.delivery_date),
        ],
        "INVOICE": [
            ("INVOICE NUMBER", invoice_number),
            ("PURCHASE ORDER NUMBER", spec.invoice_po_number or po_number),
            ("SHIPMENT REFERENCE", shipment_ref),
            ("VENDOR", VENDOR),
            ("BILLED QUANTITY", _qty_str(spec.invoice_qty)),
            ("UNIT PRICE (PER KG)", _money(spec.unit_price, spec.currency)),
            ("TOTAL AMOUNT", _money(invoice_amount, spec.currency)),
            ("INVOICE DATE", spec.invoice_date),
        ],
    }

    titles = {
        "PO": "PURCHASE ORDER",
        "BOL": "BILL OF LADING",
        "POD": "PROOF OF DELIVERY",
        "INVOICE": "INVOICE",
    }
    out: dict[str, bytes] = {}
    for doc_type, lines in docs.items():
        if doc_type == "POD" and not spec.include_pod:
            continue
        out[doc_type] = _pdf(titles[doc_type], lines, spec.case_id)
    if spec.second_invoice:
        # Realistic duplicate: vendor resubmits the same invoice (same number +
        # amount) on a later date. Bytes differ (date line) so the upload
        # idempotency rule does not swallow it — the reconciliation engine
        # must catch it via (invoice_number, amount).
        dup_lines = [
            (label, spec.second_invoice_date) if label == "INVOICE DATE" and spec.second_invoice_date
            else (label, value)
            for label, value in docs["INVOICE"]
        ]
        out["INVOICE_2"] = _pdf(titles["INVOICE"], dup_lines, spec.case_id)

    return {
        "spec": spec,
        "files": out,
        "metadata": {
            "po_number": po_number,
            "shipment_ref": shipment_ref,
            "invoice_number": invoice_number,
            "invoice_amount": invoice_amount,
        },
    }


CASES: list[CaseSpec] = [
    CaseSpec(
        "C01",
        "Clean shipment - all documents agree",
        expected_exception_types=[],
        requires_human_review=False,
        notes="All quantities 800 kg; amount consistent (800 x 12.50).",
    ),
    CaseSpec(
        "C02",
        "CANONICAL DEMO CASE - invoice exceeds delivered quantity",
        bol_qty=815.0,
        pod_qty=815.0,
        invoice_qty=840.0,
        expected_exception_types=["QUANTITY_MISMATCH"],
        expected_affected_fields=["quantity"],
        notes="PO 800 kg / BOL 815 kg / POD 815 kg / INVOICE 840 kg (dossier §3, §26).",
    ),
    CaseSpec(
        "C03",
        "Amount mismatch - invoice amount higher than unit price x billed qty",
        invoice_amount=10_500.0,  # 800 x 12.50 = 10,000 expected
        expected_exception_types=["AMOUNT_MISMATCH"],
        expected_affected_fields=["amount"],
    ),
    CaseSpec(
        "C04",
        "Duplicate invoice - vendor resubmits same invoice number and amount on a later date",
        second_invoice=True,
        second_invoice_date="2026-09-15",
        expected_exception_types=["DUPLICATE_INVOICE"],
        expected_affected_fields=["invoice_number", "amount"],
    ),
    CaseSpec(
        "C05",
        "Missing POD - no proof of delivery provided",
        include_pod=False,
        expected_exception_types=["EVIDENCE_MISSING"],
        expected_affected_fields=["POD"],
    ),
    CaseSpec(
        "C06",
        "Identifier mismatch - invoice references a different PO",
        invoice_po_number="PO-2026-9999",
        expected_exception_types=["IDENTIFIER_MISMATCH"],
        expected_affected_fields=["po_number"],
    ),
    CaseSpec(
        "C07",
        "Partial shipment - delivered 600 of ordered 800",
        bol_qty=600.0,
        pod_qty=600.0,
        invoice_qty=600.0,
        expected_exception_types=["PARTIAL_SHIPMENT"],
        expected_affected_fields=["quantity"],
        notes="BOL/POD consistent at 600; invoice matches delivered. Legitimate partial delivery possible.",
    ),
    CaseSpec(
        "C08",
        "Timeline inconsistency - invoice dated before ship date",
        invoice_date="2026-09-01",
        expected_exception_types=["TIMELINE_INCONSISTENCY"],
        expected_affected_fields=["invoice_date", "ship_date"],
    ),
    CaseSpec(
        "C09",
        "Multi-exception - quantity mismatch AND missing POD",
        bol_qty=815.0,
        invoice_qty=840.0,
        include_pod=False,
        expected_exception_types=["QUANTITY_MISMATCH", "EVIDENCE_MISSING"],
        expected_affected_fields=["quantity", "POD"],
    ),
    CaseSpec(
        "C10",
        "Ambiguous - documents conflict with each other; human review required",
        bol_qty=815.0,
        pod_qty=600.0,
        invoice_qty=815.0,
        expected_exception_types=["QUANTITY_MISMATCH"],
        expected_affected_fields=["quantity"],
        notes="BOL says 815, POD says 600: delivered quantity itself is disputed. System must present the conflict, not pick a winner.",
    ),
    CaseSpec(
        "C11",
        "Clean shipment - second clean case (different volumes)",
        ordered_qty=1200.0,
        bol_qty=1200.0,
        pod_qty=1200.0,
        invoice_qty=1200.0,
        expected_exception_types=[],
        requires_human_review=False,
    ),
    CaseSpec(
        "C12",
        "Clean with unit variation - BOL in tonnes (0.8 t) must normalize to 800 kg, no false positive",
        bol_qty_display="0.8 t",
        expected_exception_types=[],
        requires_human_review=False,
        notes="Proves canonical-unit normalization end-to-end (Blueprint §22 Step 1).",
    ),
    CaseSpec(
        "C13",
        "Amount mismatch in INR - invoice 52,000 vs 100 x 500 = 50,000",
        ordered_qty=500.0,
        bol_qty=500.0,
        pod_qty=500.0,
        invoice_qty=500.0,
        unit_price=100.0,
        invoice_amount=52_000.0,
        currency="INR",
        expected_exception_types=["AMOUNT_MISMATCH"],
        expected_affected_fields=["amount"],
        notes="Proves explicit currency handling (no silent cross-currency arithmetic).",
    ),
    CaseSpec(
        "C14",
        "Multi-exception - identifier mismatch AND missing POD",
        invoice_po_number="PO-2026-9914",
        include_pod=False,
        expected_exception_types=["IDENTIFIER_MISMATCH", "EVIDENCE_MISSING"],
        expected_affected_fields=["po_number", "POD"],
    ),
]


def main() -> None:
    SYNTHETIC_DIR.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    summary = []
    for spec in CASES:
        result = build_case(spec)
        case_dir = SYNTHETIC_DIR / spec.case_id
        case_dir.mkdir(parents=True, exist_ok=True)
        file_map = {}
        for doc_type, data in result["files"].items():
            ext = ".pdf"
            name = f"{doc_type}_{result['metadata']['shipment_ref']}{ext}"
            (case_dir / name).write_bytes(data)
            file_map[doc_type] = f"{spec.case_id}/{name}"
        ground_truth = {
            "case_id": spec.case_id,
            "description": spec.description,
            "notes": spec.notes,
            "shipment": {
                "external_reference": result["metadata"]["shipment_ref"],
                "purchase_order_id": result["metadata"]["po_number"],
                "carrier_id": CARRIER,
                "vendor_id": VENDOR,
                "origin": ORIGIN,
                "destination": DESTINATION,
            },
            "documents": file_map,
            "expected_values": {
                "ordered_qty_kg": spec.ordered_qty,
                "bol_qty_kg": spec.bol_qty,
                "pod_qty_kg": spec.pod_qty if spec.include_pod else None,
                "invoice_qty_kg": spec.invoice_qty,
                "unit_price": spec.unit_price,
                "invoice_amount": result["metadata"]["invoice_amount"],
                "currency": spec.currency,
            },
            "injected_anomalies": [spec.description],
            "expected_exception_types": spec.expected_exception_types,
            "expected_affected_fields": spec.expected_affected_fields,
            "expected_requires_human_review": spec.requires_human_review,
            "synthetic": True,
        }
        (GROUND_TRUTH_DIR / f"{spec.case_id}.json").write_text(
            json.dumps(ground_truth, indent=2) + "\n"
        )
        summary.append((spec.case_id, spec.description))
        print(f"generated {spec.case_id}: {spec.description}")
    print(f"\n{len(CASES)} cases written to {SYNTHETIC_DIR} + {GROUND_TRUTH_DIR}")


if __name__ == "__main__":
    main()
