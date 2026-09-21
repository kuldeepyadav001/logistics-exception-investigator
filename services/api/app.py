"""HTTP API — Blueprint §24 API Contract (8 endpoints + health + demo seed).

Local dev:  uvicorn services.api.app:app --port 8000
Deploy:     each endpoint is a thin wrapper suitable for API Gateway +
            Lambda (ADR-002); domain code is backend-agnostic.

Conventions:
- all requests carry an X-Request-ID (generated if absent) — correlation IDs
- errors: {"error": {"code", "message", "request_id"}}
- uploads are idempotent per (shipment, document_type, checksum) — §27
- /demo/seed runs the REAL pipeline (same ingest + investigation code paths)
  on a synthetic case — demo reproducibility without manual DB manipulation
  (Definition of Done, Blueprint §31).
"""
from __future__ import annotations

import hashlib
import logging
import os
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from domain.models import (
    ActorType,
    AuditEvent,
    Decision,
    DecisionValue,
    Document,
    DocumentType,
    Exception,
    ExceptionStatus,
    EvidenceField,
    ExtractionStatus,
    Investigation,
    Shipment,
    new_id,
    utcnow,
)
from infrastructure.db.local import AppRepository
from infrastructure.storage.local import LocalDocumentStore
from services.extraction.local import LocalExtractor
from services.investigation.local import build_investigation
from services.investigation.llm import InvestigationLLM, make_investigation_llm
from services.reconciliation.checks import (
    ReconciliationConfig,
    ShipmentContext,
    run_deterministic_checks,
)

logger = logging.getLogger("lei.api")

_BUSINESS_RULES = [
    "Invoice quantity must not exceed the verified delivered quantity (BOL/POD).",
    "Invoice amount must equal unit price × billed quantity.",
    "Every payment-relevant resolution requires a human decision.",
]
_ALLOWED_ACTIONS = [
    "hold_payment",
    "request_corrected_invoice",
    "request_credit_note",
    "request_missing_document",
    "verify_with_carrier",
    "verify_with_vendor",
]

ALLOWED_CONTENT_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
}


# ---------------------------------------------------------------------------
# request schemas
# ---------------------------------------------------------------------------


class CreateShipmentRequest(BaseModel):
    external_reference: str = Field(min_length=1, max_length=120)
    purchase_order_id: Optional[str] = None
    carrier_id: Optional[str] = None
    vendor_id: Optional[str] = None
    origin: Optional[str] = None
    destination: Optional[str] = None
    expected_delivery_date: Optional[str] = None


class DecisionRequest(BaseModel):
    decision: DecisionValue
    reviewer_id: str = Field(min_length=1, max_length=120)
    reviewer_note: Optional[str] = None
    final_action: Optional[str] = None


# ---------------------------------------------------------------------------
# app factory
# ---------------------------------------------------------------------------


