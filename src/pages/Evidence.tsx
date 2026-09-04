import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import {
  api,
  type EvidenceRecord,
  type IngestEvidenceInput,
} from "../ipc";
import { useActiveCase } from "../hooks/useActiveCase";

export default function EvidencePage() {
  const { active, refresh } = useActiveCase();
  const [items, setItems] = useState<EvidenceRecord[]>([]);
  const [verifying, setVerifying] = useState<string | null>(null);
  const [lastVerify, setLastVerify] = useState<boolean | null>(null);
  const [form, setForm] = useState<IngestEvidenceInput>({
    source_path: "",
    evidence_label: "",
    evidence_type: "",
    examiner: "",
    acquisition_method: "write-blocked image",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = async () => {
    if (!active) return setItems([]);
    try {
      setItems(await api.listEvidence());
    } catch {
      setItems([]);
    }
  };

  useEffect(() => {
    reload();
  }, [active?.case_id]);

  const pickFile = async () => {
    const sel = await open({
      multiple: false,
      directory: false,
      title: "Select evidence image or folder",
    });
    if (typeof sel === "string") {
      setForm((f) => ({ ...f, source_path: sel }));
    }
  };

  const pickFolder = async () => {
    const sel = await open({
      multiple: false,
      directory: true,
      title: "Select exported DVR folder",
    });
    if (typeof sel === "string") {
      setForm((f) => ({ ...f, source_path: sel, evidence_type: "exported_folder" }));
    }
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!active) {
      setError("Open or create a case first.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await api.ingestEvidence(form);
      setForm((f) => ({ ...f, source_path: "", evidence_label: "", notes: "" }));
      await reload();
      refresh();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  const verify = async (id: string) => {
    setVerifying(id);
    setError(null);
    try {
      const ok = await api.verifyEvidence(id);
      setLastVerify(ok);
      if (!ok) {
        setError(`Hash MISMATCH for ${id}`);
      }
    } catch (e) {
      setError(`Verification failed: ${(e as Error).message}`);
    } finally {
      setVerifying(null);
    }
  };

  return (
    <div className="p-6 space-y-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Evidence</h1>
        <p className="text-sm text-ink-400">
          Ingest disk images or exported DVR folders. Hashes are calculated in a streaming pass.
        </p>
      </div>

      {!active && (
        <div className="card border-amber-700/40">
          <div className="text-amber-300">
            No active case. Open or create a case from the Cases page first.
          </div>
        </div>
      )}

      {active && (
        <form onSubmit={submit} className="card space-y-3">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="md:col-span-2">
              <label className="label">Source path</label>
              <div className="flex gap-2">
                <input
                  className="input"
                  value={form.source_path}
                  onChange={(e) =>
                    setForm((f) => ({ ...f, source_path: e.target.value }))
                  }
                  placeholder="Path to .img/.dd/.raw or folder"
                  required
                />
                <button type="button" className="btn" onClick={pickFile}>
                  File…
                </button>
                <button type="button" className="btn" onClick={pickFolder}>
                  Folder…
                </button>
              </div>
            </div>
            <div>
              <label className="label">Label</label>
              <input
                className="input"
                value={form.evidence_label}
                onChange={(e) =>
                  setForm((f) => ({ ...f, evidence_label: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="label">Evidence type</label>
              <select
                className="input"
                value={form.evidence_type}
                onChange={(e) =>
                  setForm((f) => ({ ...f, evidence_type: e.target.value }))
                }
              >
                <option value="">Auto-detect</option>
                <option value="disk_image">Disk image</option>
                <option value="exported_folder">Exported folder</option>
              </select>
            </div>
            <div>
              <label className="label">Examiner</label>
              <input
                className="input"
                value={form.examiner}
                onChange={(e) =>
                  setForm((f) => ({ ...f, examiner: e.target.value }))
                }
              />
            </div>
            <div>
              <label className="label">Acquisition method</label>
              <input
                className="input"
                value={form.acquisition_method}
                onChange={(e) =>
                  setForm((f) => ({ ...f, acquisition_method: e.target.value }))
                }
              />
            </div>
          </div>
          <div>
            <label className="label">Notes</label>
            <textarea
              className="input"
              rows={2}
              value={form.notes}
              onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
            />
          </div>
          {error && <div className="text-sm text-red-400">{error}</div>}
          <div className="flex justify-end">
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Hashing…" : "Ingest & hash"}
            </button>
          </div>
        </form>
      )}

      {lastVerify !== null && (
        <div
          className={`card ${
            lastVerify
              ? "border-emerald-700/50"
              : "border-red-700/50"
          }`}
        >
          <div className="flex items-center justify-between">
            <div
              className={
                lastVerify
                  ? "text-emerald-300 font-medium"
                  : "text-red-300 font-medium"
              }
            >
              {lastVerify ? "Hash verified ✓" : "Hash verification FAILED ✗"}
            </div>
            <button className="btn" onClick={() => setLastVerify(null)}>
              Dismiss
            </button>
          </div>
          <div className="text-sm text-ink-300 mt-2">
            {lastVerify
              ? "Re-computed MD5/SHA-256 matches the recorded evidence manifest."
              : "Re-computed hash does not match the recorded value. Treat the evidence as potentially altered."}
          </div>
        </div>
      )}

      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-ink-400 border-b border-ink-700">
            <tr>
              <th className="text-left py-2 px-2">Evidence ID</th>
              <th className="text-left py-2 px-2">Type</th>
              <th className="text-left py-2 px-2">Source</th>
              <th className="text-left py-2 px-2">MD5</th>
              <th className="text-left py-2 px-2">SHA-256</th>
              <th className="text-left py-2 px-2">Size</th>
              <th className="text-right py-2 px-2">Verify</th>
            </tr>
          </thead>
          <tbody>
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="text-center py-6 text-ink-400">
                  No evidence ingested yet.
                </td>
              </tr>
            )}
            {items.map((e) => (
              <tr key={e.evidence_id} className="border-b border-ink-800">
                <td className="py-2 px-2 font-mono text-blue-300">{e.evidence_id}</td>
                <td className="py-2 px-2">{e.evidence_type}</td>
                <td className="py-2 px-2 truncate max-w-[200px]" title={e.source_path}>
                  {e.source_path}
                </td>
                <td className="py-2 px-2 font-mono text-xs">
                  {e.md5 ? e.md5.substring(0, 16) + "…" : "—"}
                </td>
                <td className="py-2 px-2 font-mono text-xs">
                  {e.sha256 ? e.sha256.substring(0, 16) + "…" : "—"}
                </td>
                <td className="py-2 px-2">{formatBytes(e.size_bytes)}</td>
                <td className="py-2 px-2 text-right">
                  <button
                    className="btn"
                    onClick={() => verify(e.evidence_id)}
                    disabled={verifying === e.evidence_id}
                  >
                    {verifying === e.evidence_id ? "…" : "Verify"}
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

function formatBytes(n: number): string {
  if (!n) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(2)} ${units[i]}`;
}