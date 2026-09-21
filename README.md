# Logistics Exception Investigator

> **Don't automate the document. Automate the investigation.**

An AI-assisted **shipment exception investigation layer**: turns conflicting
shipment records (PO / BOL / POD / Invoice) into an evidence-backed case →
recommended action → **human decision** → audit trail.

It sits **alongside** your TMS/ERP/AP — it does not replace them. Every fact is
computed deterministically and traceable to a source document line; the AI
layer (optional, any provider) only interprets evidence, never invents it;
schema-invalid AI output is rejected; consequential resolution always requires
a human decision.

- **Source of truth:** [Master Project Dossier (Notion)](https://app.notion.com/p/Logistics-Exception-Investigator-Master-Project-Dossier-3d77a721f05c813488e1e92ad20881a9) — repo docs derive from it.
- **Status:** pilot-grade prototype — 55 tests, 14/14 measured evaluation cases
  (P/R/F1 = 1.0), one-command Docker demo. See `docs/company-pitch.md`.
- **AI tools used:** built with an AI coding assistant (disclosed per
  transparency norms); all logic reviewed and test-covered.

## Quick start (Docker — one container, one port, any machine)

```bash
docker compose up -d --build
# → http://localhost:8000  (web UI + API + one-click demo seed)
curl -X POST "localhost:8000/demo/seed?case_id=C02"
```

Then open http://localhost:8000 → **⚡ Load demo case C02** and watch:
conflict (800/815/815/840 kg) → deterministic detection (+25 kg, exposure
$312.50) → evidence lines → investigation → recommended action → human
decision → audit trail.

Optional AI investigation layer (any provider, env-configured, ADR-012):

```bash
# Anthropic:
LEI_LLM_PROVIDER=anthropic LEI_LLM_API_KEY=*** LEI_LLM_MODEL=claude-sonnet-4-20250514 docker compose up -d
# or any OpenAI-compatible endpoint:
LEI_LLM_PROVIDER=openai LEI_LLM_API_KEY=*** LEI_LLM_MODEL=gpt-4o docker compose up -d
```

Without a key, the deterministic rule-table investigation runs — by design the
system works with or without the AI layer.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                                  # 55 tests
LEI_DATA_DIR=data/runtime .venv/bin/python -m uvicorn services.api.app:app --port 8000
# API at http://localhost:8000 (OpenAPI at /docs)

.venv/bin/python -m scripts.generate_dataset                   # regenerate 14-case dataset
.venv/bin/python -m scripts.run_evaluation                     # measured evaluation report
.venv/bin/python -m scripts.baseline_experiment                # baseline timing sheet

cd apps/web && npm ci && npm run dev                           # UI at :5173 (proxies /api)
```

## Repository layout

```
apps/web                  React + Vite + Tailwind — 4 screens (Blueprint §25)
services/api              FastAPI — Blueprint §24 contract + /demo/seed + /health
services/extraction       Controlled local extractor (Textract-shaped contract)
services/reconciliation   Deterministic checks: normalization, matching, variance,
                          duplicates, thresholds (Blueprint §22)
services/investigation    Deterministic investigation + pluggable LLM layer (§23)
infrastructure            Local adapters (SQLite, filesystem) — same interfaces as AWS
domain                    Models + evidence contract (pydantic, validated)
data/synthetic            14 machine-readable ground-truth cases (clearly synthetic)
tests                     unit / integration (incl. failure paths) / evaluation
docs                      architecture, API, data model, evaluation, pitch kit,
                          ADRs (DECISIONS.md), AWS setup (optional path)
scripts                   dataset generation, evaluation runner, baseline experiment
```

## Measured results

| Metric | Value | Source |
| --- | --- | --- |
| Evaluation cases | 14 (ground-truth, synthetic, labeled) | `data/ground_truth/` |
| Detection (type-set exact) | **14/14** | `docs/evaluation-results-2026-09-21.json` |
| Precision / recall / F1 | **1.0 / 1.0 / 1.0** | same |
| End-to-end latency per case | **median 35 ms** (local) | same |
| Automated tests | **55 passing** | `pytest` |

Honest limitations: synthetic, clearly-labeled data; controlled document
layouts; single-tenant; recommendation-only. A controlled pilot on real
operational data is the next validation step (see `docs/company-pitch.md`).

## Optional AWS path

The same code can run on S3 / DynamoDB / Textract / Bedrock / Lambda behind
identical interfaces (ADR-001); setup instructions in `docs/AWS-SETUP.md`.
This is **optional** — the local/Docker deployment is complete and is the
default for demos and pilots (ADR-011).
