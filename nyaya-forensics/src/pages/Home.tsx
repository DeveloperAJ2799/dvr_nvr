import { useEffect, useState } from "react";
import { nyaya, errMsg } from "../ipc";

export default function Home() {
  const [info, setInfo] = useState<string>("");
  const [py, setPy] = useState<string>("");

  useEffect(() => {
    nyaya
      .appInfo()
      .then((v) => setInfo(JSON.stringify(v, null, 2)))
      .catch((e) => setInfo("app info error: " + errMsg(e)));
    nyaya
      .pythonInfo()
      .then((v) => setPy(JSON.stringify(v, null, 2)))
      .catch((e) => setPy("python info error: " + errMsg(e)));
  }, []);

  return (
    <div className="max-w-4xl space-y-6">
      <header>
        <h1 className="text-3xl font-extrabold text-white">NYAYA Forensics</h1>
        <p className="mt-1 text-sm text-slate-400">
          Unified vendor-agnostic DVR/NVR forensic analysis — acquire, parse,
          recover, timeline, AI-triage and report in one offline desktop app.
        </p>
        <div className="mt-4 flex flex-wrap gap-3">
          <span className="rounded-full border border-brand-700 bg-brand-900/40 px-3 py-1 text-xs font-semibold text-brand-300">Tauri v2 + Rust</span>
          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300">React + Tailwind</span>
          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300">Python sidecar core</span>
          <span className="rounded-full border border-slate-700 bg-slate-800 px-3 py-1 text-xs font-semibold text-slate-300">YOLOv8n + InsightFace</span>
        </div>
      </header>

      <section className="card">
        <h2 className="text-lg font-semibold text-white">Workflow</h2>
        <ol className="mt-3 list-decimal space-y-2 pl-5 text-sm text-slate-300">
          <li><b className="text-slate-100">Case</b> — create case + examiner metadata.</li>
          <li><b className="text-slate-100">Evidence</b> — drag-drop the HDD image, auto-detect vendor, acquire with MD5/SHA-256.</li>
          <li><b className="text-slate-100">Timeline</b> — browse normalised multi-camera events (vis-timeline).</li>
          <li><b className="text-slate-100">Recovery</b> — carve deleted H.264 footage + decode vendor containers.</li>
          <li><b className="text-slate-100">Report</b> — one-click ReportLab PDF with Section 65B certificate.</li>
        </ol>
      </section>

      <div className="grid gap-4 sm:grid-cols-2">
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">App status</h3>
          <pre className="codeblock">{info || "…"}</pre>
        </section>
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">Python sidecar</h3>
          <pre className="codeblock">{py || "…"}</pre>
        </section>
      </div>
    </div>
  );
}