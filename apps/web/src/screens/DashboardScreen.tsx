import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, ExceptionRec } from "../api";
import { severityBadge, statusBadge } from "../App";

export default function DashboardScreen() {
  const [rows, setRows] = useState<ExceptionRec[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api
      .exceptions()
      .then((r) => setRows(r.exceptions))
      .catch((e) => setErr(String(e)));
  }, []);

  return (
    <section>
      <h2 className="mb-4 text-xl font-semibold">Open exceptions</h2>
      {err && <p className="mb-3 rounded bg-rose-900/40 p-3 text-sm text-rose-200">{err}</p>}
      {rows.length === 0 && !err && (
        <p className="rounded border border-dashed border-slate-700 p-6 text-sm text-slate-400">
          No exceptions yet. Upload documents on the{" "}
          <Link className="text-emerald-400 underline" to="/shipment">
            Shipment / Evidence
          </Link>{" "}
          screen, then run an investigation.
        </p>
      )}
      {rows.length > 0 && (
        <table className="w-full text-left text-sm">
          <thead className="text-xs uppercase text-slate-400">
            <tr>
              <th className="py-2 pr-4">Type</th>
              <th className="py-2 pr-4">Severity</th>
              <th className="py-2 pr-4">Shipment</th>
              <th className="py-2 pr-4">Exposure</th>
              <th className="py-2 pr-4">Status</th>
              <th className="py-2 pr-4">Age</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.exception_id} className="border-t border-slate-800 hover:bg-slate-900/50">
                <td className="py-2 pr-4 font-mono text-xs">{e.exception_type}</td>
                <td className="py-2 pr-4">{severityBadge(e.severity)}</td>
                <td className="py-2 pr-4">{e.shipment_id}</td>
                <td className="py-2 pr-4">
                  {e.estimated_exposure != null
                    ? `${e.exposure_currency ?? ""} ${e.estimated_exposure.toFixed(2)}`
                    : "—"}
                </td>
                <td className="py-2 pr-4">{statusBadge(e.status)}</td>
                <td className="py-2 pr-4 text-xs text-slate-400">
                  {Math.max(0, Math.round((Date.now() - new Date(e.created_at).getTime()) / 60000))}m
                </td>
                <td className="py-2 text-right">
                  <Link
                    to={`/case/${e.exception_id}`}
                    className="text-emerald-400 hover:underline"
                  >
                    investigate →
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  );
}
