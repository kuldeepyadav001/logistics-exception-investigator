# Data Model (Blueprint §21)

Source of truth: `domain/models.py` (pydantic). Storage: one table per entity
(today SQLite; tomorrow DynamoDB with the same shape — ADR-001).

**Design rule:** raw document evidence is never overwritten by AI-generated
conclusions. Conclusions reference evidence; they do not become evidence.

## Entities

### Shipment
`shipment_id`, `external_reference`, `purchase_order_id?`, `carrier_id?`, `vendor_id?`, `origin?`, `destination?`, `expected_delivery_date?`, `status`, `created_at`, `updated_at`

### Document
`document_id`, `shipment_id`, `document_type` (PO|BOL|POD|INVOICE|OTHER), `s3_key`, `original_filename`, `extraction_status` (PENDING|RUNNING|SUCCEEDED|PARTIAL|FAILED), `uploaded_at`, `checksum` (SHA-256)

### EvidenceField
`evidence_id`, `document_id`, `field_name`, `normalized_value`, `raw_value`, `unit?`, `location?` (line/page in source), `extraction_confidence`, `created_at`

### DeterministicFinding
`check_id`, `description`, `reference_source`, `observed_source`, `reference_value?`, `observed_value?`, `absolute_variance?`, `percentage_variance?`, `metadata{}`
— a variance is never reported without the compared records named.

### Exception
`exception_id`, `shipment_id`, `exception_type`, `severity` (LOW|MEDIUM|HIGH|CRITICAL), `status` (OPEN|INVESTIGATING|PENDING_REVIEW|RESOLVED|REJECTED), `deterministic_findings[]`, `affected_fields[]`, `estimated_exposure?`, `exposure_currency?`, `created_at`, `updated_at`

Exception types: `QUANTITY_MISMATCH`, `AMOUNT_MISMATCH`, `DUPLICATE_INVOICE`, `IDENTIFIER_MISMATCH`, `PARTIAL_SHIPMENT`, `TIMELINE_INCONSISTENCY`, `EVIDENCE_MISSING`.

### Investigation
`investigation_id`, `exception_id`, `evidence_snapshot[]` (frozen EvidenceField copies), `deterministic_findings[]`, `ai_summary?` (null until Bedrock fills it — stated, never faked), `plausible_causes[]` (each tagged hypothesis), `recommended_action?`, `uncertainty[]`, `model_metadata{}` (provider/model/version), `requires_human_review` (always true for consequential resolution), `created_at`

### Decision
`decision_id`, `exception_id`, `reviewer_id`, `decision` (APPROVE|REJECT|EDIT_AND_APPROVE), `reviewer_note?`, `final_action?`, `created_at`

### AuditEvent
`audit_event_id`, `entity_type`, `entity_id`, `actor_type` (USER|SYSTEM|AI), `actor_id?`, `action`, `before_ref?`, `after_ref?`, `timestamp`
Append-only in the store.

## State machine (exception lifecycle)

```
OPEN ──investigate──► PENDING_REVIEW ──APPROVE/EDIT_AND_APPROVE──► RESOLVED
   ▲                        │
   │                 REJECT ▼
   └─────────────────── REJECTED  (terminal; re-investigation creates new findings on next run)
```

## Storage mapping

| Entity | Table (SQLite now / DynamoDB later) | Key |
| --- | --- | --- |
| Shipment | shipments | shipment_id |
| Document | documents | document_id (index: shipment_id) |
| EvidenceField | evidence_fields | evidence_id (index: document_id) |
| Exception | exceptions | exception_id (index: shipment_id) |
| Investigation | investigations | investigation_id (index: exception_id) |
| Decision | decisions | decision_id (index: exception_id) |
| AuditEvent | audit_events | audit_event_id (index: entity_type, entity_id) |
