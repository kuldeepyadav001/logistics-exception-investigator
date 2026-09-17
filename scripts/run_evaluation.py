"""Reproducible evaluation run (Phase 6, Blueprint §26/§14).

Runs every synthetic case through the full pipeline and records:
- per-case detection vs ground truth (TP/FP/FN)
- precision / recall / F1 over the whole suite
- per-case end-to-end latency (upload → evidence → investigation)

Output: a committed JSON report under docs/ so every number quoted in the
demo/write-up is a MEASURED RESULT, not an assumption.

Usage:
    .venv/bin/python -m scripts.run_evaluation
"""
from __future__ import annotations

import json
import statistics
import tempfile
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    from fastapi.testclient import TestClient

    from infrastructure.db.local import AppRepository
    from infrastructure.storage.local import LocalDocumentStore
    from scripts.generate_dataset import CASES, build_case
    from services.api.app import create_app

    tmp = Path(tempfile.mkdtemp())
    app = create_app(
        repo=AppRepository(tmp / "app.sqlite3"),
        store=LocalDocumentStore(tmp / "documents"),
    )
    client = TestClient(app)

    rows = []
    tp = fp = fn = 0
    latencies: list[float] = []

    for spec in CASES:
        t0 = time.perf_counter()
        result = build_case(spec)
        m = result["metadata"]
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
        assert r.status_code == 201, (spec.case_id, r.text)
        sid = r.json()["shipment"]["shipment_id"]

        extraction_ok = True
        for key, data in result["files"].items():
            r = client.post(
                f"/shipments/{sid}/documents",
                files={"file": (f"{key}.pdf", data, "application/pdf")},
                data={"document_type": "INVOICE" if key == "INVOICE_2" else key},
            )
            assert r.status_code == 201, (spec.case_id, r.text)
            if r.json()["extraction"]["status"] != "SUCCEEDED":
                extraction_ok = False

        r = client.post(f"/shipments/{sid}/investigate")
        assert r.status_code == 200, (spec.case_id, r.text)
        latency = time.perf_counter() - t0
        latencies.append(latency)

        detected = sorted(e["exception_type"] for e in r.json()["exceptions"])
        expected = sorted(spec.expected_exception_types)
        det, exp = set(detected), set(expected)
        tpc, fpc, fnc = len(det & exp), len(det - exp), len(exp - det)
        tp += tpc
        fp += fpc
        fn += fnc
        rows.append(
            {
                "case_id": spec.case_id,
                "description": spec.description,
                "expected": expected,
                "detected": detected,
                "correct": fpc == 0 and fnc == 0,  # no extra types, no missed types
                "extraction_succeeded": extraction_ok,
                "latency_s": round(latency, 3),
            }
        )

    precision = tp / (tp + fp) if (tp + fp) else None
    recall = tp / (tp + fn) if (tp + fn) else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None
        else None
    )
    correct = sum(1 for r in rows if r["correct"])

    report = {
        "measured_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "date": date.today().isoformat(),
        "environment": "local adapters (filesystem/sqlite/controlled-parser/rule-table)",
        "engine": "deterministic — no LLM used for detection",
        "cases_total": len(rows),
        "cases_fully_correct": correct,
        "detection": {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "definition": "per-case exact-type-set: TP = detected types that are expected; FP = extra types; FN = missed expected types",
        },
        "latency_seconds": {
            "per_case": {r["case_id"]: r["latency_s"] for r in rows},
            "min": round(min(latencies), 3),
            "median": round(statistics.median(latencies), 3),
            "max": round(max(latencies), 3),
            "total": round(sum(latencies), 3),
        },
        "rows": rows,
        "notes": [
            "Local pipeline on generated controlled PDFs; Textract/Bedrock measurements pending AWS deployment.",
            "Latency covers upload+extraction+investigation per case on the sandbox machine; not an AWS production figure.",
        ],
    }

    out = ROOT / "docs" / f"evaluation-results-{report['date']}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"{'CASE':6} {'CORRECT':8} {'EXPECTED':38} {'DETECTED'}")
    for r in rows:
        print(
            f"{r['case_id']:6} {'PASS' if r['correct'] else 'FAIL':8} "
            f"{','.join(r['expected']) or '—':38} {','.join(r['detected']) or '—'}"
        )
    print(
        f"\n{correct}/{len(rows)} cases fully correct | precision={precision} recall={recall} f1={f1}"
    )
    print(
        f"latency min/median/max = {report['latency_seconds']['min']} / "
        f"{report['latency_seconds']['median']} / {report['latency_seconds']['max']} s"
    )
    print(f"report written to {out}")


if __name__ == "__main__":
    main()
