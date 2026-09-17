"""Canonical domain model (Dossier Blueprint §21).

Design rule (Blueprint §21): raw document evidence is never overwritten by
AI-generated conclusions. Conclusions reference evidence; they do not become
evidence themselves.

Storage mapping: each entity maps 1:1 to a DynamoDB table at deploy time
(ADR-001); locally the same entities are persisted via AppRepository.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DocumentType(str, Enum):
    PO = "PO"
    BOL = "BOL"
    POD = "POD"
    INVOICE = "INVOICE"
    OTHER = "OTHER"


class ExtractionStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ExceptionType(str, Enum):
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"
    AMOUNT_MISMATCH = "AMOUNT_MISMATCH"
    DUPLICATE_INVOICE = "DUPLICATE_INVOICE"
    IDENTIFIER_MISMATCH = "IDENTIFIER_MISMATCH"
    PARTIAL_SHIPMENT = "PARTIAL_SHIPMENT"
    TIMELINE_INCONSISTENCY = "TIMELINE_INCONSISTENCY"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"


class ExceptionStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    PENDING_REVIEW = "PENDING_REVIEW"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class DecisionValue(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT_AND_APPROVE = "EDIT_AND_APPROVE"


class ActorType(str, Enum):
    USER = "USER"
    SYSTEM = "SYSTEM"
    AI = "AI"


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class Shipment(BaseModel):
    shipment_id: str
    external_reference: str
    purchase_order_id: Optional[str] = None
    carrier_id: Optional[str] = None
    vendor_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    expected_delivery_date: Optional[str] = None  # ISO yyyy-mm-dd
    status: str = "ACTIVE"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Document(BaseModel):
    document_id: str
    shipment_id: str
    document_type: DocumentType
    s3_key: str  # storage key (local path today, S3 object key at deploy)
    original_filename: str
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    uploaded_at: datetime = Field(default_factory=utcnow)
    checksum: Optional[str] = None


class EvidenceField(BaseModel):
    evidence_id: str
    document_id: str
    field_name: str
    normalized_value: str
    raw_value: str
    unit: Optional[str] = None
    location: Optional[str] = None  # page/line reference in source document
    extraction_confidence: float = 1.0
    created_at: datetime = Field(default_factory=utcnow)


class DeterministicFinding(BaseModel):
    """One deterministic reconciliation finding (Blueprint §22, Step 4).

    A variance is never reported without the compared records being named
    explicitly (reference_source / observed_source).
    """

    check_id: str
    description: str
    reference_source: str
    observed_source: str
    reference_value: Optional[str] = None
    observed_value: Optional[str] = None
    absolute_variance: Optional[float] = None
    percentage_variance: Optional[float] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Exception(BaseModel):  # noqa: A001 - canonical name per Blueprint §21
    exception_id: str
    shipment_id: str
    exception_type: ExceptionType
    severity: Severity
    status: ExceptionStatus = ExceptionStatus.OPEN
    deterministic_findings: list[DeterministicFinding] = Field(default_factory=list)
    affected_fields: list[str] = Field(default_factory=list)
    estimated_exposure: Optional[float] = None
    exposure_currency: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class Investigation(BaseModel):
    investigation_id: str
    exception_id: str
    evidence_snapshot: list[EvidenceField] = Field(default_factory=list)
    deterministic_findings: list[DeterministicFinding] = Field(default_factory=list)
    ai_summary: Optional[str] = None
    plausible_causes: list[str] = Field(default_factory=list)
    recommended_action: Optional[str] = None
    uncertainty: list[str] = Field(default_factory=list)
    model_metadata: dict[str, Any] = Field(default_factory=dict)
    requires_human_review: bool = True
    created_at: datetime = Field(default_factory=utcnow)


class Decision(BaseModel):
    decision_id: str
    exception_id: str
    reviewer_id: str
    decision: DecisionValue
    reviewer_note: Optional[str] = None
    final_action: Optional[str] = None
    created_at: datetime = Field(default_factory=utcnow)


class AuditEvent(BaseModel):
    audit_event_id: str
    entity_type: str
    entity_id: str
    actor_type: ActorType
    actor_id: Optional[str] = None
    action: str
    before_ref: Optional[str] = None
    after_ref: Optional[str] = None
    timestamp: datetime = Field(default_factory=utcnow)
