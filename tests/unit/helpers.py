"""Test helpers: build reconciliation contexts from plain dicts."""
from __future__ import annotations

from domain.models import Document, DocumentType, EvidenceField, Shipment, new_id
from services.reconciliation.checks import ReconciliationConfig, ShipmentContext


def make_doc(shipment_id: str, doc_type: str) -> Document:
    return Document(
        document_id=new_id("doc"),
        shipment_id=shipment_id,
        document_type=DocumentType(doc_type),
        s3_key=f"shipments/{shipment_id}/documents/x",
        original_filename=f"{doc_type}.pdf",
    )


def make_evidence(doc_id: str, fields: dict[str, tuple[str, str | None]]) -> dict[str, EvidenceField]:
    """fields: name -> (normalized_value, unit)"""
    return {
        name: EvidenceField(
            evidence_id=new_id("evd"),
            document_id=doc_id,
            field_name=name,
            normalized_value=norm,
            raw_value=norm,
            unit=unit,
        )
        for name, (norm, unit) in fields.items()
    }


def make_ctx(
    docs: dict[str, dict[str, tuple[str, str | None]]],
    shipment_kwargs: dict | None = None,
    config: ReconciliationConfig | None = None,
) -> ShipmentContext:
    """docs: document_type -> fields dict. e.g. {"PO": {"quantity_kg": ("800", "kg")}, ...}"""
    shipment = Shipment(
        shipment_id=new_id("sht"),
        external_reference="TEST-REF",
        **(shipment_kwargs or {}),
    )
    documents: list[Document] = []
    evidence: dict[str, dict[str, EvidenceField]] = {}
    for doc_type, fields in docs.items():
        d = make_doc(shipment.shipment_id, doc_type)
        documents.append(d)
        evidence[d.document_id] = make_evidence(d.document_id, fields)
    return ShipmentContext(
        shipment=shipment,
        documents=documents,
        evidence=evidence,
        config=config or ReconciliationConfig(),
    )


# canonical synthetic values
UNIT_PRICE = ("12.50", "USD")
CLEAN_QTY = ("800", "kg")
CLEAN_AMT = ("10000.00", "USD")
