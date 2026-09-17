# Baseline Experiment (human vs system) — run Day 3, ~20 min

Purpose: a MEASURED comparison so no business claim is unmeasured (dossier §14).
**A faster answer that is wrong is not an improvement.**

## Materials
- One team member who has NOT seen the product.
- Print/PDF packets for 3 cases: **C02** (canonical), **C07** (partial), **C10** (ambiguous) — files in `data/synthetic/<case>/`.
- A stopwatch (phone is fine).
- The score sheet below.

## Procedure
1. Hand over case C02's four documents only. Start the stopwatch.
2. Ask the participant to: (a) tell you **what is wrong**, (b) name the
   **affected fields**, (c) state the **correct resolution action**. Stop the
   clock. Record.
3. Repeat for C07 and C10.
4. Then (separately): open the system, load the same cases, and time
   **reviewer time** = time to read the investigation and make the decision.

## Score sheet

| Case | Human: time to identify | Human: affected fields correct? | Human: resolution correct? | System: detection time (from eval report) | Reviewer: time to decide |
| --- | --- | --- | --- | --- | --- |
| C02 | | | | 52 ms median (local) | |
| C07 | | | | | |
| C10 | | | | | |

Ground truth for scoring is in `data/ground_truth/<case>.json`.

## Record results
Fill the table into `docs/evaluation.md` under "Human baseline (MEASURED)",
with date + participant role. Do NOT put human data (PII) in the repo —
record only durations and correctness.
