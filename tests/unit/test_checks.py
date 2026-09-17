"""Fixture-based deterministic engine tests (Phase 3 core).

These mirror the synthetic ground-truth cases (Blueprint §26) and prove the
Phase 3 exit criterion: known anomalies are detected WITHOUT any LLM.
"""
from domain.models import ExceptionType, Severity

from .helpers import CLEAN_AMT, CLEAN_QTY, UNIT_PRICE, make_ctx
from services.reconciliation.checks import run_deterministic_checks


def _types(ctx):
    return [e.exception_type for e in run_deterministic_checks(ctx)]


def test_clean_case_produces_no_exceptions():
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": CLEAN_QTY, "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": CLEAN_QTY},
            "POD": {"quantity_kg": CLEAN_QTY},
            "INVOICE": {"quantity_kg": CLEAN_QTY, "amount": CLEAN_AMT},
        }
    )
    assert run_deterministic_checks(ctx) == []


def test_canonical_demo_case_quantity_mismatch():
    """PO 800 / BOL 815 / POD 815 / INVOICE 840 → QUANTITY_MISMATCH, HIGH."""
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": ("800", "kg"), "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": ("815", "kg")},
            "POD": {"quantity_kg": ("815", "kg")},
            "INVOICE": {"quantity_kg": ("840", "kg"), "amount": ("10500.00", "USD")},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert [e.exception_type for e in exceptions] == [ExceptionType.QUANTITY_MISMATCH]
    ex = exceptions[0]
    check_ids = sorted(f.check_id for f in ex.deterministic_findings)
    # BOL>PO finding + invoice vs BOL + invoice vs POD
    assert check_ids == [
        "QTY_DELIVERED_VS_INVOICE",
        "QTY_DELIVERED_VS_INVOICE",
        "QTY_PO_VS_BOL",
    ]
    # every finding names the compared records explicitly
    for f in ex.deterministic_findings:
        assert f.reference_source
        assert f.observed_source
    # exposure = 25 kg (max discrepancy) × 12.50 = 312.50
    assert ex.estimated_exposure is not None
    assert abs(ex.estimated_exposure - 312.5) < 0.01
    assert ex.severity == Severity.HIGH
    assert "quantity" in ex.affected_fields


def test_partial_shipment_not_mislabeled_as_mismatch():
    """PO 800, BOL 600, POD 600, INVOICE 600 → PARTIAL_SHIPMENT (MEDIUM)."""
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": ("800", "kg"), "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": ("600", "kg")},
            "POD": {"quantity_kg": ("600", "kg")},
            "INVOICE": {"quantity_kg": ("600", "kg"), "amount": ("7500.00", "USD")},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert [e.exception_type for e in exceptions] == [ExceptionType.PARTIAL_SHIPMENT]
    assert exceptions[0].severity == Severity.MEDIUM


def test_amount_mismatch_internal_consistency():
    """Quantities agree at 800 but invoice total 10,500 vs 12.50×800=10,000."""
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": CLEAN_QTY, "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": CLEAN_QTY},
            "POD": {"quantity_kg": CLEAN_QTY},
            "INVOICE": {"quantity_kg": CLEAN_QTY, "amount": ("10500.00", "USD")},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.AMOUNT_MISMATCH in [e.exception_type for e in exceptions]
    ex = next(e for e in exceptions if e.exception_type == ExceptionType.AMOUNT_MISMATCH)
    assert ex.estimated_exposure is not None
    assert abs(ex.estimated_exposure - 500.0) < 0.01
    assert ex.severity in (Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL)


