# Architecture

## System overview

```
┌─────────────┐        ┌────────────────────────────────────────────────────┐
│  React UI   │  HTTP  │                     API (FastAPI)                  │
│  (Vite/TS/  │◄──────►│  8 contract endpoints + /health  (§24)             │
│  Tailwind)  │        └───────────────┬────────────────────────────────────┘
─────────────┘                        │
                    ┌──────────────────┼──────────────────────────────┐
                    ▼                  ▼                              ▼
          ┌──────────────────┐ ┌──────────────────┐  ┌──────────────────────────┐
          │  DocumentStore   │ │  AppRepository   │  │   Processing pipeline    │
          │  (S3 semantics)  │ │  (DynamoDB sem.) │  │  upload → extract →      │
          │  today: local FS │ │  today: SQLite   │  │  normalize → reconcile → │
          │  later: S3       │ │  later: DynamoDB │  │  investigate → decide    │
          └──────────────────┘ └──────────────────┘  └────────────┬─────────────┘
                                                                  │
                                              ┌───────────────────┼───────────────────┐
                                              ▼                   ▼                   ▼
                                   ┌─────────────────┐ ┌──────────────────┐ ┌──────────────────┐
                                   │ Extraction      │ │ Reconciliation   │ │ Investigation    │
                                   │ today: controlled│ │ engine (pure     │ │ today: rule-table│
                                   │ PDF parser      │ │ deterministic,   │ │ + tagged        │
                                   │ later: Textract │ │ no LLM)          │ │ hypotheses;      │
                                   └─────────────────┘ └──────────────────┘ │ later: Bedrock   │
                                                                              └──────────────────┘
```

## Design principle: adapters (ADR-001)

Each AWS dependency has an interface + local backend now + AWS backend later:

| Interface | Local backend (today) | AWS backend (Day 3–4) |
| --- | --- | --- |
| `DocumentStore` | filesystem under `data/runtime/documents` | S3 |
| `AppRepository` | SQLite, one table per entity | DynamoDB, one table per entity |
| `Extractor` | controlled `LABEL: value` parser (pypdf) | Textract AnalyzeExpense/AnalyzeDocument + same normalization layer |
| `Investigator` | deterministic rule table (schema-validated output) | Bedrock Claude with the §23 input/output contract + schema validation |

`GET /health` reports which backend is active — the demo can never misrepresent the environment.

## Data flow (one upload)

1. `POST /shipments` → Shipment created (audit: `shipment.created`).
2. `POST /shipments/{id}/documents` (multipart + `document_type`):
   - checksum (SHA-256) → idempotency check (ADR-010)
   - bytes → DocumentStore; Document record `RUNNING`
   - Extractor → `ExtractionResult` (fields with raw+normalized+unit+location+confidence)
   - EvidenceField rows stored; Document → `SUCCEEDED|PARTIAL|FAILED` (never invented values)
   - audit: `document.uploaded`, `extraction.<status>`
3. `POST /shipments/{id}/investigate`:
   - ShipmentContext = shipment + documents + evidence
   - **deterministic checks** → exceptions (findings always name reference + observed sources; variances absolute + %)
   - merged per type; severity from explainable rule table
   - per exception: Investigation built from evidence snapshot (raw evidence immutable)
   - status → `PENDING_REVIEW`; audit events recorded
4. `GET /exceptions/{id}` → full case (exception + investigation + evidence + documents + decisions).
5. `POST /exceptions/{id}/decision` → state machine validation → `RESOLVED|REJECTED` + audit.

## Failure handling (dossier §27)

- Unreadable/unparseable document → `FAILED`, error surfaced, no values invented.
- Unrecognized unit/date/amount → field skipped + warning (`PARTIAL`), never guessed.
- Missing document type → `EVIDENCE_MISSING` exception (not silent).
- Conflicting BOL vs POD → both values preserved; exception states the conflict; human decides.
- Duplicate upload (byte-identical) → idempotent skip (ADR-010).
- Decision on terminal exception → 409 `INVALID_STATE`.
- (Phase 6+) AI/extractor service failures on AWS → deterministic results stay available; retry only idempotent ops.

## Security (dossier §15, prototype level)

- Synthetic data only; no PII in the dataset.
- Credentials only via env vars; `.env` gitignored; nothing secret in code/docs/commits.
- LLM never performs actions; recommendations only; `requires_human_review=true` always for consequential resolution.
- CORS open for the prototype; locked per environment at deploy (ADR-004).
- Audit events on every consequential transition (immutable append in the store).
