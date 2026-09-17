# Demo Script — 3 minutes (dossier §18, operational version)

**Prereqs:** server running (local or AWS-deployed), UI at :5173 (dev) or
Amplify URL, fresh instance or already-seeded C02. Have a browser tab open at
the Shipment/Evidence screen.

**Rule:** if anything stalls >5 s, keep talking and cut ahead — never wait on
the screen.

## 0:00–0:20 — Problem
> "Four records describe the same shipment. They should tell the same story."
Show: nothing technical — just the sentence.

## 0:20–0:45 — Case
Show the numbers (slide or the UI after seed):
> "The purchase order says 800 kilograms. The bill of lading and proof of
> delivery say 815. The invoice says 840. Somebody is billing for 25 kg that
> was never delivered."

## 0:45–1:45 — Product (live)
1. Click **"⚡ Load demo case C02"** (Shipment/Evidence screen) —
   "This runs the real pipeline: documents stored, extracted, normalized."
2. Point at the **Documents table** (4 × SUCCEEDED) and the **normalized
   evidence** (each value shows its source line): "Every number is traceable
   to the document it came from."
3. Open the **Investigation** screen: "The engine — no AI for the facts —
   compares PO vs BOL vs delivered vs invoice."
   - Point at the **conflicting values side by side** (815 vs 840, Δ +25 kg, 3.07%).
   - Point at **exposure $312.50**: "25 kg times the unit price — computed, not guessed."

## 1:45–2:15 — Decision
- Point at **plausible causes** (each tagged hypothesis): "The AI explains the
  case using only the supplied evidence — and tells you what it does *not* know."
- Point at the **recommended action** (hold payment, verify, credit note): "It
  recommends. It never acts."
- Go to **Resolution**: type a reviewer note, click **Approve**: "The human
  decides; the system records it."

## 2:15–2:40 — AWS
- Show the audit trail: "Every step — upload, detection, investigation,
  decision — is in the audit log."
- Cut to: `/health` (or the AWS console): "And this is where it's running:
  S3 stored the documents, Textract extracted them, Lambda ran the pipeline,
  DynamoDB holds the case, Bedrock wrote the investigation, CloudWatch logged
  everything." [If local at recording time: state exactly that and show the AWS
  run separately — never misrepresent the environment.]

## 2:40–3:00 — Impact / future
> "We measured it: 11 controlled cases, 11 detected correctly, zero false
> positives. The same layer connects to your existing TMS/ERP — it doesn't
> replace them."
End on the case screen (conflict → case → decision visible in one frame).

## Cut rules (Blueprint §29)
- If Bedrock isn't wired at record time: show deterministic investigation and
  say "the AI layer is [status]; here's what it will add" — the demo must not
  depend on it.
- If AWS isn't live at record time: record the product flow locally, then
  record a separate 20-second AWS pass once deployed.