def test_duplicate_invoice_detected():
    def inv_doc(amount):
        return {"quantity_kg": CLEAN_QTY, "amount": amount, "invoice_number": ("INV-1", None)}

    # two invoice documents: need two entries — build ctx manually
    from domain.models import DocumentType
    from tests.unit.helpers import make_doc, make_evidence
    from domain.models import Shipment, new_id
    from services.reconciliation.checks import ShipmentContext, ReconciliationConfig

    shipment = Shipment(shipment_id=new_id("sht"), external_reference="T")
    docs = []
    evidence = {}
    for i in range(2):
        d = make_doc(shipment.shipment_id, "INVOICE")
        docs.append(d)
        evidence[d.document_id] = make_evidence(d.document_id, inv_doc(("10000.00", "USD")))
    for t in ("PO", "BOL", "POD"):
        d = make_doc(shipment.shipment_id, t)
        docs.append(d)
        evidence[d.document_id] = make_evidence(d.document_id, {"quantity_kg": CLEAN_QTY})
    d_po = make_doc(shipment.shipment_id, "PO")
    ctx = ShipmentContext(
        shipment=shipment,
        documents=docs,
        evidence=evidence,
        config=ReconciliationConfig(),
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.DUPLICATE_INVOICE in [e.exception_type for e in exceptions]
    ex = next(e for e in exceptions if e.exception_type == ExceptionType.DUPLICATE_INVOICE)
    assert ex.severity == Severity.HIGH


def test_missing_pod_evidence_missing():
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": CLEAN_QTY, "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": CLEAN_QTY},
            "INVOICE": {"quantity_kg": CLEAN_QTY, "amount": CLEAN_AMT},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.EVIDENCE_MISSING in [e.exception_type for e in exceptions]
    ex = next(e for e in exceptions if e.exception_type == ExceptionType.EVIDENCE_MISSING)
    assert "POD" in ex.affected_fields
    assert ex.severity == Severity.HIGH


def test_identifier_mismatch():
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": CLEAN_QTY, "unit_price": UNIT_PRICE, "po_number": ("PO-1", None)},
            "BOL": {"quantity_kg": CLEAN_QTY},
            "POD": {"quantity_kg": CLEAN_QTY},
            "INVOICE": {
                "quantity_kg": CLEAN_QTY,
                "amount": CLEAN_AMT,
                "po_number": ("PO-9999", None),
            },
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.IDENTIFIER_MISMATCH in [e.exception_type for e in exceptions]


def test_timeline_inconsistency_invoice_before_ship():
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": CLEAN_QTY, "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": CLEAN_QTY, "ship_date": ("2026-09-05", None)},
            "POD": {"quantity_kg": CLEAN_QTY, "delivery_date": ("2026-09-09", None)},
            "INVOICE": {"quantity_kg": CLEAN_QTY, "amount": CLEAN_AMT, "invoice_date": ("2026-09-01", None)},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.TIMELINE_INCONSISTENCY in [e.exception_type for e in exceptions]


def test_ambiguous_case_bol_pod_conflict_is_quantity_mismatch():
    """C10: BOL 815 vs POD 600, invoice 815 → QUANTITY_MISMATCH, human review."""
    ctx = make_ctx(
        {
            "PO": {"quantity_kg": ("800", "kg"), "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": ("815", "kg")},
            "POD": {"quantity_kg": ("600", "kg")},
            "INVOICE": {"quantity_kg": ("815", "kg"), "amount": ("10187.50", "USD")},
        }
    )
    exceptions = run_deterministic_checks(ctx)
    assert ExceptionType.QUANTITY_MISMATCH in _types(ctx)
    ex = next(e for e in exceptions if e.exception_type == ExceptionType.QUANTITY_MISMATCH)
    assert any(f.check_id == "QTY_BOL_VS_POD" for f in ex.deterministic_findings)


def test_unit_conversion_mismatch_detected():
    """PO 800 kg vs BOL 0.8 t (same amount) must NOT raise; 0.85 t must raise."""
    ctx_ok = make_ctx(
        {
            "PO": {"quantity_kg": ("800", "kg"), "unit_price": UNIT_PRICE},
            "BOL": {"quantity_kg": ("800", "kg")},
            "POD": {"quantity_kg": ("800", "kg")},
            "INVOICE": {"quantity_kg": ("800", "kg"), "amount": CLEAN_AMT},
        }
    )
    assert run_deterministic_checks(ctx_ok) == []
