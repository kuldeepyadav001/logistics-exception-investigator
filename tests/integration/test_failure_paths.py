"""Failure-path tests (P1 reliability, Blueprint §27).

The system must degrade safely: no invented values, explicit failures,
state-machine protection, ambiguous evidence preserved (not silently resolved).
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from infrastructure.db.local import AppRepository
from infrastructure.storage.local import LocalDocumentStore
from scripts.generate_dataset import CASES, build_case
from services.api.app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        repo=AppRepository(tmp_path / "app.sqlite3"),
        store=LocalDocumentStore(tmp_path / "documents"),
    )
    with TestClient(app) as c:
        yield c


def _new_shipment(client) -> str:
    r = client.post("/shipments", json={"external_reference": "FAIL-1"})
    assert r.status_code == 201
    return r.json()["shipment"]["shipment_id"]


def test_unsupported_content_type_rejected(client):
    sid = _new_shipment(client)
    r = client.post(
        f"/shipments/{sid}/documents",
        files={"file": ("x.zip", b"PK\x03\x04", "application/zip")},
        data={"document_type": "PO"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "UNSUPPORTED_CONTENT_TYPE"


def test_invalid_document_type_rejected(client):
    sid = _new_shipment(client)
    r = client.post(
        f"/shipments/{sid}/documents",
        files={"file": ("x.pdf", b"%PDF-1.4", "application/pdf")},
        data={"document_type": "BANK_STATEMENT"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_DOCUMENT_TYPE"


def test_corrupt_pdf_marks_failed_never_invents(client):
    sid = _new_shipment(client)
    r = client.post(
        f"/shipments/{sid}/documents",
        files={"file": ("broken.pdf", b"%PDF-1.3 this is not a real pdf body", "application/pdf")},
        data={"document_type": "PO"},
    )
    # extraction FAILED is acceptable (surface it) or PARTIAL; must never SUCCEED with invented fields
    body = r.json()
    assert body["document"]["extraction_status"] in ("FAILED", "PARTIAL")
    if body["document"]["extraction_status"] == "FAILED":
        assert body["extraction"]["errors"]

    # investigate still works and does not crash
    r = client.post(f"/shipments/{sid}/investigate")
    assert r.status_code == 200


def test_unparseable_values_produce_partial_not_garbage(client):
    sid = _new_shipment(client)
    text = (
        "PURCHASE ORDER\n"
        "PURCHASE ORDER NUMBER: PO-1\n"
        "ORDERED QUANTITY: eight hundred kg\n"   # not parseable → skipped, warned
        "UNIT PRICE (PER KG): USD 12.50\n"
    )
    r = client.post(
        f"/shipments/{sid}/documents",
        files={"file": ("po.txt", text.encode(), "text/plain")},
        data={"document_type": "PO"},
    )
    body = r.json()
    assert body["extraction"]["status"] in ("SUCCEEDED", "PARTIAL")
    warnings = " ".join(body["extraction"]["warnings"])
    assert "unrecognized value" in warnings or "no recognized fields" in warnings

    # the shipment view must not contain an invented quantity
    r = client.get(f"/shipments/{sid}")
    for e in r.json()["evidence"]:
        if e["field_name"] == "quantity_kg":
            pytest.fail("invented quantity field found for unparseable input")


def test_missing_documents_create_evidence_missing_exception(client):
    sid = _new_shipment(client)
    # upload only a PO (clean text) — no BOL/POD/INVOICE
    po = (
        "PURCHASE ORDER\n"
        "PURCHASE ORDER NUMBER: PO-7\n"
        "ORDERED QUANTITY: 800 kg\n"
        "UNIT PRICE (PER KG): USD 12.50\n"
    )
    client.post(
        f"/shipments/{sid}/documents",
        files={"file": ("po.txt", po.encode(), "text/plain")},
        data={"document_type": "PO"},
    )
    r = client.post(f"/shipments/{sid}/investigate")
    types = [e["exception_type"] for e in r.json()["exceptions"]]
    assert "EVIDENCE_MISSING" in types


def test_ambiguous_case_preserves_both_conflicting_values(client):
    """C10: BOL 815 vs POD 600 — system must present the conflict, not pick."""
    spec = next(c for c in CASES if c.case_id == "C10")
    result = build_case(spec)
    sid = _new_shipment(client)
    for key, data in result["files"].items():
        r = client.post(
            f"/shipments/{sid}/documents",
            files={"file": (f"{key}.pdf", data, "application/pdf")},
            data={"document_type": "INVOICE" if key == "INVOICE_2" else key},
        )
        assert r.status_code == 201, r.text
    r = client.post(f"/shipments/{sid}/investigate")
    body = r.json()
    ex = next(e for e in body["exceptions"] if e["exception_type"] == "QUANTITY_MISMATCH")
    check_ids = [f["check_id"] for f in ex["deterministic_findings"]]
    assert "QTY_BOL_VS_POD" in check_ids

    # both conflicting delivered values must be visible in the evidence
    r = client.get(f"/exceptions/{ex['exception_id']}")
    qty_values = {
        e["normalized_value"] for e in r.json()["evidence"] if e["field_name"] == "quantity_kg"
    }
    assert "815" in qty_values and "600" in qty_values
    assert r.json()["investigation"]["requires_human_review"] is True


def test_terminal_exception_rejects_second_decision(client):
    sid = _new_shipment(client)
    spec = next(c for c in CASES if c.case_id == "C02")
    result = build_case(spec)
    for key, data in result["files"].items():
        client.post(
            f"/shipments/{sid}/documents",
            files={"file": (f"{key}.pdf", data, "application/pdf")},
            data={"document_type": key},
        )
    r = client.post(f"/shipments/{sid}/investigate")
    eid = r.json()["exceptions"][0]["exception_id"]
    r = client.post(
        f"/exceptions/{eid}/decision",
        json={"decision": "REJECT", "reviewer_id": "a1", "reviewer_note": "not our flow"},
    )
    assert r.status_code == 201
    r = client.post(
        f"/exceptions/{eid}/decision", json={"decision": "APPROVE", "reviewer_id": "a2"}
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_STATE"
    # audit shows exactly one decision
    r = client.get(f"/exceptions/{eid}/audit")
    decisions = [a for a in r.json()["audit_events"] if a["action"] == "decision.received"]
    assert len(decisions) == 1


def test_seed_endpoint_reproducible_and_idempotent(client):
    r = client.post("/demo/seed?case_id=C02")
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["already_seeded"] is False
    assert len(body["exceptions"]) == 1
    assert body["exceptions"][0]["exception_type"] == "QUANTITY_MISMATCH"
    first = body["shipment_id"]

    # seed again → same shipment, no duplicates
    r = client.post("/demo/seed?case_id=C02")
    assert r.json()["already_seeded"] is True
    assert r.json()["shipment_id"] == first
    r = client.get(f"/shipments/{first}")
    assert len(r.json()["documents"]) == 4  # still exactly 4


def test_seed_unknown_case_404(client):
    r = client.post("/demo/seed?case_id=C99")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "DEMO_CASE_NOT_FOUND"
