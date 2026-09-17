import { useEffect, useRef, useState } from "react";
import { api, DocumentRec, DocumentType, EvidenceRec, ShipmentSummary } from "../api";

const DOC_TYPES: DocumentType[] = ["PO", "BOL", "POD", "INVOICE"];

export default function ShipmentScreen() {
  const [externalRef, setExternalRef] = useState("SHI-2026-0002");
  const [poId, setPoId] = useState("PO-2026-0002");
  const [shipment, setShipment] = useState<ShipmentSummary | null>(null);
  const [docs, setDocs] = useState<DocumentRec[]>([]);
  const [evidence, setEvidence] = useState<EvidenceRec[]>([]);
  const [docType, setDocType] = useState<DocumentType>("PO");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function refresh(id: string) {
    const r = await api.shipment(id);
    setDocs(r.documents);
    setEvidence(r.evidence);
  }

  async function createShipment() {
    const r = await api.shipments({
      external_reference: externalRef,
      purchase_order_id: poId,
    });
    setShipment(r.shipment);
    await refresh(r.shipment.shipment_id);
  }

  async function upload() {
    if (!shipment || !fileRef.current?.files?.[0]) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.uploadDocument(shipment.shipment_id, fileRef.current.files[0], docType);
      setMsg(
        r.duplicate
          ? "Duplicate upload — same document already registered (idempotent skip)."
          : `Extracted ${r.extraction.fields_extracted} fields (${r.extraction.status}).`,
      );
      await refresh(shipment.shipment_id);
      if (fileRef.current) fileRef.current.value = "";
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function runInvestigation() {
    if (!shipment) return;
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.investigate(shipment.shipment_id);
      setMsg(`Investigation complete: ${r.exceptions_created.length} exception(s) created.`);
      await refresh(shipment.shipment_id);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function seedDemo() {
    setBusy(true);
    setMsg(null);
    try {
      const r = await api.seedDemo("C02");
      const s = await api.shipment(r.shipment_id);
      setShipment(s.shipment);
      setExternalRef(s.shipment.external_reference);
      if (s.shipment.purchase_order_id) setPoId(s.shipment.purchase_order_id);
      setDocs(s.documents);
      setEvidence(s.evidence);
      setMsg(
        r.already_seeded
          ? "Demo case already loaded — showing it."
          : `Demo case C02 loaded through the real pipeline: ${r.exceptions_created.length} exception(s) detected.`,
      );
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    // convenience: pre-seed with the canonical demo case if a shipment id was
    // passed via query (used by the demo flow)
    const id = new URLSearchParams(location.search).get("shipment");
    if (id) {
      api
        .shipment(id)
        .then((r) => setShipment(r.shipment))
        .then(() => refresh(id))
        .catch((e) => setMsg(String(e)));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <section className="space-y-6">
      <h2 className="text-xl font-semibold">Shipment / Evidence view</h2>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">1 · Create shipment</h3>
          <label className="block text-xs text-slate-400">
            External reference
            <input
              value={externalRef}
              onChange={(e) => setExternalRef(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm"
            />
          </label>
          <label className="mt-2 block text-xs text-slate-400">
            Purchase order
            <input
              value={poId}
              onChange={(e) => setPoId(e.target.value)}
              className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm"
            />
          </label>
          <button
            onClick={createShipment}
            disabled={busy}
            className="mt-3 w-full rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
          >
            Create
          </button>
        </div>

        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">
            2 · Upload documents{shipment ? ` for ${shipment.shipment_id}` : " (create shipment first)"}
          </h3>
          <div className="flex items-center gap-2">
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value as DocumentType)}
              className="rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm"
            >
              {DOC_TYPES.map((t) => (
                <option key={t}>{t}</option>
              ))}
            </select>
            <input ref={fileRef} type="file" accept=".pdf,.txt,.md" className="min-w-0 flex-1 text-xs" />
          </div>
          <button
            onClick={upload}
            disabled={!shipment || busy}
            className="mt-3 w-full rounded bg-sky-600 px-3 py-1.5 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
          >
            Upload + extract
          </button>
        </div>

        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">3 · Investigate</h3>
          <p className="text-xs text-slate-400">
            Runs deterministic checks across all uploaded documents. No AI is used for detection.
          </p>
          <button
            onClick={runInvestigation}
            disabled={!shipment || busy}
            className="mt-3 w-full rounded bg-purple-600 px-3 py-1.5 text-sm font-medium hover:bg-purple-500 disabled:opacity-50"
          >
            Run investigation
          </button>
        </div>
      </div>

      {msg && <p className="rounded bg-slate-800 p-3 text-sm text-slate-200">{msg}</p>}

      <div className="rounded-lg border border-dashed border-emerald-700/60 p-3">
        <p className="text-xs text-slate-400">
          Demo (repeatable, no manual steps): loads the canonical case — PO 800 kg / BOL 815 kg /
          POD 815 kg / Invoice 840 kg — through the real upload → extract → investigate pipeline.
        </p>
        <button
          onClick={seedDemo}
          disabled={busy}
          className="mt-2 rounded bg-emerald-700 px-4 py-1.5 text-sm font-medium hover:bg-emerald-600 disabled:opacity-50"
        >
          ⚡ Load demo case C02
        </button>
      </div>

      {docs.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Documents & extraction status</h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="py-1 pr-4">Type</th>
                <th className="py-1 pr-4">File</th>
                <th className="py-1 pr-4">Extraction</th>
                <th className="py-1 pr-4">Uploaded</th>
              </tr>
            </thead>
            <tbody>
              {docs.map((d) => (
                <tr key={d.document_id} className="border-t border-slate-800">
                  <td className="py-1.5 pr-4 font-mono text-xs">{d.document_type}</td>
                  <td className="py-1.5 pr-4 text-xs">{d.original_filename}</td>
                  <td className="py-1.5 pr-4">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        d.extraction_status === "SUCCEEDED"
                          ? "bg-emerald-800 text-emerald-100"
                          : "bg-amber-800 text-amber-100"
                      }`}
                    >
                      {d.extraction_status}
                    </span>
                  </td>
                  <td className="py-1.5 pr-4 text-xs text-slate-400">
                    {new Date(d.uploaded_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {evidence.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-semibold text-slate-300">
            Normalized evidence (traceable to source line)
          </h3>
          <table className="w-full text-left text-sm">
            <thead className="text-xs uppercase text-slate-400">
              <tr>
                <th className="py-1 pr-4">Doc</th>
                <th className="py-1 pr-4">Field</th>
                <th className="py-1 pr-4">Normalized</th>
                <th className="py-1 pr-4">Raw</th>
                <th className="py-1 pr-4">Source location</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((e) => (
                <tr key={e.evidence_id} className="border-t border-slate-800">
                  <td className="py-1 pr-4 font-mono text-xs">{e.document_id.slice(0, 12)}…</td>
                  <td className="py-1 pr-4">{e.field_name}</td>
                  <td className="py-1 pr-4 font-mono">{e.normalized_value}{e.unit ? ` ${e.unit}` : ""}</td>
                  <td className="py-1 pr-4 text-slate-400">{e.raw_value}</td>
                  <td className="py-1 pr-4 text-xs text-slate-400">{e.location ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
