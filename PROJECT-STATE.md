# PROJECT-STATE

_Last updated: 2026-09-17 (Day 1 of First Commit, ~18:30 IST)_

**Current state:** `BUILDING` — Phase 1–3 ✅, Phase 4 local ✅, Phase 5 (API + UI) ✅, Phase 6 partial ✅ (metrics measured locally), Phase 7 blocked on AWS (user: **Sep 18**).

## Completed (with evidence)

- **Repo initialized** 2026-09-17 (history = event dates, per rules).
- **Canonical domain model** (Blueprint §21): 7 entities + enums.
- **Infrastructure adapters** (ADR-001): local S3/DynamoDB semantics.
- **HTTP API**: 8 contract endpoints + `/health` + **`POST /demo/seed`** (reproducible demo via the REAL pipeline; idempotent per case) + correlation IDs + uniform errors.
- **Extraction** (local controlled parser, traceable fields) + **Reconciliation engine** (7 types, no LLM) + **Investigation** (evidence-constrained, rule-table local / Bedrock later) + **Decision state machine + audit**.
- **Frontend**: 4 screens (Blueprint §25) incl. one-click **demo seed button**; strict TS production build passing.
- **Synthetic dataset**: 11 cases + ground truth.
- **Failure-path tests** (P1): corrupt PDF → FAILED (never invented), unparseable values → warning (no guess), ambiguous C10 → both values preserved + human review, terminal state → 409, unsupported type → 409.
- **Demo assets**: architecture SVG (`docs/architecture.svg`), write-up draft, 3-min demo script, human-baseline experiment sheet.

## MEASURED RESULTS (2026-09-17, local)

- **11/11 cases fully correct · precision 1.0 · recall 1.0 · F1 1.0**
- Latency per case: **median 52 ms** (min 41 / max 105) — local adapters
- **45/45 tests passing**; report: `docs/evaluation-results-2026-09-17.json`

## Waiting on (human)

1. **GitHub repo URL** — repo created + deploy key added (user confirmed). Agent needs the exact clone URL (`git@github.com:OWNER/logistics-exception-investigator.git`) to push.
2. **AWS** — user creates account + IAM user on **Sep 18** (guide: `docs/AWS-SETUP.md`). Region: ap-south-1.

## Blocked

- Phase 7 (AWS deployment, Textract/Bedrock live, AWS re-evaluation, demo recording) — **Sep 18**, by design.

## Assumptions

PDF-first (ADR-005), exact-match defaults (ADR-006), no auth in MVP (ADR-004), sync processing (ADR-008).

## Next actions (ordered)

1. **Push repo to GitHub** (need clone URL from user — 1 min once provided).
2. Sep 18: AWS adapters (S3/DynamoDB/Textract/Bedrock) + deploy (Lambda/API GW/Amplify) + re-run evaluation on AWS → new MEASURED RESULT section.
3. Sep 18–19: human baseline experiment (`docs/baseline-experiment.md`), Textract accuracy study on the 11 cases, cost/latency on AWS.
4. Sep 19: demo recording per `docs/demo-script.md`; finalize `docs/writeup-draft.md`; submission (repo + video + write-up, early submit per rules).

## Resume note (agent protocol)

If the sandbox is rebuilt: source is fully in git. Re-provision with:
```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd apps/web && npm ci
```
Then `pytest -q` must show 45 passed before continuing. Environment rebuilds have happened and been verified (this is the tested resume path).
