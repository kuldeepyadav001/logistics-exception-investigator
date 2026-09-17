# NEXT-ACTIONS

## For the user (blocking / parallel)
1. **GitHub:** create a **public** repository (suggested name: `logistics-exception-investigator`), then add this deploy key with **write** access:
   `Settings → Deploy keys → Add deploy key`
   ```
   ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINCwkWX0o/erUKskWXGvLzdp+qqFiAsGskxT3nkGB4a+ lei-agent-deploy
   ```
   → agent pushes the full repo.
2. **AWS:** create the account now (takes ~15–30 min incl. phone verification). Follow `docs/AWS-SETUP.md` (ordered steps + exact IAM permissions + what to read). Tell the agent when the IAM user credentials are ready (region recommended: `ap-south-1` Mumbai).

## For the agent (in order)
1. Push repo to GitHub (once key is connected).
2. Frontend: Screen 1 dashboard + Screen 3 investigation hero (Blueprint §25) against local API.
3. Evaluation run: record precision/recall + per-case timing in `docs/evaluation.md`.
4. AWS adapters (S3, DynamoDB, Textract, Bedrock) + deploy (Lambda/API Gateway/Amplify) once account is ready.
5. Re-run full evaluation against the deployed pipeline; capture measured results for the demo.
6. Demo: seed demo data (C02), record 3-minute video per dossier §18 script.
7. Submission: public repo + write-up (problem, build, where AWS fits, AI tools disclosed) + video.
