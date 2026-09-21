"""Tests for the LLM investigation adapter (Blueprint §23 contract).

Uses fake providers — no network. Verifies the contract, not a specific vendor:
valid output is accepted and enforced; invalid output is rejected and the
deterministic fallback path is taken; requires_human_review is forced true.
"""
from __future__ import annotations

from services.investigation.llm import (
    InvestigationLLM,
    LLMInvestigationOutput,
    _extract_json,
)

BUNDLE = {
    "shipment": {"shipment_id": "s1", "external_reference": "S-1"},
    "documents": [{"document_id": "d1", "document_type": "INVOICE"}],
    "normalized_evidence": [
        {"field_name": "quantity_kg", "normalized_value": "840", "document_id": "d1"}
    ],
    "deterministic_findings": [
        {
            "check_id": "QTY_DELIVERED_VS_INVOICE",
            "description": "Invoice quantity differs from POD delivered quantity",
            "reference_source": "POD:d0",
            "observed_source": "INVOICE:d1",
            "absolute_variance": 25.0,
            "percentage_variance": 3.0675,
        }
    ],
    "business_rules": ["invoice must not exceed delivered quantity"],
    "allowed_actions": ["hold_payment", "request_credit_note"],
}

VALID_OUTPUT = {
    "summary": "Invoice bills 840 kg while POD evidences 815 kg delivered (deterministic finding QTY_DELIVERED_VS_INVOICE, +25 kg / 3.07%).",
    "findings": ["Invoice quantity exceeds delivered quantity by 25 kg."],
    "evidence_references": ["POD:d0", "INVOICE:d1"],
    "plausible_causes": ["Invoice may have been raised on a later, unrecorded addition (hypothesis)."],
    "recommended_action": "Hold payment; verify with carrier; request credit note for 25 kg.",
    "reasoning_limitations": ["No carrier confirmation available in the bundle."],
    "requires_human_review": False,  # model lies — must be forced true
}


class FakeProvider:
    def __init__(self, output: dict | str, name: str = "fake", model: str = "fake-1"):
        self._output = output
        self.name = name
        self.model = model

    def generate(self, system: str, prompt: str) -> str:
        import json as _json

        return self._output if isinstance(self._output, str) else _json.dumps(self._output)


class RaisingProvider:
    name = "raising"
    model = "raising-1"

    def generate(self, system: str, prompt: str) -> str:
        raise RuntimeError("provider exploded")


def test_valid_output_accepted_and_review_forced():
    llm = InvestigationLLM(FakeProvider(VALID_OUTPUT))
    assert llm.ready
    out, meta = llm.run(**BUNDLE)
    assert isinstance(out, LLMInvestigationOutput)
    assert out.requires_human_review is True  # forced, despite model saying False
    assert meta["status"] == "ok"
    assert meta["provider"] == "fake"


def test_invalid_json_rejected_fallback():
    llm = InvestigationLLM(FakeProvider("I think the numbers look a bit off."))
    out, meta = llm.run(**BUNDLE)
    assert out is None
    assert meta["status"] == "rejected"
    assert "error" in meta


def test_schema_invalid_rejected():
    # valid JSON but missing required field
    bad = dict(VALID_OUTPUT)
    del bad["recommended_action"]
    llm = InvestigationLLM(FakeProvider(bad))
    out, meta = llm.run(**BUNDLE)
    assert out is None
    assert meta["status"] == "rejected"


def test_provider_error_rejected_fallback():
    llm = InvestigationLLM(RaisingProvider())
    out, meta = llm.run(**BUNDLE)
    assert out is None
    assert meta["status"] == "rejected"
    assert "exploded" in meta["error"]


def test_json_embedded_in_prose_extracted():
    raw = 'Sure, here is the result:\n```json\n' + __import__("json").dumps(VALID_OUTPUT) + "\n```\nHope that helps!"
    llm = InvestigationLLM(FakeProvider(raw))
    out, meta = llm.run(**BUNDLE)
    assert isinstance(out, LLMInvestigationOutput)
    assert meta["status"] == "ok"


def test_extract_json_handles_plain():
    data = _extract_json('{"a": 1}')
    assert data == {"a": 1}


def test_unconfigured_reports_none():
    llm = InvestigationLLM(None)
    assert not llm.ready
    out, meta = llm.run(**BUNDLE)
    assert out is None
    assert meta["provider"] == "none"
    assert "note" in meta
