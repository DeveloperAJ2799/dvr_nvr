import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { nyaya, errMsg } from "../ipc";
import { useWorkspace } from "../App";

export default function RecoveryPage() {
  const { evidencePath, setOutput } = useWorkspace();
  const [image, setImage] = useState<string>("");
  const [workdir, setWorkdir] = useState<string>("recovered");
  const [joinGap, setJoinGap] = useState<number>(2);
  const [busy, setBusy] = useState<string | null>(null);
  const [recovery, setRecovery] = useState<string>("");

  const pick = async () => {
    const p = await open({
      filters: [
        { name: "Disk images", extensions: ["dd", "img", "raw"] },
        { name: "All files", extensions: ["*"] },
      ],
    });
    if (typeof p === "string") setImage(p);
  };

  const carve = async () => {
    if (!image) return;
    setBusy("Carving H.264 deleted recordings…");
    try {
      const r = await nyaya.carveDeleted(image, workdir, joinGap);
      setRecovery(JSON.stringify(r, null, 2));
    } catch (e) {
      setRecovery("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const decode = async () => {
    if (!image) return;
    const out = await save({
      title: "Save decoded MP4",
      defaultPath: "decoded.mp4",
      filters: [{ name: "MP4", extensions: ["mp4"] }],
    });
    if (!out) return;
    setBusy("Decoding (header strip + remux)…");
    try {
      let r = await nyaya.decodeVideo(image, out, 32);
      // FFmpeg-missing fallback: pull the DHAV runs out via the native
      // extraction adapter (no ffmpeg needed for the carve step).
      const j = r as Record<string, unknown>;
      if (j && j.ok === false && String(j.error ?? "").includes("ffmpeg")) {
        r = await nyaya.extractDahua(image, workdir + "/extracted");
      }
      setRecovery(JSON.stringify(r, null, 2));
      setOutput("decoded_mp4", out);
    } catch (e) {
      setRecovery("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">Recovery Engine</h1>
        <p className="mt-1 text-sm text-slate-400">
          Carve deleted H.264 footage (NAL <code>00 00 00 01 65</code>) and decode vendor containers.
        </p>
      </header>

      <div className="card grid gap-4 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="label">Image path</label>
          <div className="flex gap-2">
            <input
              className="input"
              value={image || evidencePath || ""}
              onChange={(e) => setImage(e.target.value)}
              placeholder={evidencePath ?? "no image selected"}
            />
            <button className="btn-secondary shrink-0" onClick={pick}>Browse</button>
          </div>
        </div>
        <div>
          <label className="label">Work directory</label>
          <input className="input" value={workdir} onChange={(e) => setWorkdir(e.target.value)} />
        </div>
        <div>
          <label className="label">Join gap (MB)</label>
          <input
            className="input"
            type="number"
            min={1}
            value={joinGap}
            onChange={(e) => setJoinGap(Number(e.target.value))}
          />
        </div>
      </div>

      <div className="flex flex-wrap gap-3">
        <button className="btn-primary" onClick={carve} disabled={!!busy || !image}>
          Carve deleted recordings
        </button>
        <button className="btn-secondary" onClick={decode} disabled={!!busy || !image}>
          Decode .dav/.hik → MP4
        </button>
      </div>
      {busy && <div className="text-sm text-amber-400">⏳ {busy}</div>}

      {recovery && (
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">Result</h3>
          <pre className="codeblock max-h-96 overflow-y-auto">{recovery}</pre>
        </section>
      )}
    </div>
  );
}