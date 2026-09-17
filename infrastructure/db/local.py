"""SQLite-backed application repository (DynamoDB stand-in, ADR-001).

One table per domain entity — the same shape the DynamoDB tables will take
at deploy time (Blueprint §20 Storage). Complex sub-models are stored as
JSON columns; entity ids are indexed for the query patterns in §24 API.

A DynamoDB adapter implementing this exact method surface will be added in
the deployment phase; call sites must not import sqlite directly.
"""
from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Optional

from domain.models import (
    AuditEvent,
    Decision,
    Document,
    Exception,
    ExceptionStatus,
    ExceptionType,
    EvidenceField,
    Investigation,
    Shipment,
)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS shipments (id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documents (id TEXT PRIMARY KEY, shipment_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS evidence_fields (id TEXT PRIMARY KEY, document_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exceptions (id TEXT PRIMARY KEY, shipment_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS investigations (id TEXT PRIMARY KEY, exception_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS decisions (id TEXT PRIMARY KEY, exception_id TEXT, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS audit_events (id TEXT PRIMARY KEY, entity_type TEXT, entity_id TEXT, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_documents_ship ON documents(shipment_id);
CREATE INDEX IF NOT EXISTS idx_evidence_doc ON evidence_fields(document_id);
CREATE INDEX IF NOT EXISTS idx_exceptions_ship ON exceptions(shipment_id);
CREATE INDEX IF NOT EXISTS idx_investigations_exc ON investigations(exception_id);
CREATE INDEX IF NOT EXISTS idx_decisions_exc ON decisions(exception_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_events(entity_type, entity_id);
"""


class AppRepository:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        if str(self.db_path.parent) not in ("", "."):
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # -- shipments ---------------------------------------------------------
    def save_shipment(self, s: Shipment) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO shipments (id, data) VALUES (?, ?)",
                (s.shipment_id, s.model_dump_json()),
            )
            self._conn.commit()

    def get_shipment(self, shipment_id: str) -> Optional[Shipment]:
        row = self._conn.execute(
            "SELECT data FROM shipments WHERE id = ?", (shipment_id,)
        ).fetchone()
        return Shipment.model_validate_json(row[0]) if row else None

    def list_shipments(self) -> list[Shipment]:
        rows = self._conn.execute("SELECT data FROM shipments ORDER BY id").fetchall()
        return [Shipment.model_validate_json(r[0]) for r in rows]

    # -- documents ---------------------------------------------------------
    def save_document(self, d: Document) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO documents (id, shipment_id, data) VALUES (?, ?, ?)",
                (d.document_id, d.shipment_id, d.model_dump_json()),
            )
            self._conn.commit()

    def get_document(self, document_id: str) -> Optional[Document]:
        row = self._conn.execute(
            "SELECT data FROM documents WHERE id = ?", (document_id,)
        ).fetchone()
        return Document.model_validate_json(row[0]) if row else None

    def documents_for_shipment(self, shipment_id: str) -> list[Document]:
        rows = self._conn.execute(
            "SELECT data FROM documents WHERE shipment_id = ? ORDER BY rowid",
            (shipment_id,),
        ).fetchall()
        return [Document.model_validate_json(r[0]) for r in rows]

    def find_document_by_checksum(
        self, shipment_id: str, document_type: str, checksum: str
    ) -> Optional[Document]:
        for d in self.documents_for_shipment(shipment_id):
            if d.document_type.value == document_type and d.checksum == checksum:
                return d
        return None

    # -- evidence ----------------------------------------------------------
    def save_evidence(self, e: EvidenceField) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO evidence_fields (id, document_id, data) VALUES (?, ?, ?)",
                (e.evidence_id, e.document_id, e.model_dump_json()),
            )
            self._conn.commit()

    def clear_evidence_for_document(self, document_id: str) -> None:
        with self._lock:
            self._conn.execute(
                "DELETE FROM evidence_fields WHERE document_id = ?", (document_id,)
            )
            self._conn.commit()

    def evidence_for_document(self, document_id: str) -> list[EvidenceField]:
        rows = self._conn.execute(
            "SELECT data FROM evidence_fields WHERE document_id = ? ORDER BY rowid",
            (document_id,),
        ).fetchall()
        return [EvidenceField.model_validate_json(r[0]) for r in rows]

    def evidence_for_shipment(self, shipment_id: str) -> list[EvidenceField]:
        docs = self.documents_for_shipment(shipment_id)
        out: list[EvidenceField] = []
        for d in docs:
            out.extend(self.evidence_for_document(d.document_id))
        return out

    # -- exceptions --------------------------------------------------------
    def save_exception(self, e: Exception) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO exceptions (id, shipment_id, data) VALUES (?, ?, ?)",
                (e.exception_id, e.shipment_id, e.model_dump_json()),
            )
            self._conn.commit()

    def get_exception(self, exception_id: str) -> Optional[Exception]:
        row = self._conn.execute(
            "SELECT data FROM exceptions WHERE id = ?", (exception_id,)
        ).fetchone()
        return Exception.model_validate_json(row[0]) if row else None

    def exceptions_for_shipment(self, shipment_id: str) -> list[Exception]:
        rows = self._conn.execute(
            "SELECT data FROM exceptions WHERE shipment_id = ? ORDER BY rowid",
            (shipment_id,),
        ).fetchall()
        return [Exception.model_validate_json(r[0]) for r in rows]

    def list_exceptions(
        self,
        shipment_id: Optional[str] = None,
        status: Optional[ExceptionStatus] = None,
        exception_type: Optional[ExceptionType] = None,
    ) -> list[Exception]:
        all_ex = self.list_shipments_exceptions()
        out = []
        for e in all_ex:
            if shipment_id and e.shipment_id != shipment_id:
                continue
            if status and e.status != status:
                continue
            if exception_type and e.exception_type != exception_type:
                continue
            out.append(e)
        return out

    def list_shipments_exceptions(self) -> list[Exception]:
        rows = self._conn.execute(
            "SELECT data FROM exceptions ORDER BY rowid"
        ).fetchall()
        return [Exception.model_validate_json(r[0]) for r in rows]

    # -- investigations ----------------------------------------------------
    def save_investigation(self, i: Investigation) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO investigations (id, exception_id, data) VALUES (?, ?, ?)",
                (i.investigation_id, i.exception_id, i.model_dump_json()),
            )
            self._conn.commit()

    def investigations_for_exception(self, exception_id: str) -> list[Investigation]:
        rows = self._conn.execute(
            "SELECT data FROM investigations WHERE exception_id = ? ORDER BY rowid",
            (exception_id,),
        ).fetchall()
        return [Investigation.model_validate_json(r[0]) for r in rows]

    # -- decisions ---------------------------------------------------------
    def save_decision(self, d: Decision) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO decisions (id, exception_id, data) VALUES (?, ?, ?)",
                (d.decision_id, d.exception_id, d.model_dump_json()),
            )
            self._conn.commit()

    def decisions_for_exception(self, exception_id: str) -> list[Decision]:
        rows = self._conn.execute(
            "SELECT data FROM decisions WHERE exception_id = ? ORDER BY rowid",
            (exception_id,),
        ).fetchall()
        return [Decision.model_validate_json(r[0]) for r in rows]

    # -- audit -------------------------------------------------------------
    def add_audit_event(self, e: AuditEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO audit_events (id, entity_type, entity_id, data) VALUES (?, ?, ?, ?)",
                (e.audit_event_id, e.entity_type, e.entity_id, e.model_dump_json()),
            )
            self._conn.commit()

    def audit_events_for(self, entity_type: str, entity_id: str) -> list[AuditEvent]:
        rows = self._conn.execute(
            "SELECT data FROM audit_events WHERE entity_type = ? AND entity_id = ? ORDER BY rowid",
            (entity_type, entity_id),
        ).fetchall()
        return [AuditEvent.model_validate_json(r[0]) for r in rows]

    def close(self) -> None:
        with self._lock:
            self._conn.close()
