"""Evidence-constrained investigation (Blueprint §23).

Local deterministic implementation, used until Amazon Bedrock is available
(ADR-001). It honors every rule of the AI contract:

1. every factual finding references supplied evidence or a deterministic
   calculation (findings are carried over verbatim from the engine);
2. plausible causes are explicitly tagged as hypotheses;
3. uncertainty/limitations are stated;
4. nothing is invented — the recommended action comes from an explicit,
   reviewable rule table;
5. the system never acts; it recommends;
6. requires_human_review is always True for consequential resolution.

When Bedrock is wired in, BedrockInvestigator sends exactly the §23 input
contract and validates the model output against the same schema; invalid
model output is rejected, not displayed (§23 rule 8).
"""
from __future__ import annotations

from domain.models import Exception, EvidenceField, Investigation, new_id

_ACTION_RULES = {
    "QUANTITY_MISMATCH": (
        "Hold payment on the affected line item. Verify the delivered quantity "
        "against BOL/POD and carrier records, then request a corrected invoice "
        "or credit note for the difference before releasing payment."
    ),
    "AMOUNT_MISMATCH": (
        "Hold the invoice for review. Recalculate the expected amount from the "
        "verified unit price and delivered quantity, then request a corrected "
        "invoice or credit note for the difference."
    ),
    "DUPLICATE_INVOICE": (
        "Do not pay the duplicate invoice. Confirm payment history, then void or "
        "reject the duplicate copy and confirm with the vendor."
    ),
    "IDENTIFIER_MISMATCH": (
        "Verify the correct purchase order / shipment reference with the vendor "
        "before processing. Hold the invoice until identifiers are confirmed."
    ),
    "PARTIAL_SHIPMENT": (
        "Confirm with the carrier whether a partial delivery was authorized. If "
        "authorized, request a revised invoice matching the delivered quantity; "
        "otherwise escalate for a full shipment claim."
    ),
    "TIMELINE_INCONSISTENCY": (
        "Verify document dates with the carrier and vendor before processing the "
        "invoice. Check for back-dated or pre-delivery billing."
    ),
    "EVIDENCE_MISSING": (
        "Request the missing document(s) from the vendor or carrier. Do not "
        "resolve the case until the evidence set is complete."
    ),
}

_CAUSE_RULES = {
    "QUANTITY_MISMATCH": [
        "Invoice may have been raised on the ordered quantity instead of the delivered quantity (hypothesis, not verified)",
        "An additional load may have been added at dispatch without a revised PO (hypothesis, not verified)",
        "A data-entry error on one of the documents is possible (hypothesis, not verified)",
    ],
    "AMOUNT_MISMATCH": [
        "An incorrect rate may have been applied on the invoice (hypothesis, not verified)",
        "An undocumented surcharge may be included in the total (hypothesis, not verified)",
    ],
    "DUPLICATE_INVOICE": [
        "The vendor may have transmitted the same invoice twice (hypothesis, not verified)",
    ],
    "IDENTIFIER_MISMATCH": [
        "The document may reference an older or superseded PO (hypothesis, not verified)",
        "A data-entry error in the reference field is possible (hypothesis, not verified)",
    ],
    "PARTIAL_SHIPMENT": [
        "The carrier may have delivered only part of the ordered quantity (hypothesis, not verified)",
    ],
    "TIMELINE_INCONSISTENCY": [
        "The invoice may have been dated before physical dispatch (hypothesis, not verified)",
    ],
    "EVIDENCE_MISSING": [
        "The document may not have been transmitted or may be in transit (hypothesis, not verified)",
    ],
}

_STANDARD_UNCERTAINTY = [
    "Analysis is based only on the supplied evidence; no external verification was performed.",
    "Every plausible cause is a hypothesis and must be verified by the reviewer.",
]


def build_investigation(
    exception: Exception, evidence_snapshot: list[EvidenceField]
) -> Investigation:
    return Investigation(
        investigation_id=new_id("inv"),
        exception_id=exception.exception_id,
        evidence_snapshot=evidence_snapshot,
        deterministic_findings=list(exception.deterministic_findings),
        ai_summary=None,  # filled by the Bedrock adapter when available
        plausible_causes=list(_CAUSE_RULES.get(exception.exception_type.value, [])),
        recommended_action=_ACTION_RULES.get(exception.exception_type.value),
        uncertainty=list(_STANDARD_UNCERTAINTY),
        model_metadata={
            "provider": "deterministic-rules",
            "model": None,
            "version": "1.0",
            "note": "Bedrock investigation layer not yet configured (no AWS account). "
            "Deterministic engine findings are authoritative; AI summary pending.",
        },
        requires_human_review=True,
    )
