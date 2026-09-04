import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { nyaya, errMsg } from "../ipc";
import { useWorkspace } from "../App";

export default function ReportPage() {
  const { outputs } = useWorkspace();
  const [paths, setPaths] = useState({
    cased: "",
    hashes: "",
    timeline: "",
    custody: "",
    out: "",
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string>("");

  const set = (k: keyof typeof paths) => (v: string) =>
    setPaths((p) => ({ ...p, [k]: v }));

  const pickFile = async (k: keyof typeof paths) => {
    const p = await open({ multiple: false });
    if (typeof p === "string") setPaths((prev) => ({ ...prev, [k]: p }));
  };

  const pickSave = async () => {
    const p = await save({
      title: "Save report PDF",
      defaultPath: "nyaya_report.pdf",
      filters: [{ name: "PDF", extensions: ["pdf"] }],
    });
    if (p) setPaths((prev) => ({ ...prev, out: p }));
  };

  const generate = async () => {
    setBusy("Generating court-ready PDF…");
    try {
      const r = await nyaya.generateReport({
        case: paths.cased,
        hashes: paths.hashes,
        timeline: paths.timeline,
        custody: paths.custody,
        out: paths.out,
      });
      setResult(JSON.stringify(r, null, 2));
    } catch (e) {
      setResult("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  const prefill = () => {
    setPaths({
      cased: outputs["case_json"] ?? "",
      hashes: outputs["hashes_json"] ?? "",
      timeline: "",
      custody: "",
      out: "nyaya_report.pdf",
    });
  };

  return (
    <div className="max-w-3xl space-y-6">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Report</h1>
          <p className="mt-1 text-sm text-slate-400">
            One-click ReportLab PDF — cover, case, device, hashes, timeline, recovered, AI, custody, §65B certificate.
          </p>
        </div>
        <button className="btn-secondary" onClick={prefill}>
          Pre-fill from workspace
        </button>
      </header>

      <div className="card grid gap-4 sm:grid-cols-2">
        {(
          [
            ["cased", "case.json"],
            ["hashes", "hashes.json"],
            ["timeline", "timeline.json"],
            ["custody", "custody.jsonl"],
          ] as const
        ).map(([k, label]) => (
          <div key={k}>
            <label className="label">{label}</label>
            <div className="flex gap-2">
              <input
                className="input"
                value={paths[k]}
                onChange={(e) => set(k)(e.target.value)}
                placeholder={k}
              />
              <button className="btn-secondary shrink-0" onClick={() => pickFile(k)}>
                …
              </button>
            </div>
          </div>
        ))}
        <div>
          <label className="label">Output PDF</label>
          <div className="flex gap-2">
            <input className="input" value={paths.out} onChange={(e) => set("out")(e.target.value)} />
            <button className="btn-secondary shrink-0" onClick={pickSave}>…</button>
          </div>
        </div>
      </div>

      <button className="btn-primary" onClick={generate} disabled={!!busy}>
        {busy || "Generate PDF"}
      </button>

      {result && (
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">Result</h3>
          <pre className="codeblock">{result}</pre>
        </section>
      )}
    </div>
  );
}