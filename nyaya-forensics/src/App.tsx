import { createContext, useContext, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import HomePage from "./pages/Home";
import CasePage from "./pages/Case";
import EvidencePage from "./pages/Evidence";
import TimelinePage from "./pages/Timeline";
import RecoveryPage from "./pages/Recovery";
import ReportPage from "./pages/Report";
import { CaseInfo, emptyCase } from "./ipc";

export type Workspace = {
  caseInfo: CaseInfo;
  setCaseInfo: (c: CaseInfo) => void;
  evidencePath: string | null;
  setEvidencePath: (p: string | null) => void;
  outputs: Record<string, string>;
  setOutput: (key: string, value: string) => void;
};

const WorkspaceCtx = createContext<Workspace>(null as unknown as Workspace);
export const useWorkspace = () => useContext(WorkspaceCtx);

const nav = [
  { to: "/", label: "Dashboard", end: true },
  { to: "/case", label: "Case", end: false },
  { to: "/evidence", label: "Evidence", end: false },
  { to: "/timeline", label: "Timeline", end: false },
  { to: "/recovery", label: "Recovery", end: false },
  { to: "/report", label: "Report", end: false },
];

export default function App() {
  const [caseInfo, setCaseInfo] = useState<CaseInfo>({
    case_id: "",
    case_name: "",
    examiner: "",
    organization: "",
    timezone: "Asia/Kolkata (IST, +05:30)",
    notes: "",
  });
  const [evidencePath, setEvidencePath] = useState<string | null>(null);
  const [outputs, setOutputs] = useState<Record<string, string>>({});

  const setOutput = (key: string, value: string) =>
    setOutputs((o) => ({ ...o, [key]: value }));

  const ws: Workspace = {
    caseInfo,
    setCaseInfo,
    evidencePath,
    setEvidencePath,
    outputs,
    setOutput,
  };

  return (
    <WorkspaceCtx.Provider value={ws}>
      <div className="flex h-screen w-screen overflow-hidden">
        <aside className="w-60 shrink-0 bg-ink-900 border-r border-slate-700/70 flex flex-col">
          <div className="px-4 py-4 border-b border-slate-700/70">
            <div className="text-sm font-bold tracking-wide text-white">
              NYAYA FORENSICS
            </div>
            <div className="text-[11px] uppercase tracking-widest text-brand-400">
              DVR/NVR Evidence Analyzer
            </div>
          </div>
          <nav className="flex-1 overflow-y-auto py-2">
            {nav.map((n) => (
              <NavLink
                key={n.to}
                to={n.to}
                end={n.end}
                className={({ isActive }) =>
                  `block px-4 py-2 text-sm transition-colors border-l-2 ${
                    isActive
                      ? "bg-slate-800 text-white border-brand-500"
                      : "text-slate-400 hover:bg-slate-800/60 border-transparent"
                  }`
                }
              >
                {n.label}
              </NavLink>
            ))}
          </nav>
          <div className="px-4 py-3 border-t border-slate-700/70 text-xs text-slate-400">
            <div className="font-medium text-slate-200">
              {caseInfo.case_name || "No open case"}
            </div>
            {evidencePath && (
              <div className="truncate mt-1 text-[11px]">{evidencePath}</div>
            )}
            <div className="mt-1 text-[11px] text-amber-500">
              For Law Enforcement Use Only
            </div>
          </div>
        </aside>

        <main className="flex-1 overflow-y-auto bg-ink-950 p-6">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/case" element={<CasePage />} />
            <Route path="/evidence" element={<EvidencePage />} />
            <Route path="/timeline" element={<TimelinePage />} />
            <Route path="/recovery" element={<RecoveryPage />} />
            <Route path="/report" element={<ReportPage />} />
          </Routes>
        </main>
      </div>
    </WorkspaceCtx.Provider>
  );
}