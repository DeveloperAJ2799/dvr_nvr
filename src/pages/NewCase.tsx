import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type NewCaseInput } from "../ipc";

export default function NewCasePage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<NewCaseInput>({
    case_id: "",
    case_name: "",
    examiner: "",
    organization: "",
    timezone_assumption: "UTC",
    notes: "",
  });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const update = <K extends keyof NewCaseInput>(k: K, v: NewCaseInput[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createCase(form);
      navigate("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <h1 className="text-2xl font-semibold text-ink-100 mb-4">New Case</h1>

      <form onSubmit={submit} className="card space-y-4">
        <div>
          <label className="label">Case ID (optional; auto-generated if blank)</label>
          <input
            className="input"
            placeholder="CASE-001"
            value={form.case_id ?? ""}
            onChange={(e) => update("case_id", e.target.value)}
          />
        </div>
        <div>
          <label className="label">Case name *</label>
          <input
            className="input"
            required
            value={form.case_name}
            onChange={(e) => update("case_name", e.target.value)}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Examiner</label>
            <input
              className="input"
              value={form.examiner}
              onChange={(e) => update("examiner", e.target.value)}
            />
          </div>
          <div>
            <label className="label">Organization</label>
            <input
              className="input"
              value={form.organization}
              onChange={(e) => update("organization", e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="label">Timezone assumption</label>
          <select
            className="input"
            value={form.timezone_assumption}
            onChange={(e) => update("timezone_assumption", e.target.value)}
          >
            <option value="UTC">UTC</option>
            <option value="local">Local system</option>
          </select>
          <p className="text-xs text-ink-400 mt-1">
            Recorded assumption used when normalizing vendor timestamps.
          </p>
        </div>
        <div>
          <label className="label">Notes</label>
          <textarea
            className="input"
            rows={3}
            value={form.notes}
            onChange={(e) => update("notes", e.target.value)}
          />
        </div>

        {error && <div className="text-sm text-red-400">{error}</div>}

        <div className="flex justify-end gap-2">
          <button
            type="button"
            className="btn"
            onClick={() => navigate("/cases")}
            disabled={submitting}
          >
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={submitting}>
            {submitting ? "Creating…" : "Create case"}
          </button>
        </div>
      </form>
    </div>
  );
}