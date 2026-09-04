import { useEffect, useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { nyaya, errMsg, type DriveListResult } from "../ipc";
import { useWorkspace as useWS } from "../App";

export default function EvidencePage() {
  const { evidencePath, setEvidencePath, outputs, setOutput, caseInfo } =
    useWS();
  const [busy, setBusy] = useState<string | null>(null);
  const [vendor, setVendor] = useState<string>("");
  const [acquired, setAcquired] = useState<string>("");
  const [drives, setDrives] = useState<DriveListResult | null>(null);
  const [ledgerMsg, setLedgerMsg] = useState<string>("");

  useEffect(() => {
    let unlisten: (() => void) | undefined;
    getCurrentWindow()
      .onDragDropEvent((event) => {
        if (event.payload.type === "drop") {
          const p = event.payload.paths?.[0];
          if (p) setEvidencePath(p);
        }
      })
      .then((fn) => {
        unlisten = fn;
      });
    return () => unlisten?.();
  }, [setEvidencePath]);

  const browse = async () => {
    const p = await open({
      multiple: false,
      filters: [
        { name: "Disk images", extensions: ["dd", "img", "E01", "e01", "raw"] },
        { name: "All files", extensions: ["*"] },
      ],
    });
    if (typeof p === "string") setEvidencePath(p);
  };

  const detect = async () => {
    if (!evidencePath) return;
    setBusy("Detecting vendor…");
    try {
      const r = await nyaya.detectVendor(evidencePath);
      setVendor(JSON.stringify(r, null, 2));
    } catch (e) {
      setVendor("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const acquire = async () => {
    if (!evidencePath) return;
    const out = await save({
      title: "Save acquired copy",
      defaultPath: "evidence_copy.dd",
      filters: [{ name: "Raw image", extensions: ["dd"] }],
    });
    if (!out) return;
    setBusy("Acquiring (dd + MD5/SHA-256)…");
    try {
      const r = await nyaya.acquireImage(evidencePath, out, true);
      // Persist the acquisition JSON so the Report page can prefill it.
      const hashPath = `${out}.hashes.json`;
      try {
        await writeTextFile(hashPath, JSON.stringify(r, null, 2));
        setOutput("hashes_json", hashPath);
      } catch {
        setOutput("hashes_json", out);
      }
      // Open the hash-chained custody ledger and record acquisition.
      const ledger = `${out}.custody.jsonl`;
      try {
        await nyaya.custodyAppend(
          ledger,
          caseInfo.examiner || "examiner",
          "acquire",
          { source: evidencePath, output: out },
        );
        setOutput("custody_jsonl", ledger);
        setLedgerMsg(`Custody ledger opened: ${ledger}`);
      } catch {
        setLedgerMsg("Custody ledger not written (custody module unavailable).");
      }
      setAcquired(JSON.stringify(r, null, 2));
    } catch (e) {
      setAcquired("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const loadDrives = async () => {
    setBusy("Enumerating physical drives…");
    try {
      setDrives(await nyaya.listDrives());
    } catch (e) {
      setLedgerMsg("Drive enumeration failed: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Evidence</h1>
        <p className="mt-1 text-sm text-slate-400">
          Drop the DVR HDD image here — the source is never modified.
        </p>
      </header>

      <div
        className="dropzone"
        onClick={browse}
        onDragOver={(e) => e.preventDefault()}
      >
        {evidencePath ? (
          <div>
            <div className="text-lg font-semibold text-brand-300">
              {evidencePath.split(/[\\/]/).pop()}
            </div>
            <div className="mt-1 text-xs text-slate-400">{evidencePath}</div>
          </div>
        ) : (
          <div>
            <div className="text-3xl">⬇️</div>
            <p className="mt-2 text-sm text-slate-300">
              Drag &amp; drop a <code>.dd</code>/<code>.img</code>/<code>.E01</code> image, or click to browse
            </p>
          </div>
        )}
      </div>

      {evidencePath && (
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" onClick={detect} disabled={!!busy}>
            {busy || "Detect Vendor"}
          </button>
          <button className="btn-secondary" onClick={acquire} disabled={!!busy}>
            Acquire copy + hashes
          </button>
        </div>
      )}

      <section className="card">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-slate-200">
            Physical drive acquisition (read-only)
          </h3>
          <button className="btn-secondary" onClick={loadDrives} disabled={!!busy}>
            List physical drives
          </button>
        </div>
        {drives && (
          <div className="mt-3 space-y-1 text-xs font-mono text-slate-300">
            {drives.physical_drives.length === 0 && (
              <div className="text-slate-500">No physical drives visible.</div>
            )}
            {drives.physical_drives.map((d) => (
              <button
                key={d.device}
                className="block w-full rounded bg-slate-800/60 px-2 py-1 text-left hover:bg-slate-700/60"
                onClick={() => setEvidencePath(d.device)}
              >
                {d.device} · {d.size_human}
                {d.model ? ` · ${d.model}` : ""}
              </button>
            ))}
            <div className="pt-1 text-[11px] text-slate-500">{drives.note}</div>
          </div>
        )}
      </section>

      {ledgerMsg && <div className="text-xs text-emerald-400">{ledgerMsg}</div>}
      {busy && (
        <div className="text-sm text-amber-400">⏳ {busy}</div>
      )}

      {vendor && (
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">Vendor ID</h3>
          <pre className="codeblock">{vendor}</pre>
        </section>
      )}
      {acquired && (
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">
            Acquisition result (stored: {outputs["hashes_json"] || "not saved"})
          </h3>
          <pre className="codeblock">{acquired}</pre>
        </section>
      )}
    </div>
  );
}