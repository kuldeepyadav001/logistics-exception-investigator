# PROJECT STATE — updated 2026-09-21 (COMPANY/PILOT TRACK)

## Orientation
Hackathon (First Commit, Sep 17–20) closed without submission (laptop lost Sep 19).
Per dossier §2/§41, the project's objective is now **Narrative B: company pilot** —
complete the project to company/industry standard for pitching other companies.
See ADR-011 (pivot) and ADR-012 (pluggable LLM).

## Current position (measured)
- **Tests: 55/55 passing** (unit + integration + failure paths + LLM adapter).
- **Evaluation: 14/14 synthetic cases, precision/recall/F1 = 1.0**, median 35 ms
  (`docs/evaluation-results-2026-09-21.json`, committed). New: C12 unit
  normalization (0.8 t), C13 INR currency handling, C14 multi-exception.
- **AI investigation layer (ADR-012):** `services/investigation/llm.py` —
  pluggable providers (Anthropic / any OpenAI-compatible / none), env-configured,
  strict §23 schema validation, `requires_human_review` forced true,
  deterministic fallback on ANY failure. Wired into the API; `/health` reports
  the active backend. Default = deterministic (works with zero API keys).
- **Docker (single container):** `Dockerfile` + `docker-compose.yml` —
  multi-stage (React build → python:3.12-slim), UI served by the API on ONE
  port (verified: `/` = UI, `/api`/`/health`/`/demo/seed` = JSON, assets 200).
  `LEI_DATA_DIR=/data` volume. Runs anywhere; AWS no longer a dependency.
- **Web UI:** 4 screens + one-click "⚡ Load demo case C02" (idempotent seed).
- **Repo:** public, `github.com/kuldeepyadav001/logistics-exception-investigator`,
  main = origin/main (pushed). Deploy key works (chmod 600 after rebuild).

## Pitch assets (NEW)
- `docs/company-pitch.md` — one-liner, 60-second demo script, measured-results
  table, 4–6-week pilot proposal, 5-slide outline, say/don't-say (banned claims
  per §26), demo-environment options.
- `docs/baseline-experiment.md` — baseline methodology for pilot step 1.
- `docs/writeup-draft.md` — adaptable for any external description.

## Environment recovery (sandbox rebuilds wipe: .venv, node_modules, git identity)
```
cd /home/user/logistics-exception-investigator
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cd apps/web && npm ci --no-audit --no-fund && cd ..
git config user.name "LEI Build Agent" && git config user.email "build@lei.local"
chmod 600 /home/user/.ssh/id_ed25519_lei
# .git/config is snapshot-excluded → restore remote if missing:
git remote get-url origin 2>/dev/null || \
  git remote add origin git@github.com:kuldeepyadav001/logistics-exception-investigator.git
# no ~/.ssh/config after rebuild → push with explicit key:
GIT_SSH_COMMAND='ssh -i /home/user/.ssh/id_ed25519_lei -o IdentitiesOnly=yes' git push origin main
.venv/bin/python -m pytest tests/ -q   # expect 55 passing
```

## Next (company track — see BACKLOG.md)
1. Optional: LLM smoke test with a real key when the user has one (env only).
2. Optional: Docker image build verification in this sandbox (needs Docker).
3. Optional: `apps/web` polish (empty states, loading) — only if time exists.
4. When a laptop/VM is available: one-command demo rehearsal + first outreach
   (drafts in dossier §36 / docs/company-pitch.md).
