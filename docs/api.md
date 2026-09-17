# API Contract (Blueprint §24)

Base URL (local): `http://localhost:8000` · Interactive docs: `http://localhost:8000/docs`

Conventions:
- every response carries `X-Request-ID` (pass one in to correlate).
- errors: `{"error": {"code": "...", "message": "...", "request_id": "..."}}`.
- uploads are idempotent per (shipment, document_type, SHA-256 checksum).

## Endpoints

### `GET /health`
Backend active-report (local vs AWS) + status.

### `POST /shipments` → 201
```json
{"external_reference": "SHI-2026-0002", "purchase_order_id": "PO-2026-0002",
 "carrier_id": "...", "vendor_id": "...", "origin": "MUMBAI",
 "destination": "DELHI", "expected_delivery_date": "2026-09-09"}
```

### `POST /shipments/{shipment_id}/documents` → 201 (multipart)
Fields: `file` (pdf/txt/md), `document_type` (PO|BOL|POD|INVOICE|OTHER).
Response: `document` (+ `duplicate: true` on idempotent re-upload) and `extraction` (`status`, `fields_extracted`, `warnings`, `errors`).

### `GET /shipments/{shipment_id}`
`{shipment, documents[], evidence[], exceptions[]}` — evidence entries carry `raw_value`, `normalized_value`, `unit`, `location`, `extraction_confidence` (traceability).

### `POST /shipments/{shipment_id}/investigate` → 200
Runs deterministic checks + creates/refreshes exceptions and investigations.
Response: `{shipment_id, exceptions_created[], exceptions[], investigations[]}`.

### `GET /exceptions?shipment_id=&status=&exception_type=` → 200
Summary list.

### `GET /exceptions/{exception_id}` → 200
Full case: `{exception, investigation, evidence[], documents[], decisions[]}`.

### `POST /exceptions/{exception_id}/decision` → 201
```json
{"decision": "APPROVE | REJECT | EDIT_AND_APPROVE", "reviewer_id": "analyst-01",
 "reviewer_note": "optional", "final_action": "optional override"}
```
Allowed from `OPEN | INVESTIGATING | PENDING_REVIEW`; else 409 `INVALID_STATE`.
`APPROVE`/`EDIT_AND_APPROVE` → `RESOLVED`; `REJECT` → `REJECTED`.

### `GET /exceptions/{exception_id}/audit` → 200
Chronological audit events for the exception.

## Canonical demo flow (case C02)

```bash
B=http://localhost:8000
SID=$(curl -s -X POST $B/shipments -H 'content-type: application/json' \
  -d '{"external_reference":"SHI-2026-0002","purchase_order_id":"PO-2026-0002"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["shipment"]["shipment_id"])')

for T in PO BOL POD INVOICE; do
  curl -s -X POST $B/shipments/$SID/documents \
    -F "file=@data/synthetic/C02/${T}_SHI-2026-0002.pdf" -F "document_type=$T" > /dev/null
done

curl -s -X POST $B/shipments/$SID/investigate          # → QUANTITY_MISMATCH, HIGH, exposure 312.50
EID=$(curl -s "$B/exceptions?shipment_id=$SID" | python3 -c 'import sys,json;print(json.load(sys.stdin)["exceptions"][0]["exception_id"])')

curl -s $B/exceptions/$EID                              # full evidence-backed case
curl -s -X POST $B/exceptions/$EID/decision -H 'content-type: application/json' \
  -d '{"decision":"APPROVE","reviewer_id":"analyst-01","reviewer_note":"credit note requested"}'
curl -s $B/exceptions/$EID/audit                        # full trail
```

## Evidence field names (extraction → engine contract)

`po_number`, `shipment_reference`, `invoice_number`, `carrier_id`, `vendor_id`, `origin`, `destination`,
`quantity_kg` (unit `kg`), `amount` (unit = currency), `unit_price` (unit = currency, per kg),
`ship_date`, `delivery_date`, `invoice_date`, `expected_delivery_date` (ISO dates).
