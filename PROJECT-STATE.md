# PROJECT-STATE

_Last updated: 2026-09-17 (Day 1 of First Commit)_

**Current state:** `BUILDING` (Blueprint Phase 1–3 complete + tested; Phase 4 partial; Phase 5 API complete; Phase 6 partial; Phase 7 pending)

## Completed (with evidence)

- **Repo initialized** 2026-09-17 (history must match event dates — event rule §03/§05).
- **Canonical domain model** (Blueprint §21): `domain/models.py` — 7 entities + enums; pydantic-validated.
- **Infrastructure adapters** (ADR-001): `LocalDocumentStore` (S3 semantics), `AppRepository` (SQLite, one table per entity = future DynamoDB shape).
- **HTTP API** (Blueprint §24): all 8 endpoints + `/health`, correlation IDs (`X-Request-ID`), uniform error shape, idempotent uploads (checksum).
- **Extraction** (Phase 2, local): controlled `LABEL: value` parser over PDF (pypdf); every field has `raw_value`, `normalized_value`, `unit`, `location`, `confidence`; unrecognized values → warning, never a guess.
- **Reconciliation engine** (Phase 3): normalize → PO/BOL/POD/INVOICE checks → variance (reference source always explicit) → severity (explainable rule table). **No LLM involved.**
- **Investigation** (Phase 4, local): deterministic, evidence-constrained, rule-table recommendations, hypotheses tagged as hypotheses, `requires_human_review=true` always.
- **Human resolution** (Phase 5, API): state machine (OPEN/INVESTIGATING/PENDING_REVIEW → RESOLVED/REJECTED), decision persistence, full audit events.
- **Synthetic dataset** (Blueprint §26): 11 cases generated to `data/synthetic` + ground truth in `data/ground_truth`.
- **Tests: 36/36 passing** — unit (normalize/variance/checks), integration (full canonical flow incl. audit), evaluation (11/11 ground-truth match).

## Verification evidence (Day 1)

- `.venv/bin/python -m pytest -q` → **36 passed**.
- Evaluation: all 11 cases detect exactly the ground-truth exception types (C01–C11).
- Canonical demo case: PO 800 / BOL 815 / POD 815 / INV 840 → `QUANTITY_MISMATCH`, severity HIGH, exposure 312.50 (25 kg × $12.50), investigation + approval + audit trail all verified in `tests/integration/test_api_flow.py`.

## In progress

- Frontend (4 screens, Blueprint §25) — scaffold written, UI implementation starts Day 2.
- Evaluation metrics (precision/recall across the case suite, latency) — harness exists, measurement run pending.

## Waiting on (human)

- **AWS account** — not yet created. Needed for: Textract, Bedrock, S3, DynamoDB, Lambda/API Gateway, Amplify (full list + order: `docs/AWS-SETUP.md`).
- **GitHub repository + deploy key** — public key generated; user to add it (see chat / `NEXT-ACTIONS.md`).

## Blocked

- Phase 4 (Bedrock adapter), Phase 7 (deployment, seeded demo, live AWS pipeline) — **blocked on AWS account**. Everything else is unblocked and continues locally.

## Key assumptions (to confirm)

- PDF is the first supported document format (ADR-005).
- Exact-match on normalized values; tolerance configurable (ADR-006).
- No Cognito auth for the MVP demo (ADR-004).
- Synchronous processing per request (ADR-008).

## Active risks

See `RISKS.md`. Top: (1) AWS account not ready by Day 3 → mitigation: local-first design keeps all momentum; AWS work is concentrated in one deployment phase. (2) Textract quality on our controlled PDF layouts → mitigation: controlled layouts chosen for machine readability; controlled parser is the validated path.

## Next actions (ordered)

1. User: create GitHub repo + add deploy key → push this repo.
2. User: start AWS account creation (guide in `docs/AWS-SETUP.md`).
3. Frontend: Screen 1 (dashboard) + Screen 3 (investigation hero) against the local API.
4. Evaluation run: record precision/recall + per-case timing into `docs/evaluation.md`.
5. On AWS account ready: implement AWS adapters (S3, DynamoDB, Textract, Bedrock), deploy Lambda/API Gateway/Amplify, run the pipeline on AWS, re-run evaluation against deployed system.
