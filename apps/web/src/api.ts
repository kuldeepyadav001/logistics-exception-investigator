// API client for the 8 contract endpoints (docs/api.md). Relative /api URL
// → proxied to FastAPI in dev, to API Gateway at deploy.

export type DocumentType = "PO" | "BOL" | "POD" | "INVOICE" | "OTHER";

export interface ShipmentSummary {
  shipment_id: string;
  external_reference: string;
  purchase_order_id?: string | null;
  carrier_id?: string | null;
  vendor_id?: string | null;
  status: string;
  created_at: string;
}

export interface DocumentRec {
  document_id: string;
  document_type: DocumentType;
  original_filename: string;
  extraction_status: string;
  checksum?: string | null;
  uploaded_at: string;
}

export interface EvidenceRec {
  evidence_id: string;
  document_id: string;
  field_name: string;
  normalized_value: string;
  raw_value: string;
  unit?: string | null;
  location?: string | null;
  extraction_confidence: number;
}

export interface Finding {
  check_id: string;
  description: string;
  reference_source: string;
  observed_source: string;
  reference_value?: string | null;
  observed_value?: string | null;
  absolute_variance?: number | null;
  percentage_variance?: number | null;
}

export interface ExceptionRec {
  exception_id: string;
  shipment_id: string;
  exception_type: string;
  severity: "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
  status: string;
  deterministic_findings: Finding[];
  affected_fields: string[];
  estimated_exposure?: number | null;
  exposure_currency?: string | null;
  created_at: string;
}

export interface InvestigationRec {
  investigation_id: string;
  exception_id: string;
  ai_summary?: string | null;
  plausible_causes: string[];
  recommended_action?: string | null;
  uncertainty: string[];
  model_metadata: Record<string, unknown>;
  requires_human_review: boolean;
  evidence_snapshot: EvidenceRec[];
  deterministic_findings: Finding[];
}

export interface ShipmentCase {
  exception: ExceptionRec;
  investigation: InvestigationRec | null;
  evidence: EvidenceRec[];
  documents: DocumentRec[];
  decisions: {
    decision_id: string;
    decision: string;
    reviewer_id: string;
    reviewer_note?: string | null;
    final_action?: string | null;
    created_at: string;
  }[];
}

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, init);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.error?.message ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  shipments: (params: {
    external_reference: string;
    purchase_order_id?: string;
    carrier_id?: string;
    vendor_id?: string;
    origin?: string;
    destination?: string;
  }) => http<{ shipment: ShipmentSummary }>("/shipments", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(params),
  }),
  uploadDocument: (shipmentId: string, file: File, docType: DocumentType) => {
    const form = new FormData();
    form.append("file", file);
    form.append("document_type", docType);
    return http<{ document: DocumentRec; duplicate: boolean; extraction: { status: string; fields_extracted: number; warnings: string[] } }>(
      `/shipments/${shipmentId}/documents`,
      { method: "POST", body: form },
    );
  },
  shipment: (id: string) =>
    http<{ shipment: ShipmentSummary; documents: DocumentRec[]; evidence: EvidenceRec[]; exceptions: ExceptionRec[] }>(
      `/shipments/${id}`,
    ),
  investigate: (shipmentId: string) =>
    http<{ exceptions_created: string[]; exceptions: ExceptionRec[] }>(
      `/shipments/${shipmentId}/investigate`,
      { method: "POST" },
    ),
  exceptions: (shipmentId?: string) =>
    http<{ exceptions: ExceptionRec[] }>(
      `/exceptions${shipmentId ? `?shipment_id=${shipmentId}` : ""}`,
    ),
  exceptionCase: (id: string) => http<ShipmentCase>(`/exceptions/${id}`),
  decide: (id: string, decision: string, reviewerId: string, note?: string) =>
    http<{ decision: { decision_id: string }; exception: ExceptionRec }>(
      `/exceptions/${id}/decision`,
      {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ decision, reviewer_id: reviewerId, reviewer_note: note }),
      },
    ),
  audit: (id: string) =>
    http<{
      audit_events: {
        action: string;
        actor_type: string;
        actor_id?: string | null;
        before_ref?: string | null;
        after_ref?: string | null;
        timestamp: string;
      }[];
    }>(`/exceptions/${id}/audit`),
};
