"""Pluggable LLM investigation adapter (Blueprint §23 AI Investigation Contract).

Company-track design: the AI layer works with ANY provider via environment
config — no hard AWS dependency. Deterministic engine remains the trusted core;
the LLM only interprets evidence and recommends.

Config (env):
  LEI_LLM_PROVIDER = none | anthropic | openai      (default: none → deterministic only)
  LEI_LLM_API_KEY  = provider API key (NEVER committed)
  LEI_LLM_MODEL    = model id (e.g. claude-3-5-haiku-latest, gpt-4o-mini)
  LEI_LLM_BASE_URL = optional base URL override (any OpenAI-compatible API)

Contract enforcement (§23 rules):
1. model receives only the structured evidence bundle — nothing else
2. output is validated against a strict schema; malformed output is REJECTED
   (rule 8) and the deterministic investigation is used instead
3. requires_human_review is forced true for consequential resolution (rule 7)
4. the model never acts — output is advisory only (rule 5/6)
"""
from __future__ import annotations

import json
import os
import re
from typing import Optional, Protocol

import httpx
from pydantic import BaseModel, Field, field_validator

REQUEST_TIMEOUT_S = 60


class LLMInvestigationOutput(BaseModel):
    summary: str = Field(min_length=1)
    findings: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)
    plausible_causes: list[str] = Field(default_factory=list)
    recommended_action: str = Field(min_length=1)
    reasoning_limitations: list[str] = Field(default_factory=list)
    requires_human_review: bool = True

    @field_validator("requires_human_review")
    @classmethod
    def force_human_review(cls, v: bool) -> bool:
        # MVP rule (Blueprint §23 rule 7): always human review for
        # consequential resolution, regardless of what the model says.
        return True


class LLMProvider(Protocol):
    name: str
    model: str

    def generate(self, system: str, prompt: str) -> str:
        """Return raw model text. Raises on transport/HTTP errors."""
        ...


class OpenAICompatibleProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, system: str, prompt: str) -> str:
        r = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com"):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def generate(self, system: str, prompt: str) -> str:
        r = httpx.post(
            f"{self.base_url}/v1/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
            },
            json={
                "model": self.model,
                "max_tokens": 1500,
                "temperature": 0.1,
                "system": system,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=REQUEST_TIMEOUT_S,
        )
        r.raise_for_status()
        return r.json()["content"][0]["text"]


_SYSTEM_PROMPT = """You are the investigation layer of a shipment exception investigation system.

You receive a STRUCTURED EVIDENCE BUNDLE for one shipment exception:
normalized document evidence (each field cites its source document and line),
and DETERMINISTIC findings (already-computed facts with explicit reference and
observed sources and variances).

HARD RULES:
1. Every factual statement must reference supplied evidence or a deterministic
   calculation. Never invent a document, value, date, carrier, person, or policy.
2. Clearly distinguish FACTS (evidence/deterministic) from PLAUSIBLE CAUSES
   (tag each cause as a hypothesis, not verified).
3. If evidence conflicts or is incomplete, say so explicitly.
4. You never act. You recommend. requires_human_review must be true.
5. If the evidence is insufficient, the summary must say:
   "Insufficient evidence. Human investigation required."
6. Respond with ONLY a JSON object, no prose, matching exactly:
{"summary": string, "findings": [string], "evidence_references": [string],
 "plausible_causes": [string], "recommended_action": string,
 "reasoning_limitations": [string], "requires_human_review": true}"""


def _extract_json(text: str) -> dict:
    """Parse the first JSON object in model output (robust to stray prose)."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


class InvestigationLLM:
    """Builds the §23 input bundle, calls the provider, validates the output."""

    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider

    @property
    def ready(self) -> bool:
        return self.provider is not None

    def run(
        self,
        shipment: dict,
        documents: list[dict],
        normalized_evidence: list[dict],
        deterministic_findings: list[dict],
        business_rules: list[str],
        allowed_actions: list[str],
    ) -> tuple[Optional[LLMInvestigationOutput], dict]:
        """Returns (validated_output_or_None, model_metadata).

        Any transport error, provider error, or schema-invalid output yields
        (None, metadata-with-error) — the caller falls back to the
        deterministic investigation. The error is recorded, never displayed as
        model output.
        """
        meta: dict = {
            "provider": self.provider.name if self.provider else "none",
            "model": self.provider.model if self.provider else None,
        }
        if self.provider is None:
            meta["note"] = "LLM provider not configured; deterministic investigation only."
            return None, meta

        bundle = {
            "shipment": shipment,
            "documents": documents,
            "normalized_evidence": normalized_evidence,
            "deterministic_findings": deterministic_findings,
            "business_rules": business_rules,
            "allowed_actions": allowed_actions,
        }
        prompt = (
            "Investigate this shipment exception using ONLY the evidence bundle below.\n\n"
            + json.dumps(bundle, indent=2, default=str)
        )
        try:
            raw = self.provider.generate(_SYSTEM_PROMPT, prompt)
            data = _extract_json(raw)
            out = LLMInvestigationOutput.model_validate(data)
            meta["status"] = "ok"
            return out, meta
        except Exception as e:  # noqa: BLE001 — reject, record, fall back
            meta["status"] = "rejected"
            meta["error"] = f"{type(e).__name__}: {e}"
            return None, meta


def make_investigation_llm() -> InvestigationLLM:
    """Factory from environment config (ADR-012)."""
    provider_name = os.environ.get("LEI_LLM_PROVIDER", "none").lower()
    api_key = os.environ.get("LEI_LLM_API_KEY", "")
    model = os.environ.get("LEI_LLM_MODEL", "")
    if provider_name == "none" or not api_key:
        return InvestigationLLM(None)
    if provider_name == "anthropic":
        return InvestigationLLM(
            AnthropicProvider(api_key, model or "claude-3-5-haiku-latest")
        )
    if provider_name == "openai":
        return InvestigationLLM(
            OpenAICompatibleProvider(
                api_key,
                model or "gpt-4o-mini",
                base_url=os.environ.get("LEI_LLM_BASE_URL", "https://api.openai.com/v1"),
            )
        )
    return InvestigationLLM(None)
