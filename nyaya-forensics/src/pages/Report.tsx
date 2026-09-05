import { useState } from "react";
import { open, save } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { nyaya, errMsg, type CustodyVerifyResult } from "../ipc";
import { useWorkspace } from "../App";

export default function ReportPage() {
  const { outputs, caseInfo } = useWorkspace();
  const [paths, setPaths] = useState({
    cased: "",
    hashes: "",
    timeline: "",
    custody: "",
    out: "",
  });
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<string>("");
  const [chain, setChain] = useState<CustodyVerifyResult | null>(null);

  const verifyChain = async () => {
    if (!paths.custody) {
      setChain(null);
      return;
    }
    setBusy("Verifying custody hash-chain…");
    try {
      setChain(await nyaya.custodyVerify(paths.custody));
    } catch (e) {
      setResult("ERROR: " + errMsg(e));
    } finally {
      setBusy(null);
    }
  };

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
      let casePath = paths.cased;
      if (!casePath) {
        casePath = "case_auto.json";
        await writeTextFile(
          casePath,
          JSON.stringify(
            {
              case_id: caseInfo.case_id || "DEMO-CASE-001",
              case_name: caseInfo.case_name || "CCTV Forensic Investigation",
              examiner: caseInfo.examiner || "Forensic Examiner",
              organization: caseInfo.organization || "Forensic Science Laboratory",
              timezone: caseInfo.timezone || "Asia/Kolkata (IST, +05:30)",
              notes: caseInfo.notes || "Auto-generated report from NYAYA Forensics",
              reported_at_utc: new Date().toISOString(),
            },
            null,
            2,
          ),
        );
      }
      const r = await nyaya.generateReport({
        case: casePath,
        hashes: paths.hashes,
        timeline: paths.timeline,
        custody: paths.custody,
        out: paths.out || "nyaya_report.pdf",
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
      custody: outputs["custody_jsonl"] ?? "",
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

      <section className="card space-y-3">
        <h3 className="text-sm font-semibold text-slate-200">
          Chain-of-custody integrity (SHA-256 hash-chained ledger)
        </h3>
        <div className="text-xs text-slate-500">
          Examiner: {caseInfo.examiner || "—"} · Ledger: {paths.custody || "not set"}
        </div>
        <button
          className="btn-secondary"
          onClick={verifyChain}
          disabled={!!busy || !paths.custody}
        >
          Verify custody chain
        </button>
        {chain && (
          <div
            className={`rounded border p-3 text-sm ${
              chain.valid
                ? "border-emerald-700 bg-emerald-950/40 text-emerald-300"
                : "border-red-700 bg-red-950/40 text-red-300"
            }`}
          >
            {chain.valid
              ? `✓ Chain intact — all ${chain.total_entries} entries verified.`
              : `✗ TAMPERING at seq #${chain.broken_at_seq} — ${chain.message}`}
            {chain.valid && chain.head_hash && (
              <div className="mt-1 font-mono text-xs text-slate-400">
                head: {chain.head_hash.slice(0, 32)}…
              </div>
            )}
          </div>
        )}
      </section>

      {result && (
        <section className="card">
          <h3 className="text-sm font-semibold text-slate-200">Result</h3>
          <pre className="codeblock">{result}</pre>
        </section>
      )}
    </div>
  );
}