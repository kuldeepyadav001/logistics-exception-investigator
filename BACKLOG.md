# BACKLOG

## P0 — Submission core (dossier §0B)
- [x] Document upload (API, idempotent)
- [x] Extraction (local controlled parser)
- [x] Normalization
- [x] Shipment association (explicit upload + reference verification)
- [x] One strong deterministic exception (quantity mismatch) + 6 more types
- [ ] Evidence comparison UI (Screen 2/3)
- [x] AI investigation summary grounded in evidence (deterministic version; **Bedrock version pending account**)
- [x] Recommendation (rule table)
- [x] Human approval (API + state machine)
- [x] Audit record
- [ ] **Deployed on AWS** (pending account) — S3/Textract/Lambda/API GW/DynamoDB/Bedrock + hosted UI

## P1 — Reliability
- [ ] Run evaluation suite against deployed (AWS) pipeline; record results
- [ ] Latency + cost-per-case measurement (Phase 6)
- [ ] Failure/retry handling on AWS paths (Textract/Bedrock errors → safe fallbacks)
- [ ] Baseline experiment: time a human on 3 cases (identify exception + resolution) vs system
- [ ] Load a few extra clean/edge cases into the suite

## P2 — Presentation
- [ ] Severity ranking on dashboard
- [ ] Search/filter (API filters exist; UI)
- [ ] Communication draft (vendor/carrier email) — AI feature, post-MVP polish
- [ ] Evidence visualization (side-by-side conflicting values with source highlights)
- [ ] Demo recording (3-minute script: dossier §18)

## P3 — Future only (explicitly out of hackathon scope)
- [ ] TMS/ERP integrations, carrier APIs, email ingestion
- [ ] Autonomous disputes (never without approval — dossier §6)
- [ ] Multi-tenant SaaS controls, Cognito/RBAC hardening
