# Write-up DRAFT (finalize after AWS deployment, Day 3–4)

> Status: DRAFT. Per event rules, the final write-up covers *the problem, the
> build, and where AWS fits*. Every number below must be a MEASURED RESULT at
> submission time. Banned-claims list (dossier §26) applies — no "no one has
> solved this", no invented percentages.

## The problem

When shipment records disagree — purchase order says 800 kg, bill of lading
and proof of delivery say 815 kg, the invoice says 840 kg — someone has to
manually locate the records, compare fields, work out which facts are
trustworthy, estimate the exposure, decide an action, and keep the evidence.
That investigation is the expensive, error-prone middle of the freight-audit
workflow. (Workflow evidence: bol.com delivery terms, SPS Commerce code-22,
SAP invoice-reconciliation guidance — see the project dossier.)

## What we built

**Logistics Exception Investigator** — not a document reader. An
exception-investigation layer that takes a shipment's documents, detects
contradictions with **deterministic rules**, and prepares an
**evidence-backed case** for a human to decide:

```
PO 800 kg + BOL 815 kg + POD 815 kg + Invoice 840 kg
        ↓ deterministic engine (no AI for facts)
conflict detected · variance +25 kg (3.07%) · exposure $312.50
        ↓ evidence-grounded investigation (structured output, schema-validated)
plain-language case + plausible causes (tagged as hypotheses) + recommended action
        ↓ human decision (approve / edit / reject)
resolution recorded · full audit trail
```

Design rules enforced in code: facts are computed, not generated; the AI never
invents evidence and never acts; every conclusion is traceable to a source
document line; the system says "insufficient evidence" instead of guessing.

## Where AWS fits (finalize with real service names/region after Day 3 deploy)

- **S3** — stores the uploaded source documents.
- **Textract** — real document field extraction (the demo shows extraction on real Textract output).
- **Lambda + API Gateway** — runs the API and the processing pipeline serverlessly.
- **DynamoDB** — shipments, evidence, exceptions, investigations, decisions, audit events.
- **Bedrock** — the investigation layer: receives normalized evidence + deterministic findings, returns schema-validated structured output.
- **Amplify Hosting** — the web UI.
- **CloudWatch Logs** — observability (shown in the demo).

No logo-pasting: each service appears in the demo because it does real work in the pipeline.

## Measured results (fill final numbers from `docs/evaluation-results-*.json` after AWS run)

- Synthetic evaluation suite: 11 controlled cases with machine-readable ground truth.
- Local pipeline (Day 1): **11/11 cases fully correct; detection precision 1.0, recall 1.0, F1 1.0**; per-case end-to-end median latency 52 ms (local adapters).
- AWS pipeline (Day 3–4, to be filled): same suite re-run on deployed services — Textract extraction accuracy, end-to-end latency, cost per case.
- Human baseline (Day 3–4, to be filled): time-to-identify and time-to-resolve on 3 cases, human vs system+reviewer.
- We do not claim business savings; we report what we measured.

## Limitations (honest, keep in final version)

- Synthetic data (clearly labeled); no real enterprise shipment data.
- Local parser and Textract are validated on controlled document layouts; messy real-world scans need a follow-up extraction study.
- No authentication in the hackathon MVP (single-operator demo).
- Investigation AI summary runs on Bedrock [model] with evidence-constrained prompting; deterministic fallback keeps the pipeline safe if the model is unavailable.

## AI tools disclosure (required by event rules)

Built with: [AI coding assistant name(s)] + Amazon Bedrock (Claude [model]) as the in-product investigation model. AI assistance did not replace testing, review, or authorship responsibility.
