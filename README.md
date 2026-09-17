# Logistics Exception Investigator

> **Don't automate the document. Automate the investigation.**

AI-assisted **shipment exception investigation layer**: turns conflicting shipment records (PO / BOL / POD / Invoice) into an evidence-backed case → recommended action → **human decision** → audit trail.

- **Source of truth:** [Master Project Dossier (Notion)](https://app.notion.com/p/Logistics-Exception-Investigator-Master-Project-Dossier-3d77a721f05c813488e1e92ad20881a9) — this repo's docs are derived from it.
- **Event:** AWS Bharat Builds Tour / First Commit, **Sept 17–20, 2026**. Per event rules, this repository's history starts **2026-09-17** (judged work). Pre-event work = research/planning only (see the dossier).
- **AI tools used:** built with an AI coding assistant (disclosed per event rules for the submission write-up).

## Status

| Phase (Blueprint §28) | Status |
| --- | --- |
| 0 — Pre-event prep (dossier, contracts, dataset design) | ✅ complete (dossier + this repo's contracts) |
| 1 — Foundation (repo, API, storage, config, logging) | ✅ complete, tested |
| 2 — Evidence pipeline (upload → extract → normalize) | ✅ local (controlled parser); Textract adapter pending AWS account |
| 3 — Reconciliation engine (deterministic checks, **no LLM**) | ✅ complete — 11/11 ground-truth cases pass |
| 4 — Investigation intelligence | 🟡 deterministic investigation live; **Bedrock adapter pending AWS account** |
| 5 — Human resolution + audit | ✅ API + state machine + audit trail (UI pending) |
| 6 — Evaluation & hardening | 🟡 ground-truth harness live (11/11); baseline experiment + latency/cost pending |
| 7 — Deployment & demo |  pending AWS account + frontend |

**Current state:** `BUILDING` — backend core is working end-to-end locally with real generated PDFs. Blocked items need the AWS account (see `docs/AWS-SETUP.md`).

## Quickstart

```bash
# backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                    # 36 tests
LEI_DATA_DIR=data/runtime .venv/bin/uvicorn services.api.app:app --port 8000
# API at http://localhost:8000 (docs at /docs)

# regenerate the synthetic dataset (idempotent)
.venv/bin/python -m scripts.generate_dataset

# frontend (React + Vite + Tailwind)
cd apps/web && npm install && npm run dev        # http://localhost:5173, proxies /api → :8000
```

### Try the canonical demo case via curl

```bash
SID=$(.venv/bin/python - <<'EOF'
import requests  # or use curl; see docs/api.md for the full flow
EOF
)
```

Full walkthrough with exact commands: `docs/api.md`. The hero case is `data/synthetic/C02` (PO 800 kg / BOL 815 kg / POD 815 kg / Invoice 840 kg).

## Repository layout (Blueprint §32 + ADR-003)

```
domain/                    canonical models (Shipment, Document, EvidenceField,
                           Exception, Investigation, Decision, AuditEvent)
services/
  api/                     HTTP API — the 8 contract endpoints (Blueprint §24)
  extraction/              controlled "LABEL: value" extractor (Textract stand-in)
  reconciliation/          normalize → checks → variance → severity (pure deterministic)
  investigation/           evidence-constrained investigation (Bedrock stand-in)
infrastructure/
  storage/                 DocumentStore (S3 semantics; local FS backend)
  db/                      AppRepository (DynamoDB semantics; SQLite backend)
apps/web/                  React + TypeScript + Vite + Tailwind (4-screen MVP)
data/
  synthetic/               generated document families (labeled SYNTHETIC)
  ground_truth/            machine-readable expected results per case
  runtime/                 local backends (gitignored)
tests/
  unit/ integration/ evaluation/
docs/                      architecture, api, data-model, evaluation, AWS-SETUP
PROJECT-STATE.md           current reality (phase, done, blocked, next)
DECISIONS.md               ADRs
RISKS.md BACKLOG.md NEXT-ACTIONS.md
```

## Core engineering rules (dossier §33, enforced in code)

1. Evidence before explanation — every conclusion references evidence or a deterministic rule.
2. Deterministic facts before AI interpretation — the engine detects without any LLM.
3. Human control before consequential action — every resolution is a human decision.
4. Explicit uncertainty before fabricated confidence — unrecognized input → warning, never a guess.
5. Raw evidence is immutable — AI conclusions reference evidence, never replace it.

## AWS

The system is **local-first by adapter design (ADR-001)**: S3/DynamoDB/Textract/Bedrock are behind interfaces with local backends so the full pipeline runs and tests today. AWS backends are dropped in when the account is ready — setup guide: **`docs/AWS-SETUP.md`**. The demo must show genuine AWS usage (event rule).
