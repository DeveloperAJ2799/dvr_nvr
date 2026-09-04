import { useEffect, useState } from "react";
import { api, type ParserInfo } from "../ipc";

export default function ParsersPage() {
  const [parsers, setParsers] = useState<ParserInfo[]>([]);

  useEffect(() => {
    api.listParsers().then(setParsers).catch(console.error);
  }, []);

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Vendor Parsers</h1>
        <p className="text-sm text-ink-400">
          The parser framework is live. Vendor-specific parsing will be activated
          once sample data is available.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {parsers.map((p) => (
          <div key={p.vendor_id} className="card">
            <div className="flex items-center justify-between">
              <div className="text-lg font-semibold text-ink-100">{p.vendor}</div>
              <span className="badge badge-info">priority {p.priority}</span>
            </div>
            <div className="text-xs text-ink-400 mt-1">id: {p.vendor_id}</div>
            <p className="text-sm text-ink-300 mt-2">{p.description}</p>
          </div>
        ))}
      </div>
    </div>
  );
}