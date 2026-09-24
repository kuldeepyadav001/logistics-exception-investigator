# Company Pitch Kit — Logistics Exception Investigator

> Audience: operations / finance leaders who own freight-audit or
> invoice-reconciliation work. Goal of first conversation: **validation, not a
> sale** (dossier §36). Every number below is a MEASURED RESULT from this repo
> (`docs/evaluation-results-*.json`); every limitation is stated.

## One-liner

> "We built an exception-investigation layer that turns conflicting shipment
> records into an evidence-backed case, a recommended action, a human decision,
> and an audit trail — without replacing your TMS, ERP, or AP system."

## The problem (30 seconds)

When shipment records disagree — PO says 800 kg, BOL/POD say 815 kg, invoice
says 840 kg — a human must locate the records, compare fields, decide which
facts are trustworthy, estimate exposure, choose an action, and keep evidence.
That middle of the freight-audit workflow is manual, slow, and error-prone.
The industry's existing tools (freight audit / invoice matching) catch some
mismatches; **the investigation step is still human.**

Supporting evidence (public): bol.com delivery terms on quantity deviations and
dispute evidence; SPS Commerce code-22 "goods billed not shipped"; SAP's
invoice-reconciliation exception handling. (Details: project dossier.)

## What we built (60 seconds, with live demo)

One command, any machine:

```bash
docker compose up -d --build     # → http://localhost:8000
```

Then in the UI: **⚡ Load demo case C02** and walk:

1. **Conflict** — four documents, four values (800 / 815 / 815 / 840 kg).
2. **Detection** — deterministic engine (no AI for facts): variance +25 kg
   (3.07%) vs delivered, exposure **$312.50** (25 kg × unit price, computed).
3. **Evidence** — every value traceable to its source document line.
4. **Investigation** — plain-language case + plausible causes (each tagged as
   hypothesis) + recommended action. AI layer is evidence-constrained and
   schema-validated; if it fails, the deterministic result stays — the system
   never invents.
5. **Decision + audit** — human approves; every step is in the audit trail.

## Measured results (what we can defend)

| Metric | Value | Basis |
| --- | --- | --- |
| Synthetic evaluation cases | 14 (with machine-readable ground truth) | `data/ground_truth/` |
| Detection accuracy (type-set exact) | **14/14** | `docs/evaluation-results-2026-09-21.json` |
| Precision / recall / F1 | **1.0 / 1.0 / 1.0** | same report |
| End-to-end latency per case (local) | **median 35 ms** | same report |
| Automated tests | **55 passing** (unit + integration + failure paths) | `pytest` |

Honest limitations: synthetic data (labeled as such), controlled document
layouts, local pipeline — no real enterprise data yet. That is precisely what
a controlled pilot measures.

## How it fits (no rip-and-replace)

It sits **alongside** your TMS/ERP/AP. Input today: documents (PO/BOL/POD/
invoice). Input later: the same data via your systems' exports or APIs — the
domain model doesn't change (architecture: `docs/architecture.svg`).

## Pilot proposal (4–6 weeks, recommendation-only)

1. One business unit, one carrier/flow or controlled document set.
2. Baseline first: time 10–20 historical exceptions the way your team does it now.
3. We run the system in **recommendation-only** mode on your (sanitized or
   synthetic-first) cases. Humans keep every decision.
4. We compare: detection precision/recall, correct-resolution rate,
   median time-to-decision, human override rate, evidence completeness.
5. Review false positives/negatives together; only then discuss deeper
   integration. No ROI percentage is promised before step 4 produces numbers.

## The ask

> "Is this workflow recognizable in your operation — and where does our model
> differ from reality? If yes, would you be open to a small pilot with
> non-sensitive or historical data?"

## Slide outline (5 slides)

1. **The contradiction** — 800 / 815 / 815 / 840 kg. "Four records, one
   shipment. They should agree. They don't."
2. **The hidden cost** — what the human investigation actually involves (the
   9-step workflow); where existing tools stop.
3. **The product, live** — demo flow (conflict → evidence → explanation →
   recommendation → decision → audit).
4. **The evidence** — 14/14 measured cases, 55 tests, traceability, safe
   failure; limitations stated on the same slide (credibility).
5. **The pilot** — 4–6 weeks, recommendation-only, one unit, baseline first,
   measured exit. The ask.

## Where to find prospects (validation targets)

Search LinkedIn / company sites for these titles at mid-size companies
(100–5,000 staff, with in-house logistics or AP teams):

- "freight audit" / "freight billing" manager
- "invoice reconciliation" / "AP supervisor" (at manufacturers or 3PLs)
- "logistics operations head" / "supply chain analyst" — automotive,
  FMCG, pharma (Kanpur/NCR/UP corridor first, then national)
- 3PL / TCS operators who already run TMS+ERP and still reconcile manually

Lead with the validation message (this file, "The ask"), not a product demo.
Send 2–3 per day, expect 10–20% reply rate; the goal is a 20-minute
conversation, not a sale.

## Say / don't say

- Say: "evidence-backed investigation layer", "measured on 14 controlled
  cases", "recommendation-only, humans decide".
- Don't say: "no one has solved this" (Navix/Orca/Shipmore/Linehaul do
  adjacent work), "saves X%" (unmeasured), "production-ready" (pilot-grade),
  "AI reads your documents" (the deterministic engine does the facts; AI
  interprets).

## Demo environment options (pitch day)

- **Any laptop with Docker** — `docker compose up -d --build`, 2 min, fully
  offline-capable (deterministic engine).
- **Free AI, zero cost:** `ollama pull llama3.2` (local model, no account, no
  key) + `LEI_LLM_PROVIDER=ollama` — the investigation screen shows a real
  model-generated, schema-validated summary, entirely on the demo machine.
- **Paid AI (if ever desired):** `LEI_LLM_PROVIDER=anthropic` (or `openai`) +
  key + model via environment — same adapter, no code change.
- **No AI at all:** the deterministic investigation is shown and stated as
  such — the demo still makes the full point (facts, evidence, audit).
- **AWS flavor (if a counterpart is AWS-aligned):** the same code runs on
  S3/DynamoDB/Textract/Bedrock/Lambda behind the identical interfaces
  (documented in the repo, `docs/AWS-SETUP.md`).
