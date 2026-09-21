# DECISIONS (ADRs)

Format: decision / context / alternatives / rationale / consequences / reversal.

## ADR-001 — Local-first adapter architecture (no AWS account yet)

- **Decision:** All AWS services (S3, DynamoDB, Textract, Bedrock) sit behind interfaces with local backends: filesystem storage, SQLite repository, controlled PDF parser, deterministic rule-table investigation. AWS implementations are added behind the same interfaces when the account exists.
- **Context:** The user has no AWS account yet (created during the event window). The dossier requires genuine AWS usage in the final demo, but Day 1 momentum cannot wait for account setup.
- **Alternatives:** (a) Stop building until AWS is ready — wastes Day 1–2; (b) fake AWS usage — violates dossier §12 "AWS must be genuine" and event rules.
- **Rationale:** Vertical progress now; genuine AWS later in one concentrated deployment phase. Interface stability is enforced by the canonical data model.
- **Consequences:** Every AWS adapter must be tested before the demo; `/health` reports which backend is active so the demo never misrepresents the environment.
- **Reversal:** N/A (additive).

## ADR-002 — FastAPI for the API layer

- **Decision:** FastAPI + Pydantic for the HTTP API; handlers structured so each endpoint maps 1:1 to a Lambda function at deploy time.
- **Context:** Blueprint §24 requires 8 endpoints with schema validation, predictable errors, correlation IDs. Deploy target is API Gateway + Lambda.
- **Alternatives:** (a) AWS chalice/serverless framework scaffolding — needs account first, more ceremony; (b) Flask — weaker schema validation story; (c) Express/TS backend — blueprint specifies Python for backend services.
- **Rationale:** FastAPI gives strict Pydantic contracts (Blueprint §20), TestClient for integration tests, and trivial Lambda wrapping later.
- **Reversal:** Endpoint contracts are framework-agnostic; swapping the framework is contained to `services/api`.

## ADR-003 — `domain/` package for canonical models

- **Decision:** Add a top-level `domain/` package holding the §21 canonical models, shared by all services (extension of the §32 layout).
- **Context:** §32 lists `services/*` and `infrastructure/` but not a shared model home; services must not import each other's internals.
- **Rationale:** Keeps domain boundaries explicit (the one thing §32 insists survives layout changes).
- **Reversal:** Rename/move only.

## ADR-004 — No Cognito for the MVP demo

- **Decision:** The deployed hackathon MVP ships without user authentication (single-operator demo).
- **Context:** Blueprint §20: "Cognito **if** authentication is required." A 3-minute judge demo is single-user; auth adds deploy risk and consumes event time.
- **Consequences:** Documented in RISKS.md; the decision is explicit in the write-up ("auth is a deployment-phase concern, out of MVP scope").
- **Reversal:** Adding Cognito later is additive.

## ADR-005 — PDF as the first supported document format; controlled synthetic layout

- **Decision:** MVP ingests PDFs of the 4 canonical document types; synthetic documents use a clean `LABEL: value` layout (still realistic-looking, machine-readable).
- **Context:** §38 open question 1 (formats) — answer: PDF first, smallest credible set.
- **Rationale:** One format = one reliable extraction path; the layout is chosen so both the local controlled parser and Textract can be validated deterministically.
- **Reversal:** New formats are additive extractor branches.

## ADR-006 — Exact match on normalized values; configurable tolerance

- **Decision:** Default reconciliation uses exact comparison of normalized values; `quantity_tolerance_kg` / `amount_tolerance` are config, not magic numbers.
- **Rationale:** Keeps the engine explainable (§22 Step 5) and lets evaluation tune thresholds visibly.
- **Reversal:** Config change only.

## ADR-007 — Git history starts 2026-09-17

- **Decision:** Repository initialized on Day 1; no pre-event code is ported in.
- **Context:** Event rule §03/§05: "A repository whose history does not match the event dates disqualifies the whole team."
- **Rationale:** Compliance + honesty. Pre-event artifacts (the dossier, research) are referenced, not committed as code.

