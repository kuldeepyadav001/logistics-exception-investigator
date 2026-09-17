"""End-to-end integration test: the canonical demo case through the full API.

Upload → store → extract → normalize → associate → detect → investigate →
decide → audit. Real generated PDFs, local backends, no LLM.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from infrastructure.db.local import AppRepository
from infrastructure.storage.local import LocalDocumentStore
from scripts.generate_dataset import CASES
from services.api.app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(
        repo=AppRepository(tmp_path / "app.sqlite3"),
        store=LocalDocumentStore(tmp_path / "documents"),
    )
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def canonical_files():
    """C02: PO 800 / BOL 815 / POD 815 / INVOICE 840 (dossier §26 demo case)."""
    from scripts.generate_dataset import build_case

    spec = next(c for c in CASES if c.case_id == "C02")
    files = build_case(spec)["files"]
    return {
        "PO": files["PO"],
        "BOL": files["BOL"],
        "POD": files["POD"],
        "INVOICE": files["INVOICE"],
    }


def _upload(client, shipment_id: str, doc_type: str, data: bytes) -> dict:
    resp = client.post(
        f"/shipments/{shipment_id}/documents",
        files={"file": (f"{doc_type}.pdf", data, "application/pdf")},
        data={"document_type": doc_type},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp.json()


def test_full_canonical_flow(client, canonical_files):
    # 1. create shipment
    r = client.post(
        "/shipments",
        json={
            "external_reference": "SHI-2026-0002",
            "purchase_order_id": "PO-2026-0002",
            "carrier_id": "BLUELINE LOGISTICS",
            "vendor_id": "ACME FREIGHT CO",
            "origin": "MUMBAI",
            "destination": "DELHI",
            "expected_delivery_date": "2026-09-09",
        },
    )
    assert r.status_code == 201, r.text
    shipment_id = r.json()["shipment"]["shipment_id"]

    # 2. upload + extract all four documents
    for doc_type, data in canonical_files.items():
        body = _upload(client, shipment_id, doc_type, data)
        assert body["duplicate"] is False
        assert body["extraction"]["status"] == "SUCCEEDED", body
        assert body["extraction"]["fields_extracted"] > 0

    # 3. shipment view: documents tracked, evidence normalized
    r = client.get(f"/shipments/{shipment_id}")
    assert r.status_code == 200
    body = r.json()
    assert len(body["documents"]) == 4
    assert all(d["extraction_status"] == "SUCCEEDED" for d in body["documents"])
    by_type = {d["document_type"]: d for d in body["documents"]}
    qty = {
        d["document_type"]: next(
            (e["normalized_value"] for e in body["evidence"] if e["document_id"] == d["document_id"] and e["field_name"] == "quantity_kg"),
            None,
        )
        for d in body["documents"]
    }
    assert qty["PO"] == "800"
    assert qty["BOL"] == "815"
    assert qty["POD"] == "815"
    assert qty["INVOICE"] == "840"
    # every evidence field is traceable to a source document
    for e in body["evidence"]:
        assert e["raw_value"]
        assert e["location"]

    # 4. investigate → deterministic exception + investigation
    r = client.post(f"/shipments/{shipment_id}/investigate")
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["exceptions"]) == 1
    ex = body["exceptions"][0]
    assert ex["exception_type"] == "QUANTITY_MISMATCH"
    assert ex["severity"] == "HIGH"
    assert ex["status"] == "PENDING_REVIEW"
    assert ex["estimated_exposure"] is not None and abs(ex["estimated_exposure"] - 312.5) < 0.01
    for f in ex["deterministic_findings"]:
        assert f["reference_source"] and f["observed_source"]
    assert len(body["investigations"]) == 1
    inv = body["investigations"][0]
    assert inv["requires_human_review"] is True
    assert inv["recommended_action"]
    assert inv["ai_summary"] is None  # Bedrock not configured yet — stated, not faked
    assert inv["model_metadata"]["provider"] == "deterministic-rules"

    exception_id = ex["exception_id"]

    # 5. full case view
    r = client.get(f"/exceptions/{exception_id}")
    assert r.status_code == 200
    case = r.json()
    assert case["exception"]["exception_type"] == "QUANTITY_MISMATCH"
    assert case["investigation"]["evidence_snapshot"]
    assert case["documents"]

    # 6. human approves
    r = client.post(
        f"/exceptions/{exception_id}/decision",
        json={
            "decision": "APPROVE",
            "reviewer_id": "analyst-01",
            "reviewer_note": "Carrier confirmed 815 kg delivered; requesting credit note for 25 kg overbilling.",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["exception"]["status"] == "RESOLVED"

    # 7. audit trail: every important step is recorded
    r = client.get(f"/exceptions/{exception_id}/audit")
    assert r.status_code == 200
    actions = [e["action"] for e in r.json()["audit_events"]]
    assert "exception.created" in actions
    assert "investigation.created" in actions
    assert "decision.received" in actions
    assert "exception.resolved" in actions

    # 8. deciding again is rejected (state machine)
    r = client.post(
        f"/exceptions/{exception_id}/decision",
        json={"decision": "REJECT", "reviewer_id": "analyst-01"},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "INVALID_STATE"


def test_duplicate_upload_is_idempotent(client, canonical_files):
    r = client.post("/shipments", json={"external_reference": "DUP-1"})
    shipment_id = r.json()["shipment"]["shipment_id"]
    first = _upload(client, shipment_id, "PO", canonical_files["PO"])
    second = _upload(client, shipment_id, "PO", canonical_files["PO"])
    assert second["duplicate"] is True
    assert second["document"]["document_id"] == first["document"]["document_id"]
    r = client.get(f"/shipments/{shipment_id}")
    assert len(r.json()["documents"]) == 1


def test_error_shapes_and_correlation(client):
    r = client.get("/shipments/does-not-exist")
    assert r.status_code == 404
    body = r.json()
    assert body["error"]["code"] == "SHIPMENT_NOT_FOUND"
    assert r.headers.get("x-request-id")

    r = client.get("/exceptions/missing")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "EXCEPTION_NOT_FOUND"


def test_health_reports_local_backends(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["environment"] == "local"
    assert body["backends"]["dynamodb"] == "sqlite"
