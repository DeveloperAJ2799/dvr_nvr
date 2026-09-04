import { useEffect, useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { nyaya, errMsg } from "../ipc";
import { useWorkspace as useWS } from "../App";

export default function EvidencePage() {
  const { evidencePath, setEvidencePath, outputs, setOutput } = useWS();
  const [busy, setBusy] = useState<string | null>(null);
  const [vendor, setVendor] = useState<string>("");
  const [acquired, setAcquired] = useState<string>("");

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
      setAcquired(JSON.stringify(r, null, 2));
    } catch (e) {
      setAcquired("ERROR: " + errMsg(e));
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