import { NavLink, Route, Routes } from "react-router-dom";
import Dashboard from "./pages/Dashboard";
import CasesPage from "./pages/Cases";
import NewCasePage from "./pages/NewCase";
import EvidencePage from "./pages/Evidence";
import ParsersPage from "./pages/Parsers";
import ExtractionPage from "./pages/Extraction";
import RecoveryPage from "./pages/Recovery";
import TimelinePage from "./pages/Timeline";
import MediaLibraryPage from "./pages/MediaLibrary";
import AnalyticsPage from "./pages/Analytics";
import ReportsPage from "./pages/Reports";
import SettingsPage from "./pages/Settings";
import { useActiveCase } from "./hooks/useActiveCase";

const nav = [
  { to: "/", label: "Dashboard" },
  { to: "/cases", label: "Cases" },
  { to: "/evidence", label: "Evidence" },
  { to: "/parsers", label: "Parsers" },
  { to: "/extraction", label: "Extract" },
  { to: "/recovery", label: "Recovery" },
  { to: "/timeline", label: "Timeline" },
  { to: "/library", label: "Media Library" },
  { to: "/analytics", label: "Analytics" },
  { to: "/reports", label: "Reports" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  const { active } = useActiveCase();

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <aside className="w-56 bg-ink-900 border-r border-ink-700 flex flex-col">
        <div className="px-4 py-4 border-b border-ink-700">
          <div className="text-sm font-semibold text-ink-100">
            DVR/NVR Forensic
          </div>
          <div className="text-xs text-ink-400">Analyzer</div>
        </div>
        <nav className="flex-1 overflow-y-auto py-2">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.to === "/"}
              className={({ isActive }) =>
                `block px-4 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-ink-800 text-ink-100 border-l-2 border-blue-500"
                    : "text-ink-300 hover:bg-ink-800 border-l-2 border-transparent"
                }`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        <div className="px-4 py-3 border-t border-ink-700 text-xs text-ink-400">
          {active ? (
            <>
              <div className="font-medium text-ink-200">{active.case_id}</div>
              <div className="truncate">{active.case_name}</div>
            </>
          ) : (
            <div>No active case</div>
          )}
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-ink-950">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/cases" element={<CasesPage />} />
          <Route path="/cases/new" element={<NewCasePage />} />
          <Route path="/evidence" element={<EvidencePage />} />
          <Route path="/parsers" element={<ParsersPage />} />
          <Route path="/extraction" element={<ExtractionPage />} />
          <Route path="/recovery" element={<RecoveryPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/library" element={<MediaLibraryPage />} />
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/settings" element={<SettingsPage />} />
        </Routes>
      </main>
    </div>
  );
}