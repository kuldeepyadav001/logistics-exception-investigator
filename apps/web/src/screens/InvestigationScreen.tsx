import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, ExceptionRec, Finding, ShipmentCase } from "../api";
import { severityBadge, statusBadge } from "../App";

/**
 * The hero screen (Blueprint §25 Screen 3): the reviewer must understand the
 * case without reading four documents manually.
 */
export default function InvestigationScreen() {
  const { id } = useParams();
  const [list, setList] = useState<ExceptionRec[]>([]);
  const [caseData, setCaseData] = useState<ShipmentCase | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (id) {
      api.exceptionCase(id).then(setCaseData).catch((e) => setErr(String(e)));
      return;
    }
    api.exceptions().then((r) => {
      setList(r.exceptions);
      if (r.exceptions[0]) api.exceptionCase(r.exceptions[0].exception_id).then(setCaseData).catch(() => {});
    }).catch((e) => setErr(String(e)));
  }, [id]);

  if (err) return <p className="rounded bg-rose-900/40 p-3 text-rose-200">{err}</p>;
  if (!caseData) {
    if (list.length === 0)
      return (
        <p className="rounded border border-dashed border-slate-700 p-6 text-sm text-slate-400">
          No exceptions to investigate yet.
        </p>
      );
    return (
      <div className="space-y-2">
        <h2 className="text-xl font-semibold">Investigations</h2>
        {list.map((e) => (
          <Link
            key={e.exception_id}
            to={`/case/${e.exception_id}`}
            className="block rounded border border-slate-800 p-3 text-sm hover:bg-slate-900"
          >
            {e.exception_type} {severityBadge(e.severity)} {statusBadge(e.status)} — {e.shipment_id}
          </Link>
        ))}
      </div>
    );
  }

  const ex = caseData.exception;
  const inv = caseData.investigation;

  return (
    <section className="space-y-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold">Investigation — {ex.exception_type}</h2>
        <div className="flex items-center gap-2">
          {severityBadge(ex.severity)}
          {statusBadge(ex.status)}
          <Link
            to={`/resolution/${ex.exception_id}`}
            className="rounded bg-emerald-600 px-3 py-1.5 text-sm font-medium hover:bg-emerald-500"
          >
            Review & decide →
          </Link>
        </div>
      </div>

      {/* What conflicts — values by source */}
      <div className="rounded-lg border border-slate-800 p-4">
        <h3 className="mb-3 text-sm font-semibold text-slate-300">What conflicts (values by source)</h3>
        <div className="space-y-2">
          {ex.deterministic_findings.map((f, i) => (
            <FindingRow key={i} f={f} />
          ))}
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {/* Deterministic findings */}
        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">Deterministic findings</h3>
          <ul className="space-y-2 text-sm text-slate-300">
            {ex.deterministic_findings.map((f, i) => (
              <li key={i} className="rounded bg-slate-900 p-2 text-xs">
                <span className="font-mono text-emerald-400">{f.check_id}</span> — {f.description}
              </li>
            ))}
          </ul>
          {ex.estimated_exposure != null && (
            <p className="mt-3 rounded bg-amber-900/30 p-2 text-sm text-amber-200">
              Estimated exposure: <b>{ex.exposure_currency} {ex.estimated_exposure.toFixed(2)}</b>{" "}
              <span className="text-xs">(deterministic estimate from unit price × variance)</span>
            </p>
          )}
        </div>

        {/* AI investigation */}
        <div className="rounded-lg border border-slate-800 p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-300">
            AI investigation
            <span className="ml-2 text-xs font-normal text-slate-500">
              provider: {inv ? String(inv.model_metadata?.provider ?? "—") : "—"}
            </span>
          </h3>
          {!inv && <p className="text-sm text-slate-400">No investigation yet.</p>}
          {inv && (
            <div className="space-y-3 text-sm">
              {inv.ai_summary ? (
                <p className="text-slate-200">{inv.ai_summary}</p>
              ) : (
                <p className="rounded bg-slate-900 p-2 text-xs text-slate-400">
                  AI (Bedrock) summary not yet generated — deterministic findings below are
                  authoritative.
                </p>
              )}
              <div>
                <h4 className="mb-1 text-xs uppercase text-slate-400">Plausible causes (hypotheses)</h4>
                <ul className="list-inside list-disc space-y-1 text-xs text-slate-300">
                  {inv.plausible_causes.map((c, i) => (
                    <li key={i}>{c}</li>
                  ))}
                </ul>
              </div>
              {inv.recommended_action && (
                <div className="rounded bg-emerald-900/30 p-2">
                  <h4 className="mb-1 text-xs uppercase text-emerald-300">Recommended action</h4>
                  <p className="text-emerald-100">{inv.recommended_action}</p>
                  <p className="mt-1 text-xs text-emerald-400/70">
                    A recommendation only — it never acts. {inv.requires_human_review && "Human review required."}
                  </p>
                </div>
              )}
              {inv.uncertainty.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs uppercase text-slate-400">Uncertainty / limitations</h4>
                  <ul className="list-inside list-disc space-y-1 text-xs text-slate-400">
                    {inv.uncertainty.map((u, i) => (
                      <li key={i}>{u}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Evidence used */}
      <div className="rounded-lg border border-slate-800 p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-300">
          Evidence used ({caseData.evidence.length} fields, traceable)
        </h3>
        <div className="grid gap-1 md:grid-cols-2">
          {caseData.evidence.map((e) => (
            <div key={e.evidence_id} className="flex justify-between rounded bg-slate-900 px-2 py-1 text-xs">
              <span className="text-slate-400">
                {e.document_id.slice(0, 12)}… · {e.field_name}
              </span>
              <span className="font-mono">
                {e.normalized_value}
                {e.unit ? ` ${e.unit}` : ""} <span className="text-slate-500">({e.location})</span>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function FindingRow({ f }: { f: Finding }) {
  return (
    <div className="rounded bg-slate-900 p-3 text-sm">
      <p className="text-slate-200">{f.description}</p>
      <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
        <div className="rounded border border-slate-700 p-2">
          <p className="text-slate-400">Reference</p>
          <p className="font-mono text-slate-200">{f.reference_source}</p>
          <p className="font-mono text-lg text-emerald-300">
            {f.reference_value ?? "—"}
          </p>
        </div>
        <div className="rounded border border-slate-700 p-2">
          <p className="text-slate-400">Observed</p>
          <p className="font-mono text-slate-200">{f.observed_source}</p>
          <p className="font-mono text-lg text-rose-300">{f.observed_value ?? "—"}</p>
        </div>
      </div>
      {(f.absolute_variance != null || f.percentage_variance != null) && (
        <p className="mt-2 text-xs text-amber-300">
          Variance: {f.absolute_variance ?? "—"}
          {f.percentage_variance != null ? ` (${f.percentage_variance}%)` : ""} —{" "}
          <span className="text-slate-400">observed − reference</span>
        </p>
      )}
    </div>
  );
}
