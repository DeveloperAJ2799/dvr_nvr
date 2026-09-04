import { useEffect, useState } from "react";
import { api, type CaseRecord, type ParserInfo } from "../ipc";
import { useActiveCase } from "../hooks/useActiveCase";
import { Link } from "react-router-dom";

export default function Dashboard() {
  const { active, refresh } = useActiveCase();
  const [cases, setCases] = useState<CaseRecord[]>([]);
  const [parsers, setParsers] = useState<ParserInfo[]>([]);

  useEffect(() => {
    api.listCases().then(setCases).catch(console.error);
    api.listParsers().then(setParsers).catch(console.error);
  }, []);

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Dashboard</h1>
        <p className="text-sm text-ink-400">
          Vendor-agnostic DVR/NVR forensic workbench.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card title="Active case" value={active ? active.case_id : "None"} subtitle={active?.case_name ?? "Open or create a case to begin"} />
        <Card title="Total cases" value={String(cases.length)} subtitle="Stored locally" />
        <Card title="Parsers available" value={String(parsers.length)} subtitle="Plugin framework ready" />
        <Card title="MVP status" value="Day 1" subtitle="Skeleton + case + ingestion" />
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-3">Quick actions</h2>
        <div className="flex flex-wrap gap-2">
          <Link className="btn btn-primary" to="/cases/new">
            New Case
          </Link>
          <Link className="btn" to="/cases">
            Open Case
          </Link>
          <Link className="btn" to="/evidence">
            Ingest Evidence
          </Link>
          <Link className="btn" to="/parsers">
            Browse Parsers
          </Link>
          <button className="btn" onClick={refresh}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card">
        <h2 className="text-lg font-semibold mb-3">Registered vendor parsers</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {parsers.map((p) => (
            <div
              key={p.vendor_id}
              className="border border-ink-700 rounded p-2 bg-ink-800"
            >
              <div className="text-sm font-medium text-ink-100">{p.vendor}</div>
              <div className="text-xs text-ink-400">priority {p.priority}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="card border-amber-700/40">
        <h2 className="text-lg font-semibold text-amber-300 mb-2">
          Forensic notice
        </h2>
        <p className="text-sm text-ink-300">
          AI analytics results are investigative aids and require human verification.
          Original evidence is never modified by this application.
        </p>
      </div>
    </div>
  );
}

function Card({
  title,
  value,
  subtitle,
}: {
  title: string;
  value: string;
  subtitle?: string;
}) {
  return (
    <div className="card">
      <div className="text-xs uppercase tracking-wider text-ink-400">
        {title}
      </div>
      <div className="text-2xl font-semibold text-ink-100 mt-1">{value}</div>
      {subtitle && (
        <div className="text-xs text-ink-400 mt-1 truncate">{subtitle}</div>
      )}
    </div>
  );
}