## ADR-008 — Synchronous processing for the MVP

- **Decision:** Upload → extraction → evidence happens inside the HTTP request; no queues/Step Functions yet.
- **Context:** Blueprint §20: "Start with direct Lambda orchestration if sufficient."
- **Rationale:** Simplest path to the demo; latency measured in Phase 6 before deciding whether async earns its complexity.
- **Reversal:** Async is additive (states already exist: PENDING/RUNNING/SUCCEEDED/PARTIAL/FAILED).

## ADR-009 — PARTIAL_SHIPMENT severity capped at MEDIUM

- **Decision:** A PO>BOL>POD-consistent shortfall is classified PARTIAL_SHIPMENT at MEDIUM severity even for large percentage variance.
- **Context:** A shortfall may be an authorized partial delivery; the engine must not over-alarm where a human decision (verify with carrier) is the correct outcome.
- **Consequences:** Documented in `checks.py` docstring; covered by unit test.
- **Reversal:** One-line rule change in `_classify`.

## ADR-010 — Duplicate invoice vs duplicate upload are different things

- **Decision:** Upload idempotency = byte-identical file (checksum) for same shipment+type → skip reprocessing (Blueprint §27). Duplicate **invoice** = two registered invoices sharing (invoice_number, amount) → exception. Synthetic C04 models the realistic case: same number+amount resubmitted on a later date (distinct bytes).
- **Context:** A byte-identical re-upload that we also flagged as a "duplicate invoice exception" would confuse the demo (it's the user re-clicking, not a billing error).
- **Reversal:** Rule is isolated in `upload_document` + `_check_duplicate_invoices`.
## ADR-011 — Pivot: hackathon window closed → company/pilot track (2026-09-21)

- **Decision:** The First Commit window (Sep 17–20) closed without submission (laptop lost Sep 19; AWS account never created). Per the dossier's two-narrative strategy (§2), the project's primary objective is now **Narrative B: company pilot** — the same prototype, finished to pilot-grade standard.
- **Context:** Dossier §41: the hackathon and company goals are separate gates; the strategic goal was "one technically credible, measurable prototype" serving both. Nothing technical was lost: 55 tests, 14/14 measured evaluation, public repo, full project memory.
- **Consequences:**
  - Deployment target becomes **portable first**: single Docker container that runs anywhere (any laptop/VM/cloud) — AWS becomes optional, not a dependency.
  - The AI layer becomes **provider-pluggable** (ADR-012) instead of Bedrock-only.
  - Deliverables shift: pitch kit + pilot design + hardened demo replace video/write-up/submission.
  - The repo's Sep-17–20 history is honest and useful (shows real engineering velocity); no relabeling.
- **Reversal:** If an AWS account exists later, the AWS adapters (ADR-001) can still be added behind the same interfaces; the Docker path remains valid either way.

## ADR-012 — Pluggable LLM investigation layer (no hard cloud dependency)

- **Decision:** The AI investigation layer is a provider-agnostic adapter: `LEI_LLM_PROVIDER=none|anthropic|openai` + key via env (works with any OpenAI-compatible base URL, incl. local models). Default `none` → deterministic rule-table investigation. Output is always schema-validated; invalid model output is rejected and the deterministic result is used; `requires_human_review` is forced true.
- **Context:** Company track = the demo must work in ANY environment a pitch counterpart provides (or our own box). Bedrock-only would make the AI demo hostage to an AWS account.
- **Rationale:** Keeps the §23 contract (controlled input, structured output, no invented evidence, no autonomous action) while making the AI layer demonstrable with a $5 API key.
- **Consequences:** AWS deployment (later, if desired) adds a Bedrock provider implementing the same protocol — additive.
- **Reversal:** Env change only; the deterministic core is untouched.
