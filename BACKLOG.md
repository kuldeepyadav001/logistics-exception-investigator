# BACKLOG — company/pilot track (replaces hackathon plan, 2026-09-21)

## Done (2026-09-21 pivot day)
- [x] Pivot ADR-011; pluggable-LLM ADR-012
- [x] `services/investigation/llm.py` — provider-agnostic AI investigation
      (Anthropic / OpenAI-compatible / none), §23 contract enforced,
      deterministic fallback on any failure; 8 unit tests with fake provider
- [x] LLM wired into API: ai_summary/plausible_causes/recommended_action/
      uncertainty + model_metadata; `/health` reports active LLM backend
- [x] Docker single-container deployment (multi-stage, UI+API one port,
      volume for data, env passthrough for LLM); static SPA serving verified
- [x] Evaluation deepened to 14 cases: C12 unit normalization, C13 INR
      currency, C14 multi-exception → 14/14, P/R/F1 = 1.0 (report committed)
- [x] `docs/company-pitch.md` — one-pager + 5-slide outline + pilot proposal
      + outreach say/don't-say (banned-claims discipline §26)
- [x] requirements split: requirements.txt (runtime) / requirements-dev.txt
- [x] All pushed to public GitHub

## Deferred / explicit non-goals
- AWS deployment (S3/DynamoDB/Textract/Bedrock adapters) — only if a specific
  counterpart needs it; interfaces already exist (ADR-001 preserved)
- Real-data ingestion, OCR on messy PDFs, auth, multi-tenant, payments
- TMS/ERP/linehaul integrations (out of scope per §3)
