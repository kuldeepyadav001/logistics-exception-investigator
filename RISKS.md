# RISKS

| # | Risk | Likelihood | Impact | Mitigation | Owner |
| --- | --- | --- | --- | --- | --- |
| 1 | AWS account not ready by Day 3 | Medium | High (AWS must be genuine in demo) | Local-first design keeps 100% of build momentum; AWS work concentrated in one deployment phase; account creation can happen in parallel today | User |
| 2 | Textract output differs from local parser expectations | Medium | Medium | Controlled PDF layout is chosen for machine readability; Textract adapter will be validated against the same ground-truth suite before the demo | Agent |
| 3 | Bedrock model unavailable / limits under event credits | Low | Medium | Investigation layer is schema-validated; if a model is unavailable, deterministic investigation (already live) is the safe fallback — stated, not faked | Agent + User |
| 4 | Demo depends on live AWS failures during recording | Medium | High | Seeded demo data + resilient path; retry only idempotent ops (§27); re-run demo end-to-end before recording | Agent |
| 5 | Time overrun → feature sprawl | Medium | High | Blueprint §29 cut rule: if Day 3 ends without reliable E2E, stop features, stabilize core | Agent |
| 6 | Unsupported claims creep into write-up/video | Low | Critical (disqualification-adjacent) | Banned-claims list (dossier §26) + evidence tagging; every metric in the submission must be a MEASURED RESULT from our harness | Agent |
| 7 | LLM hallucination in investigation | Medium | High | Evidence-constrained context, structured schema validation, hypotheses tagged, `requires_human_review=true` always | Agent |
| 8 | Secrets leak into repo/logs | Low | High | `.env` gitignored; credentials never in code/docs/commits; only env vars | Agent |
| 9 | Repo history mismatch with event dates | Low | Critical | ADR-007: history starts 2026-09-17; no pre-event code ported | Agent |
| 10 | Synthetic data looks unrealistic to judges | Low | Medium | Realistic document families with controlled ground truth (Blueprint §26); explicitly labeled synthetic (honesty) | Agent |