def create_app(
    repo: Optional[AppRepository] = None,
    store: Optional[LocalDocumentStore] = None,
    extractor: Optional[LocalExtractor] = None,
    config: Optional[ReconciliationConfig] = None,
    llm: Optional[InvestigationLLM] = None,
) -> FastAPI:
    data_dir = Path(os.environ.get("LEI_DATA_DIR", "data/runtime"))
    repo = repo or AppRepository(data_dir / "app.sqlite3")
    store = store or LocalDocumentStore(data_dir / "documents")
    extractor = extractor or LocalExtractor()
    config = config or ReconciliationConfig()
    llm = llm or make_investigation_llm()

    app = FastAPI(
        title="Logistics Exception Investigator API",
        version="0.1.0",
        description="Exception-investigation layer for conflicting shipment records.",
    )
    app.state.repo = repo
    app.state.store = store
    app.state.extractor = extractor
    app.state.config = config
    app.state.llm = llm

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # prototype; locked down per deploy environment (ADR-004)
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- correlation IDs + error shape -------------------------------------

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        rid = request.headers.get("x-request-id") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        return response

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        code = exc.headers.get("x-error-code") if exc.headers else None
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code or "ERROR",
                    "message": str(exc.detail),
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    def _not_found(entity: str, entity_id: str) -> HTTPException:
        e = HTTPException(status_code=404, detail=f"{entity} not found: {entity_id}")
        e.headers = {"x-error-code": f"{entity.upper()}_NOT_FOUND"}  # type: ignore[attr-defined]
        return e

    def _conflict(message: str, code: str) -> HTTPException:
        e = HTTPException(status_code=409, detail=message)
        e.headers = {"x-error-code": code}  # type: ignore[attr-defined]
        return e

    def _audit(
        entity_type: str,
        entity_id: str,
        actor_type: ActorType,
        action: str,
        actor_id: Optional[str] = None,
        before: Optional[str] = None,
        after: Optional[str] = None,
    ) -> None:
        repo.add_audit_event(
            AuditEvent(
                audit_event_id=new_id("aud"),
                entity_type=entity_type,
                entity_id=entity_id,
                actor_type=actor_type,
                actor_id=actor_id,
                action=action,
                before_ref=before,
                after_ref=after,
            )
        )

    # -- internal pipeline (shared by upload endpoint AND /demo/seed) -------

    def ingest(
        shipment: Shipment, doc_type: DocumentType, filename: str, data: bytes
    ) -> dict:
        """Store + extract + normalize one document. Idempotent by checksum."""
        checksum = hashlib.sha256(data).hexdigest()
        existing = repo.find_document_by_checksum(shipment.shipment_id, doc_type.value, checksum)
        if existing is not None:
            # §27: duplicate upload → do not reprocess
            return {
                "document": existing,
                "duplicate": True,
                "note": "identical document already registered for this shipment/type; not reprocessed",
            }

        lower = filename.lower()
        ext = ".pdf" if lower.endswith(".pdf") else ".md" if lower.endswith(".md") else ".txt"
        document = Document(
            document_id=new_id("doc"),
            shipment_id=shipment.shipment_id,
            document_type=doc_type,
            s3_key=f"shipments/{shipment.shipment_id}/documents/{new_id('obj')}{ext}",
            original_filename=filename,
            extraction_status=ExtractionStatus.RUNNING,
            checksum=checksum,
        )
        repo.save_document(document)
        store.put(document.s3_key, data)
        _audit("document", document.document_id, ActorType.USER, "document.uploaded")

        result = extractor.extract(data, filename)
        repo.clear_evidence_for_document(document.document_id)
        for f in result.fields:
            repo.save_evidence(
                EvidenceField(
                    evidence_id=new_id("evd"),
                    document_id=document.document_id,
                    field_name=f.field_name,
                    normalized_value=f.normalized_value,
                    raw_value=f.raw_value,
                    unit=f.unit,
                    location=f.location,
                    extraction_confidence=f.confidence,
                )
            )
        status = {
            "SUCCEEDED": ExtractionStatus.SUCCEEDED,
            "PARTIAL": ExtractionStatus.PARTIAL,
            "FAILED": ExtractionStatus.FAILED,
        }[result.status]
        document.extraction_status = status
        repo.save_document(document)
        _audit(
            "document",
            document.document_id,
            ActorType.SYSTEM,
            f"extraction.{result.status.lower()}",
            before="RUNNING",
            after=status.value,
        )
        if result.errors:
            logger.warning("extraction failed for %s: %s", document.document_id, result.errors)
        return {
            "document": document,
            "duplicate": False,
            "extraction": {
                "status": result.status,
                "fields_extracted": len(result.fields),
                "warnings": result.warnings,
                "errors": result.errors,
            },
        }

    def run_investigation(shipment_id: str) -> dict:
        shipment = repo.get_shipment(shipment_id)
        if shipment is None:
            raise _not_found("shipment", shipment_id)
        documents = repo.documents_for_shipment(shipment_id)
        evidence = {
            d.document_id: {
                ef.field_name: ef for ef in repo.evidence_for_document(d.document_id)
            }
            for d in documents
        }
        ctx = ShipmentContext(
            shipment=shipment, documents=documents, evidence=evidence, config=config
        )
        exceptions = run_deterministic_checks(ctx)
        all_evidence = [
            ef for d in documents for ef in repo.evidence_for_document(d.document_id)
        ]

        created: list[Exception] = []
        investigations: list[Investigation] = []
        for ex in exceptions:
            existing = next(
                (
                    e
                    for e in repo.exceptions_for_shipment(shipment_id)
                    if e.exception_type == ex.exception_type
                    and e.status in (ExceptionStatus.OPEN, ExceptionStatus.INVESTIGATING)
                ),
                None,
            )
            if existing is not None:
                existing.deterministic_findings = ex.deterministic_findings
                existing.affected_fields = ex.affected_fields
                existing.estimated_exposure = ex.estimated_exposure
                existing.exposure_currency = ex.exposure_currency
                existing.severity = ex.severity
                existing.updated_at = utcnow()
                repo.save_exception(existing)
                ex = existing
            else:
                repo.save_exception(ex)
                _audit("exception", ex.exception_id, ActorType.SYSTEM, "exception.created")
                created.append(ex)

            if ex.status == ExceptionStatus.OPEN:
                snapshot = [
                    ef
                    for ef in all_evidence
                    if ef.document_id in _document_ids_in_findings(ex)
                ]
                bundle_snapshot = snapshot or all_evidence
                investigation = build_investigation(ex, bundle_snapshot)
                # AI layer (if configured): evidence-constrained, schema-validated.
                # Any failure/invalid output → keep the deterministic version.
                if llm.ready:
                    llm_out, meta = llm.run(
                        shipment=shipment.model_dump(mode="json"),
                        documents=[d.model_dump(mode="json") for d in documents],
                        normalized_evidence=[
                            ef.model_dump(mode="json") for ef in bundle_snapshot
                        ],
                        deterministic_findings=[
                            f.model_dump(mode="json") for f in ex.deterministic_findings
                        ],
                        business_rules=_BUSINESS_RULES,
                        allowed_actions=_ALLOWED_ACTIONS,
                    )
                    if llm_out is not None:
                        investigation.ai_summary = llm_out.summary
                        investigation.plausible_causes = llm_out.plausible_causes
                        investigation.recommended_action = (
                            llm_out.recommended_action
                        )
                        investigation.uncertainty = llm_out.reasoning_limitations
                        investigation.model_metadata = meta
                    else:
                        # rejected output: record why, keep deterministic results
                        investigation.model_metadata = {
                            **investigation.model_metadata,
                            **meta,
                        }
                repo.save_investigation(investigation)
                ex.status = ExceptionStatus.PENDING_REVIEW
                ex.updated_at = utcnow()
                repo.save_exception(ex)
                _audit(
                    "exception",
                    ex.exception_id,
                    ActorType.SYSTEM,
                    "investigation.created",
                    before="OPEN",
                    after="PENDING_REVIEW",
                )
                investigations.append(investigation)

        return {
            "shipment_id": shipment_id,
            "exceptions_created": [e.exception_id for e in created],
            "exceptions": repo.exceptions_for_shipment(shipment_id),
            "investigations": investigations,
        }

    # -- health --------------------------------------------------------------

    @app.get("/health")
    def health() -> dict:
        aws_configured = bool(os.environ.get("AWS_ACCESS_KEY_ID"))
        return {
            "status": "ok",
            "environment": "aws" if aws_configured else "local",
            "backends": {
                "s3": "aws" if aws_configured else "local-filesystem",
                "dynamodb": "aws" if aws_configured else "sqlite",
                "textract": "aws" if aws_configured else "local-controlled-parser",
                "llm_investigation": llm.provider.name if llm.ready else "deterministic-rules",
            },
        }

    # -- demo seed (reproducibility without manual DB manipulation) ----------

    @app.post("/demo/seed", status_code=201)
    def seed_demo(case_id: str = Query("C02", min_length=1, max_length=8)) -> dict:
        """Seed a synthetic case through the REAL pipeline (upload → extract →
        normalize → investigate). Idempotent per case (external reference)."""
        from scripts.generate_dataset import CARRIER, CASES, VENDOR, build_case

        spec = next((c for c in CASES if c.case_id.upper() == case_id.upper()), None)
        if spec is None:
            raise _not_found("demo_case", case_id)
        result = build_case(spec)
        m = result["metadata"]

        existing = next(
            (
                s
                for s in repo.list_shipments()
                if s.external_reference == m["shipment_ref"]
            ),
            None,
        )
        if existing is not None:
            return {
                "case_id": spec.case_id,
                "shipment_id": existing.shipment_id,
                "already_seeded": True,
                "exceptions": [e.exception_id for e in repo.exceptions_for_shipment(existing.shipment_id)],
            }

        shipment = Shipment(
            shipment_id=new_id("sht"),
            external_reference=m["shipment_ref"],
            purchase_order_id=m["po_number"],
            carrier_id=CARRIER,
            vendor_id=VENDOR,
            origin="MUMBAI",
            destination="DELHI",
        )
        repo.save_shipment(shipment)
        _audit("shipment", shipment.shipment_id, ActorType.SYSTEM, "shipment.created")

        ingested: list[dict] = []
        for doc_type_key, data in result["files"].items():
            dt = DocumentType("INVOICE") if doc_type_key == "INVOICE_2" else DocumentType(doc_type_key)
            ingested.append(ingest(shipment, dt, f"{doc_type_key}_{m['shipment_ref']}.pdf", data))

        body = run_investigation(shipment.shipment_id)
        return {
            "case_id": spec.case_id,
            "shipment_id": shipment.shipment_id,
            "already_seeded": False,
            "documents": [i["document"] for i in ingested],
            "extraction": [i["extraction"] for i in ingested],
            **body,
        }

    # -- shipments -----------------------------------------------------------

    @app.post("/shipments", status_code=201)
    def create_shipment(req: CreateShipmentRequest) -> dict:
        shipment = Shipment(shipment_id=new_id("sht"), **req.model_dump())
        repo.save_shipment(shipment)
        _audit("shipment", shipment.shipment_id, ActorType.SYSTEM, "shipment.created")
        logger.info("shipment created %s", shipment.shipment_id)
        return {"shipment": shipment}

    @app.post("/shipments/{shipment_id}/documents", status_code=201)
    async def upload_document(
        shipment_id: str,
        file: UploadFile = File(...),
        document_type: str = Form(...),
    ) -> dict:
        shipment = repo.get_shipment(shipment_id)
        if shipment is None:
            raise _not_found("shipment", shipment_id)
        try:
            doc_type = DocumentType(document_type.upper())
        except ValueError:
            raise _conflict(
                f"invalid document_type '{document_type}'", "INVALID_DOCUMENT_TYPE"
            )

        ext = ALLOWED_CONTENT_TYPES.get(file.content_type or "")
        if ext is None:
            raise _conflict(
                f"unsupported content type '{file.content_type}' "
                f"(allowed: {sorted(ALLOWED_CONTENT_TYPES)})",
                "UNSUPPORTED_CONTENT_TYPE",
            )

        data = await file.read()
        filename = file.filename or f"upload{ext}"
        return ingest(shipment, doc_type, filename, data)

    @app.get("/shipments/{shipment_id}")
    def get_shipment(shipment_id: str) -> dict:
        shipment = repo.get_shipment(shipment_id)
        if shipment is None:
            raise _not_found("shipment", shipment_id)
        return {
            "shipment": shipment,
            "documents": repo.documents_for_shipment(shipment_id),
            "evidence": repo.evidence_for_shipment(shipment_id),
            "exceptions": repo.exceptions_for_shipment(shipment_id),
        }

    @app.post("/shipments/{shipment_id}/investigate")
    def investigate(shipment_id: str) -> dict:
        return run_investigation(shipment_id)

    # -- exceptions ----------------------------------------------------------

    @app.get("/exceptions")
    def list_exceptions(
        shipment_id: Optional[str] = None,
        status: Optional[ExceptionStatus] = None,
        exception_type: Optional[str] = None,
    ) -> dict:
        from domain.models import ExceptionType

        et = None
        if exception_type:
            try:
                et = ExceptionType(exception_type.upper())
            except ValueError:
                raise _conflict(f"invalid exception_type '{exception_type}'", "INVALID_TYPE")
        items = repo.list_exceptions(shipment_id=shipment_id, status=status, exception_type=et)
        return {
            "exceptions": [
                {
                    "exception_id": e.exception_id,
                    "shipment_id": e.shipment_id,
                    "exception_type": e.exception_type.value,
                    "severity": e.severity.value,
                    "status": e.status.value,
                    "estimated_exposure": e.estimated_exposure,
                    "exposure_currency": e.exposure_currency,
                    "created_at": e.created_at,
                }
                for e in items
            ]
        }

    @app.get("/exceptions/{exception_id}")
    def get_exception(exception_id: str) -> dict:
        ex = repo.get_exception(exception_id)
        if ex is None:
            raise _not_found("exception", exception_id)
        investigations = repo.investigations_for_exception(exception_id)
        return {
            "exception": ex,
            "investigation": investigations[-1] if investigations else None,
            "evidence": repo.evidence_for_shipment(ex.shipment_id),
            "documents": repo.documents_for_shipment(ex.shipment_id),
            "decisions": repo.decisions_for_exception(exception_id),
        }

    @app.post("/exceptions/{exception_id}/decision", status_code=201)
    def decide(exception_id: str, req: DecisionRequest) -> dict:
        ex = repo.get_exception(exception_id)
        if ex is None:
            raise _not_found("exception", exception_id)
        allowed = (ExceptionStatus.OPEN, ExceptionStatus.INVESTIGATING, ExceptionStatus.PENDING_REVIEW)
        if ex.status not in allowed:
            raise _conflict(
                f"exception is {ex.status.value}; decisions only allowed from "
                f"{[s.value for s in allowed]}",
                "INVALID_STATE",
            )
        new_status = (
            ExceptionStatus.RESOLVED
            if req.decision in (DecisionValue.APPROVE, DecisionValue.EDIT_AND_APPROVE)
            else ExceptionStatus.REJECTED
        )
        decision = Decision(
            decision_id=new_id("dec"),
            exception_id=exception_id,
            reviewer_id=req.reviewer_id,
            decision=req.decision,
            reviewer_note=req.reviewer_note,
            final_action=req.final_action or (ex.affected_fields and ",".join(ex.affected_fields)),
        )
        repo.save_decision(decision)
        _audit(
            "exception",
            exception_id,
            ActorType.USER,
            "decision.received",
            actor_id=req.reviewer_id,
        )
        ex.status = new_status
        ex.updated_at = utcnow()
        repo.save_exception(ex)
        _audit(
            "exception",
            exception_id,
            ActorType.SYSTEM,
            f"exception.{new_status.value.lower()}",
            before="PENDING_REVIEW",
            after=new_status.value,
        )
        logger.info("decision %s on %s by %s", req.decision.value, exception_id, req.reviewer_id)
        return {"decision": decision, "exception": ex}

    @app.get("/exceptions/{exception_id}/audit")
    def exception_audit(exception_id: str) -> dict:
        ex = repo.get_exception(exception_id)
        if ex is None:
            raise _not_found("exception", exception_id)
        return {
            "exception_id": exception_id,
            "audit_events": repo.audit_events_for("exception", exception_id),
        }

    return app


def _document_ids_in_findings(ex: Exception) -> set[str]:
    """Document ids referenced by an exception's findings (suffix after ':')."""
    ids = set()
    for f in ex.deterministic_findings:
        for src in (f.reference_source, f.observed_source):
            if ":" in src:
                ids.add(src.split(":", 1)[1])
    return ids


app = create_app()

# Static SPA (production build) — single-container deployment (Docker):
# API routes registered above take precedence; everything else serves the UI.
_DIST = Path(__file__).resolve().parents[2] / "apps" / "web" / "dist"
if _DIST.is_dir():
    app.mount("/", StaticFiles(directory=_DIST, html=True), name="ui")
