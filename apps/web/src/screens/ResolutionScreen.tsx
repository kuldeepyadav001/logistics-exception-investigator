import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, ShipmentCase } from "../api";
import { severityBadge, statusBadge } from "../App";

export default function ResolutionScreen() {
  const { id } = useParams();
  const [caseData, setCaseData] = useState<ShipmentCase | null>(null);
  const [note, setNote] = useState("");
  const [reviewer, setReviewer] = useState("analyst-01");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [audit, setAudit] = useState<{
    action: string;
    actor_type: string;
    actor_id?: string | null;
    before_ref?: string | null;
    after_ref?: string | null;
    timestamp: string;
  }[]>([]);

  async function load() {
    if (!id) return;
    const [c, a] = await Promise.all([api.exceptionCase(id), api.audit(id)]);
    setCaseData(c);
    setAudit(a.audit_events);
  }

  useEffect(() => {
    load().catch((e) => setMsg(String(e)));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function decide(decision: "APPROVE" | "REJECT" | "EDIT_AND_APPROVE") {
    if (!id) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.decide(id, decision, reviewer, note || undefined);
      await load();
      setMsg("Decision recorded and audited.");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!caseData) return <p className="text-slate-400">Loading…</p>;
  const ex = caseData.exception;
  const inv = caseData.investigation;
  const terminal = ex.status === "RESOLVED" || ex.status === "REJECTED";

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Resolution / Audit — {ex.exception_type}</h2>
        <div className="flex gap-2">
          {severityBadge(ex.severity)}
          {statusBadge(ex.status)}
        </div>
      </div>

      {msg && <p className="rounded bg-slate-800 p-3 text-sm">{msg}</p>}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Human decision</h3>
          {inv?.recommended_action && (
            <p className="mb-3 rounded bg-emerald-900/30 p-2 text-sm text-emerald-100">
              {inv.recommended_action}
            </p>
          )}
          {terminal ? (
            <div>
              <p className="text-sm text-slate-300">
                Status: <b>{ex.status}</b>
              </p>
              {caseData.decisions.map((d) => (
                <div key={d.decision_id} className="mt-2 rounded bg-slate-900 p-2 text-xs">
                  <p>
                    <b>{d.decision}</b> by {d.reviewer_id} — {new Date(d.created_at).toLocaleString()}
                  </p>
                  {d.reviewer_note && <p className="mt-1 text-slate-400">{d.reviewer_note}</p>}
                  {d.final_action && <p className="mt-1 text-slate-400">Final action: {d.final_action}</p>}
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-3">
              <label className="block text-xs text-slate-400">
                Reviewer ID
                <input
                  value={reviewer}
                  onChange={(e) => setReviewer(e.target.value)}
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm"
                />
              </label>
              <label className="block text-xs text-slate-400">
                Reviewer note
                <textarea
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  rows={3}
                  placeholder="e.g. Carrier confirmed 815 kg delivered; requesting credit note for 25 kg."
                  className="mt-1 w-full rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm"
                />
              </label>
              <div className="flex gap-2">
                <button
                  onClick={() => decide("APPROVE")}
                  disabled={busy}
                  className="flex-1 rounded bg-emerald-600 px-3 py-2 text-sm font-medium hover:bg-emerald-500 disabled:opacity-50"
                >
                  Approve
                </button>
                <button
                  onClick={() => decide("EDIT_AND_APPROVE")}
                  disabled={busy}
                  className="flex-1 rounded bg-sky-600 px-3 py-2 text-sm font-medium hover:bg-sky-500 disabled:opacity-50"
                >
                  Edit & approve
                </button>
                <button
                  onClick={() => decide("REJECT")}
                  disabled={busy}
                  className="flex-1 rounded bg-rose-700 px-3 py-2 text-sm font-medium hover:bg-rose-600 disabled:opacity-50"
                >
                  Reject
                </button>
              </div>
              <p className="text-xs text-slate-500">
                Decisions are only allowed from OPEN / INVESTIGATING / PENDING_REVIEW. Every
                decision is written to the audit trail.
              </p>
            </div>
          )}
        </div>

        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Audit trail</h3>
          <ol className="space-y-2">
            {audit.map((a, i) => (
              <li key={i} className="rounded bg-slate-900 p-2 text-xs">
                <p>
                  <span className="font-mono text-emerald-400">{a.action}</span>{" "}
                  <span className="text-slate-400">
                    ({a.actor_type}
                    {a.actor_id ? ` ${a.actor_id}` : ""})
                  </span>
                </p>
                {(a.before_ref || a.after_ref) && (
                  <p className="text-slate-400">
                    {a.before_ref ?? "…"} → {a.after_ref ?? "…"}
                  </p>
                )}
                <p className="text-slate-500">{new Date(a.timestamp).toLocaleString()}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
