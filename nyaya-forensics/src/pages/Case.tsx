import { useState, type ChangeEvent } from "react";
import { save } from "@tauri-apps/plugin-dialog";
import { writeTextFile } from "@tauri-apps/plugin-fs";
import { useWorkspace } from "../App";
import { CaseInfo, emptyCase } from "../ipc";

export default function CasePage() {
  const { caseInfo, setCaseInfo, outputs, setOutput } = useWorkspace();
  const [form, setForm] = useState<CaseInfo>({ ...emptyCase(), ...caseInfo });
  const [saved, setSaved] = useState(false);

  const field = (k: keyof CaseInfo) =>
    (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  const saveCase = async () => {
    const path = await save({
      title: "Save case.json",
      defaultPath: "case.json",
      filters: [{ name: "JSON", extensions: ["json"] }],
    });
    if (!path) return;
    await writeTextFile(
      path,
      JSON.stringify(
        { ...form, reported_at_utc: new Date().toISOString() },
        null,
        2,
      ),
    );
    setCaseInfo(form);
    setOutput("case_json", path);
    setSaved(true);
  };

  return (
    <div className="max-w-3xl space-y-6">
      <header>
        <h1 className="text-2xl font-bold text-white">New Case</h1>
        <p className="mt-1 text-sm text-slate-400">
          Examiner metadata drives the §65B certificate page in the final PDF.
        </p>
      </header>

      <div className="card grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label">Case ID</label>
          <input className="input" value={form.case_id} onChange={field("case_id")} placeholder="e.g. SIH-DEMO-001" />
        </div>
        <div>
          <label className="label">Case / FIR Title</label>
          <input className="input" value={form.case_name} onChange={field("case_name")} placeholder="e.g. Bank counter theft" />
        </div>
        <div>
          <label className="label">Examiner</label>
          <input className="input" value={form.examiner} onChange={field("examiner")} placeholder="e.g. SI R. Kumar" />
        </div>
        <div>
          <label className="label">Organization</label>
          <input className="input" value={form.organization} onChange={field("organization")} placeholder="e.g. State Forensic Lab" />
        </div>
        <div className="sm:col-span-2">
          <label className="label">Assumed Timezone</label>
          <input className="input" value={form.timezone} onChange={field("timezone")} />
        </div>
        <div className="sm:col-span-2">
          <label className="label">Notes</label>
          <textarea className="input" rows={3} value={form.notes} onChange={field("notes")} />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button className="btn-primary" onClick={saveCase}>
          Save case.json
        </button>
        <button className="btn-secondary" onClick={() => setForm(emptyCase())}>
          Reset
        </button>
        {saved && (
          <span className="text-sm text-emerald-400">
            ✓ Saved — {outputs["case_json"] ?? ""}
          </span>
        )}
      </div>

      <section className="card">
        <h3 className="text-sm font-semibold text-slate-200">Case JSON preview</h3>
        <pre className="codeblock">
          {JSON.stringify(form, null, 2)}
        </pre>
      </section>
    </div>
  );
}