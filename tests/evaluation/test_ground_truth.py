"""Ground-truth evaluation (Blueprint §26, Phase 6).

Runs every synthetic case through the full pipeline and compares detected
exception types against the machine-readable ground truth. This is the
reproducible evaluation harness; results are recorded, not assumed.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from infrastructure.db.local import AppRepository
from infrastructure.storage.local import LocalDocumentStore
from scripts.generate_dataset import CASES, build_case
from services.api.app import create_app


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("eval")
    app = create_app(
        repo=AppRepository(tmp / "app.sqlite3"),
        store=LocalDocumentStore(tmp / "documents"),
    )
    with TestClient(app) as c:
        yield c


def _run_case(client, spec) -> set[str]:
    meta = build_case(spec)
    files = meta["files"]
    m = meta["metadata"]
    r = client.post(
        "/shipments",
        json={
            "external_reference": m["shipment_ref"],
            "purchase_order_id": m["po_number"],
            "carrier_id": "BLUELINE LOGISTICS",
            "vendor_id": "ACME FREIGHT CO",
            "origin": "MUMBAI",
            "destination": "DELHI",
        },
    )
    shipment_id = r.json()["shipment"]["shipment_id"]
    for doc_type, data in files.items():
        r = client.post(
            f"/shipments/{shipment_id}/documents",
            files={"file": (f"{doc_type}.pdf", data, "application/pdf")},
            data={"document_type": "INVOICE" if doc_type == "INVOICE_2" else doc_type},
        )
        assert r.status_code in (200, 201), (spec.case_id, r.text)
        assert r.json()["extraction"]["status"] == "SUCCEEDED", (spec.case_id, r.text)
    r = client.post(f"/shipments/{shipment_id}/investigate")
    assert r.status_code == 200, (spec.case_id, r.text)
    return {e["exception_type"] for e in r.json()["exceptions"]}


@pytest.mark.parametrize("spec", CASES, ids=[c.case_id for c in CASES])
def test_case_matches_ground_truth(client, spec):
    detected = _run_case(client, spec)
    expected = set(spec.expected_exception_types)
    assert detected == expected, (
        f"{spec.case_id} ({spec.description}): expected {sorted(expected)}, detected {sorted(detected)}"
    )


def test_all_cases_summary_printed(client, capsys):
    rows = []
    for spec in CASES:
        detected = _run_case(client, spec)
        expected = set(spec.expected_exception_types)
        ok = detected == expected
        rows.append(f"{spec.case_id} {'PASS' if ok else 'FAIL'} expected={sorted(expected)} detected={sorted(detected)}")
    for row in rows:
        print(row)
