import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type CaseRecord } from "../ipc";

export default function CasesPage() {
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = async () => {
    setLoading(true);
    try {
      setCases(await api.listCases());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const open = async (id: string) => {
    try {
      await api.openCase(id);
      location.hash = "#/";
    } catch (e) {
      alert(`Failed to open case: ${(e as Error).message}`);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink-100">Cases</h1>
        <div className="flex gap-2">
          <button className="btn" onClick={refresh}>
            Refresh
          </button>
          <Link to="/cases/new" className="btn btn-primary">
            New Case
          </Link>
        </div>
      </div>

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-ink-400 border-b border-ink-700">
            <tr>
              <th className="text-left py-2 px-2">Case ID</th>
              <th className="text-left py-2 px-2">Name</th>
              <th className="text-left py-2 px-2">Examiner</th>
              <th className="text-left py-2 px-2">Created (UTC)</th>
              <th className="text-left py-2 px-2">Status</th>
              <th className="text-right py-2 px-2">Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={6} className="text-center py-6 text-ink-400">
                  Loading…
                </td>
              </tr>
            )}
            {!loading && cases.length === 0 && (
              <tr>
                <td colSpan={6} className="text-center py-6 text-ink-400">
                  No cases yet. Create one to begin.
                </td>
              </tr>
            )}
            {cases.map((c) => (
              <tr key={c.case_id} className="border-b border-ink-800 hover:bg-ink-800">
                <td className="py-2 px-2 font-mono text-blue-300">{c.case_id}</td>
                <td className="py-2 px-2">{c.case_name}</td>
                <td className="py-2 px-2">{c.examiner || "—"}</td>
                <td className="py-2 px-2 font-mono text-xs">{c.created_at_utc}</td>
                <td className="py-2 px-2">
                  <span className="badge badge-ok">{c.status}</span>
                </td>
                <td className="py-2 px-2 text-right">
                  <button
                    className="btn"
                    onClick={() => open(c.case_id)}
                  >
                    Open
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}