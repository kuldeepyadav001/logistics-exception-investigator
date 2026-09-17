import { NavLink, Route, Routes } from "react-router-dom";
import DashboardScreen from "./screens/DashboardScreen";
import ShipmentScreen from "./screens/ShipmentScreen";
import InvestigationScreen from "./screens/InvestigationScreen";
import ResolutionScreen from "./screens/ResolutionScreen";

const nav = [
  { to: "/", label: "1 · Exceptions" },
  { to: "/shipment", label: "2 · Shipment / Evidence" },
  { to: "/case", label: "3 · Investigation" },
  { to: "/resolution", label: "4 · Resolution / Audit" },
];

export default function App() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-800 bg-slate-900/60 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold tracking-tight">
              🚚 Logistics Exception Investigator
            </h1>
            <p className="text-xs text-slate-400">
              Don't automate the document. Automate the investigation.
            </p>
          </div>
          <nav className="flex gap-1">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.to === "/"}
                className={({ isActive }) =>
                  `rounded-md px-3 py-1.5 text-sm ${
                    isActive
                      ? "bg-emerald-600 text-white"
                      : "text-slate-300 hover:bg-slate-800"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-6 py-6">
        <Routes>
          <Route path="/" element={<DashboardScreen />} />
          <Route path="/shipment" element={<ShipmentScreen />} />
          <Route path="/case" element={<InvestigationScreen />} />
          <Route path="/case/:id" element={<InvestigationScreen />} />
          <Route path="/resolution/:id" element={<ResolutionScreen />} />
        </Routes>
      </main>
    </div>
  );
}

export function severityBadge(s: string) {
  const map: Record<string, string> = {
    LOW: "bg-slate-700 text-slate-200",
    MEDIUM: "bg-amber-600/80 text-white",
    HIGH: "bg-orange-600 text-white",
    CRITICAL: "bg-red-600 text-white",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-semibold ${map[s] ?? map.LOW}`}>
      {s}
    </span>
  );
}

export function statusBadge(s: string) {
  const map: Record<string, string> = {
    OPEN: "bg-sky-700 text-white",
    INVESTIGATING: "bg-indigo-700 text-white",
    PENDING_REVIEW: "bg-purple-700 text-white",
    RESOLVED: "bg-emerald-700 text-white",
    REJECTED: "bg-rose-800 text-white",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${map[s] ?? "bg-slate-700 text-slate-200"}`}>
      {s}
    </span>
  );
}
