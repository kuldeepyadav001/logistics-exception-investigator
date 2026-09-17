"""Deterministic cross-document checks (Blueprint §22, Steps 3–5).

Phase 3 exit criterion (Dossier Blueprint §28): the system can correctly
identify known synthetic anomalies WITHOUT an LLM. This module is pure
deterministic logic — normalization, matching, variance, threshold checks.

Severity is a simple, explainable, configurable rule table (§22 Step 5).

Quantity semantics (documented, tested):
- PO>BOL with BOL==POD  → PARTIAL_SHIPMENT (possible legitimate partial delivery)
- BOL>PO, or unexplained PO≠BOL → QUANTITY_MISMATCH
- BOL≠POD              → QUANTITY_MISMATCH (delivered quantity itself disputed)
- INVOICE≠BOL/POD      → QUANTITY_MISMATCH (billed vs delivered)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from datetime import timedelta
from typing import Optional

from domain.models import (
    Document,
    DocumentType,
    Exception,
    ExceptionStatus,
    ExceptionType,
    EvidenceField,
    DeterministicFinding,
    Shipment,
    Severity,
    new_id,
)
from .normalize import normalize_identifier, normalize_number
from .variance import compute_variance

_QTY_FIELD = "quantity_kg"


@dataclass
class ReconciliationConfig:
    """Simple, explainable, configurable thresholds (Blueprint §22 Step 5)."""

    required_document_types: tuple[DocumentType, ...] = (
        DocumentType.PO,
        DocumentType.BOL,
        DocumentType.POD,
        DocumentType.INVOICE,
    )
    quantity_tolerance_kg: float = 0.0
    amount_tolerance: float = 0.01
    critical_exposure: float = 1000.0
    high_variance_pct: float = 10.0
    medium_variance_pct: float = 1.0
    timeline_grace_days: int = 0


@dataclass
class ShipmentContext:
    shipment: Shipment
    documents: list[Document]
    evidence: dict[str, dict[str, EvidenceField]]  # document_id -> field_name -> EvidenceField
    config: ReconciliationConfig = field(default_factory=ReconciliationConfig)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _label(doc: Document) -> str:
    return f"{doc.document_type.value}:{doc.document_id}"


def _docs_of_type(ctx: ShipmentContext, t: DocumentType) -> list[Document]:
    return [d for d in ctx.documents if d.document_type == t]


def _raw_field(ctx: ShipmentContext, doc: Document, name: str) -> Optional[EvidenceField]:
    return ctx.evidence.get(doc.document_id, {}).get(name)


def _qty(
    ctx: ShipmentContext, doc: Document
) -> tuple[Optional[float], Optional[EvidenceField]]:
    ev = _raw_field(ctx, doc, _QTY_FIELD)
    if ev is None:
        return None, None
    num = normalize_number(ev.normalized_value)
    return num, ev


def _num_field(
    ctx: ShipmentContext, doc: Document, name: str
) -> tuple[Optional[float], Optional[EvidenceField]]:
    ev = _raw_field(ctx, doc, name)
    if ev is None:
        return None, None
    num = normalize_number(ev.normalized_value)
    return num, ev


def _date_field(ctx: ShipmentContext, doc: Document, name: str) -> Optional[str]:
    ev = _raw_field(ctx, doc, name)
    return ev.normalized_value if ev else None


def _id_field(ctx: ShipmentContext, doc: Document, name: str) -> Optional[str]:
    ev = _raw_field(ctx, doc, name)
    return normalize_identifier(ev.normalized_value) if ev else None


def _make_finding(
    check_id: str,
    description: str,
    ref_source: str,
    obs_source: str,
    ref_val: Optional[str],
    obs_val: Optional[str],
    ref_num: Optional[float],
    obs_num: Optional[float],
    metadata: Optional[dict] = None,
) -> DeterministicFinding:
    abs_var, pct = (
        compute_variance(obs_num, ref_num)
        if ref_num is not None and obs_num is not None
        else (None, None)
    )
    return DeterministicFinding(
        check_id=check_id,
        description=description,
        reference_source=ref_source,
        observed_source=obs_source,
        reference_value=ref_val,
        observed_value=obs_val,
        absolute_variance=abs_var,
        percentage_variance=pct,
        metadata=metadata or {},
    )


def _unit_price(ctx: ShipmentContext) -> tuple[Optional[float], Optional[str]]:
    """Unit price (per kg) from the PO document, when present."""
    for po in _docs_of_type(ctx, DocumentType.PO):
        num, ev = _num_field(ctx, po, "unit_price")
        if num is not None:
            return num, (ev.unit if ev else None)
    return None, None


# ---------------------------------------------------------------------------
# check results: (exception_type, findings, affected_fields, exposure, currency)
# ---------------------------------------------------------------------------


def _check_quantity(ctx: ShipmentContext):
    tol = ctx.config.quantity_tolerance_kg
    po = _docs_of_type(ctx, DocumentType.PO)
    bol = _docs_of_type(ctx, DocumentType.BOL)
    pod = _docs_of_type(ctx, DocumentType.POD)
    inv = _docs_of_type(ctx, DocumentType.INVOICE)

    p_num, _ = _qty(ctx, po[0]) if po else (None, None)
    b_num, b_ev = _qty(ctx, bol[0]) if bol else (None, None)
    d_num, d_ev = _qty(ctx, pod[0]) if pod else (None, None)

    findings: list[DeterministicFinding] = []
    delivered_consistent = (
        b_num is not None and d_num is not None and abs(b_num - d_num) <= tol
    )

    # (a) PO vs BOL — partial delivery only when BOL==POD confirms it
    if p_num is not None and b_num is not None and abs(b_num - p_num) > tol:
        if delivered_consistent and b_num < p_num:
            findings.append(
                _make_finding(
                    "QTY_PARTIAL_DELIVERY",
                    "Delivered quantity (BOL/POD) is below ordered quantity (PO)",
                    _label(po[0]),
                    _label(pod[0]),
                    None,
                    d_ev.normalized_value if d_ev else None,
                    p_num,
                    b_num,
                    metadata={
                        "note": "May be a legitimate partial delivery — verify with carrier"
                    },
                )
            )
        else:
            findings.append(
                _make_finding(
                    "QTY_PO_VS_BOL",
                    "PO quantity differs from BOL quantity",
                    _label(po[0]),
                    _label(bol[0]),
                    None,
                    b_ev.normalized_value if b_ev else None,
                    p_num,
                    b_num,
                )
            )

    # (b) BOL vs POD — delivered quantity itself disputed
    if b_num is not None and d_num is not None and abs(b_num - d_num) > tol:
        findings.append(
            _make_finding(
                "QTY_BOL_VS_POD",
                "BOL and POD disagree on delivered quantity",
                _label(bol[0]),
                _label(pod[0]),
                b_ev.normalized_value if b_ev else None,
                d_ev.normalized_value if d_ev else None,
                b_num,
                d_num,
            )
        )

    # (c) INVOICE vs delivered (BOL and POD individually) — canonical demo case
    exposure: Optional[float] = None
    unit_price, currency = _unit_price(ctx)
    for inv_doc in inv:
        i_num, i_ev = _qty(ctx, inv_doc)
        if i_num is None or i_ev is None:
            continue
        worst = 0.0
        sources: list[tuple[Document, float, Optional[EvidenceField]]] = []
        if bol and b_num is not None:
            sources.append((bol[0], b_num, b_ev))
        if pod and d_num is not None:
            sources.append((pod[0], d_num, d_ev))
        for src_doc, src_num, src_ev in sources:
            if abs(i_num - src_num) > tol:
                findings.append(
                    _make_finding(
                        "QTY_DELIVERED_VS_INVOICE",
                        f"Invoice quantity differs from {src_doc.document_type.value} delivered quantity",
                        _label(src_doc),
                        _label(inv_doc),
                        src_ev.normalized_value if src_ev else None,
                        i_ev.normalized_value,
                        src_num,
                        i_num,
                    )
                )
                worst = max(worst, abs(i_num - src_num))
        if worst > 0 and unit_price is not None:
            exposure = (exposure or 0.0) + worst * unit_price

    if not findings:
        return None
    ex_type = (
        ExceptionType.PARTIAL_SHIPMENT
        if all(f.check_id == "QTY_PARTIAL_DELIVERY" for f in findings)
        else ExceptionType.QUANTITY_MISMATCH
    )
    return ex_type, findings, ["quantity"], exposure, currency


def _check_amount(ctx: ShipmentContext, qty_delivered_conflict: bool):
    findings: list[DeterministicFinding] = []
    exposure: Optional[float] = None
    tol = ctx.config.amount_tolerance
    unit_price, currency = _unit_price(ctx)
    if unit_price is None:
        return None
    for inv_doc in _docs_of_type(ctx, DocumentType.INVOICE):
        i_num, _ = _qty(ctx, inv_doc)
        a_num, a_ev = _num_field(ctx, inv_doc, "amount")
        if a_num is None:
            continue
        # (a) invoice internal consistency: amount vs unit_price × billed qty
        if i_num is not None:
            expected_internal = unit_price * i_num
            if abs(a_num - expected_internal) > tol:
                f = _make_finding(
                    "AMT_INVOICE_INTERNAL",
                    "Invoice amount inconsistent with unit price × billed quantity",
                    f"computed: unit_price x qty({_label(inv_doc)})",
                    f"amount:{_label(inv_doc)}",
                    f"{expected_internal:.2f}",
                    a_ev.normalized_value if a_ev else None,
                    expected_internal,
                    a_num,
                )
                findings.append(f)
                exposure = max(exposure or 0.0, abs(f.absolute_variance or 0.0))
        # (b) expected from verified delivered qty — only when quantities agree
        if not qty_delivered_conflict:
            for t in (DocumentType.BOL, DocumentType.POD):
                for d_src in _docs_of_type(ctx, t):
                    n_src, _ = _qty(ctx, d_src)
                    if n_src is None:
                        continue
                    expected = unit_price * n_src
                    if abs(a_num - expected) > tol:
                        f = _make_finding(
                            "AMT_EXPECTED_VS_INVOICE",
                            f"Invoice amount inconsistent with unit price x {t.value} delivered quantity",
                            f"computed: unit_price x qty({_label(d_src)})",
                            f"amount:{_label(inv_doc)}",
                            f"{expected:.2f}",
                            a_ev.normalized_value if a_ev else None,
                            expected,
                            a_num,
                        )
                        findings.append(f)
                        exposure = max(exposure or 0.0, abs(f.absolute_variance or 0.0))
                        break
                else:
                    continue
                break
    if not findings:
        return None
    return ExceptionType.AMOUNT_MISMATCH, findings, ["amount"], exposure, currency


def _check_duplicate_invoices(ctx: ShipmentContext):
    groups: dict[tuple, list[Document]] = {}
    for d in _docs_of_type(ctx, DocumentType.INVOICE):
        num, _ = _num_field(ctx, d, "amount")
        ino = _id_field(ctx, d, "invoice_number")
        if ino is None or num is None:
            continue
        groups.setdefault((ino, num), []).append(d)
    findings = [
        DeterministicFinding(
            check_id="DUP_INVOICE",
            description=f"Duplicate invoice: {len(docs)} documents share invoice number and amount",
            reference_source=_label(docs[0]),
            observed_source=", ".join(_label(d) for d in docs[1:]),
            reference_value=f"invoice_number={ino}, amount={num}",
            observed_value=f"invoice_number={ino}, amount={num}",
        )
        for (ino, num), docs in groups.items()
        if len(docs) >= 2
    ]
    if findings:
        return (
            ExceptionType.DUPLICATE_INVOICE,
            findings,
            ["invoice_number", "amount"],
            None,
            None,
        )
    return None


def _check_identifiers(ctx: ShipmentContext):
    findings: list[DeterministicFinding] = []
    po = _docs_of_type(ctx, DocumentType.PO)
    expected_po = _id_field(ctx, po[0], "po_number") if po else None
    if expected_po is None:
        expected_po = normalize_identifier(ctx.shipment.purchase_order_id)

    for t in (DocumentType.BOL, DocumentType.INVOICE, DocumentType.POD):
        for d in _docs_of_type(ctx, t):
            doc_po = _id_field(ctx, d, "po_number")
            if expected_po and doc_po and doc_po != expected_po:
                findings.append(
                    _make_finding(
                        "ID_PO_MISMATCH",
                        f"{t.value} references a different purchase order than the PO document",
                        f"po_number:{_label(po[0]) if po else 'shipment'}",
                        f"po_number:{_label(d)}",
                        expected_po,
                        doc_po,
                        None,
                        None,
                    )
                )

    refs: list[tuple[Document, str]] = []
    for d in ctx.documents:
        r = _id_field(ctx, d, "shipment_reference")
        if r:
            refs.append((d, r))
    for i in range(len(refs)):
        for j in range(i + 1, len(refs)):
            (d1, r1), (d2, r2) = refs[i], refs[j]
            if r1 != r2:
                findings.append(
                    _make_finding(
                        "ID_SHIPMENT_REF_MISMATCH",
                        "Documents disagree on shipment reference",
                        f"shipment_reference:{_label(d1)}",
                        f"shipment_reference:{_label(d2)}",
                        r1,
                        r2,
                        None,
                        None,
                    )
                )
    if findings:
        return (
            ExceptionType.IDENTIFIER_MISMATCH,
            findings,
            ["po_number", "shipment_reference"],
            None,
            None,
        )
    return None


def _check_completeness(ctx: ShipmentContext):
    present = {d.document_type for d in ctx.documents}
    missing = [t for t in ctx.config.required_document_types if t not in present]
    if not missing:
        return None
    findings = [
        DeterministicFinding(
            check_id="EVIDENCE_MISSING",
            description=f"Required document not present: {t.value}",
            reference_source=f"required:{t.value}",
            observed_source="shipment document set",
        )
        for t in missing
    ]
    return (
        ExceptionType.EVIDENCE_MISSING,
        findings,
        [t.value for t in missing],
        None,
        None,
    )


def _shift(iso_date: str, days: int) -> str:
    return (_date.fromisoformat(iso_date) + timedelta(days=days)).isoformat()


def _check_timeline(ctx: ShipmentContext):
    findings: list[DeterministicFinding] = []
    grace = ctx.config.timeline_grace_days
    ship = None
    for d in _docs_of_type(ctx, DocumentType.BOL):
        ship = _date_field(ctx, d, "ship_date")
        if ship:
            break
    delivery = None
    for d in _docs_of_type(ctx, DocumentType.POD):
        delivery = _date_field(ctx, d, "delivery_date")
        if delivery:
            break
    for inv in _docs_of_type(ctx, DocumentType.INVOICE):
        inv_date = _date_field(ctx, inv, "invoice_date")
        if inv_date is None:
            continue
        if ship and inv_date < _shift(ship, -grace):
            findings.append(
                _make_finding(
                    "TIME_INVOICE_BEFORE_SHIP",
                    "Invoice date precedes ship date",
                    "ship_date:BOL",
                    f"invoice_date:{_label(inv)}",
                    ship,
                    inv_date,
                    None,
                    None,
                )
            )
        if delivery and inv_date < _shift(delivery, -grace):
            findings.append(
                _make_finding(
                    "TIME_INVOICE_BEFORE_DELIVERY",
                    "Invoice date precedes delivery date",
                    "delivery_date:POD",
                    f"invoice_date:{_label(inv)}",
                    delivery,
                    inv_date,
                    None,
                    None,
                )
            )
    if findings:
        return (
            ExceptionType.TIMELINE_INCONSISTENCY,
            findings,
            ["invoice_date", "ship_date"],
            None,
            None,
        )
    return None


# ---------------------------------------------------------------------------
# severity (simple, explainable, configurable — §22 Step 5)
# ---------------------------------------------------------------------------


def _classify(
    ex_type: ExceptionType,
    findings: list[DeterministicFinding],
    exposure: Optional[float],
    ctx: ShipmentContext,
) -> Severity:
    max_pct = max(
        (abs(f.percentage_variance) for f in findings if f.percentage_variance is not None),
        default=None,
    )
    if ex_type == ExceptionType.DUPLICATE_INVOICE:
        return Severity.HIGH
    if ex_type == ExceptionType.EVIDENCE_MISSING:
        return Severity.HIGH
    if exposure is not None and exposure >= ctx.config.critical_exposure:
        return Severity.CRITICAL
    if ex_type == ExceptionType.PARTIAL_SHIPMENT:
        # capped: a shortfall may be an authorized partial delivery —
        # the reviewer decides, so the engine does not over-alarm
        return Severity.MEDIUM
    sev = Severity.LOW
    if max_pct is not None and max_pct >= ctx.config.high_variance_pct:
        sev = Severity.HIGH
    elif max_pct is not None and max_pct >= ctx.config.medium_variance_pct:
        sev = Severity.MEDIUM
    overbilling = any(
        f.absolute_variance is not None
        and f.absolute_variance > 0
        and f.check_id
        in ("QTY_DELIVERED_VS_INVOICE", "AMT_EXPECTED_VS_INVOICE", "AMT_INVOICE_INTERNAL")
        for f in findings
    )
    if ex_type == ExceptionType.QUANTITY_MISMATCH and overbilling:
        sev = Severity.HIGH  # billed above verified delivered quantity
    if ex_type == ExceptionType.AMOUNT_MISMATCH and exposure is not None:
        sev = max(sev, Severity.MEDIUM)
    if ex_type == ExceptionType.PARTIAL_SHIPMENT and sev == Severity.LOW:
        sev = Severity.MEDIUM
    return sev


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------


def run_deterministic_checks(ctx: ShipmentContext) -> list[Exception]:
    """Run all deterministic checks; merge same-type findings into one exception."""
    qty_result = _check_quantity(ctx)
    qty_delivered_conflict = bool(
        qty_result
        and any(f.check_id == "QTY_DELIVERED_VS_INVOICE" for f in qty_result[1])
    )
    results = [
        qty_result,
        _check_amount(ctx, qty_delivered_conflict),
        _check_duplicate_invoices(ctx),
        _check_identifiers(ctx),
        _check_completeness(ctx),
        _check_timeline(ctx),
    ]

    buckets: dict[ExceptionType, dict] = {}
    for result in results:
        if result is None:
            continue
        ex_type, findings, affected, exposure, currency = result
        b = buckets.setdefault(
            ex_type, {"findings": [], "affected": [], "exposure": None, "currency": None}
        )
        b["findings"].extend(findings)
        for a in affected:
            if a not in b["affected"]:
                b["affected"].append(a)
        if exposure is not None:
            b["exposure"] = (b["exposure"] or 0.0) + exposure
            b["currency"] = currency

    return [
        Exception(
            exception_id=new_id("exc"),
            shipment_id=ctx.shipment.shipment_id,
            exception_type=ex_type,
            severity=_classify(ex_type, b["findings"], b["exposure"], ctx),
            status=ExceptionStatus.OPEN,
            deterministic_findings=b["findings"],
            affected_fields=b["affected"],
            estimated_exposure=b["exposure"],
            exposure_currency=b["currency"],
        )
        for ex_type, b in buckets.items()
    ]
