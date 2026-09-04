import { useEffect, useState } from "react";
import { api, type AppSettings } from "../ipc";

export default function SettingsPage() {
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [ffmpeg, setFfmpeg] = useState<string | null>(null);
  const [ffprobe, setFfprobe] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    api.getSettings().then(setSettings).catch(console.error);
    api.detectFfmpeg().then(setFfmpeg).catch(() => setFfmpeg(null));
    api.detectFfprobe().then(setFfprobe).catch(() => setFfprobe(null));
  }, []);

  if (!settings) return <div className="p-6 text-ink-400">Loading…</div>;

  const update = <K extends keyof AppSettings>(k: K, v: AppSettings[K]) =>
    setSettings((s) => (s ? { ...s, [k]: v } : s));

  const save = async () => {
    setSaving(true);
    setMsg(null);
    try {
      await api.saveSettings(settings);
      setMsg("Saved.");
    } catch (e) {
      setMsg(`Failed: ${(e as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl space-y-4">
      <h1 className="text-2xl font-semibold text-ink-100">Settings</h1>

      <div className="card space-y-3">
        <div>
          <label className="label">Case storage directory</label>
          <input
            className="input"
            value={settings.case_storage_dir}
            onChange={(e) => update("case_storage_dir", e.target.value)}
          />
        </div>
        <div>
          <label className="label">Default timezone</label>
          <select
            className="input"
            value={settings.default_timezone}
            onChange={(e) => update("default_timezone", e.target.value)}
          >
            <option value="UTC">UTC</option>
            <option value="local">Local</option>
          </select>
        </div>
        <div>
          <label className="label">FFmpeg path (optional override)</label>
          <input
            className="input"
            value={settings.ffmpeg_path ?? ""}
            onChange={(e) =>
              update("ffmpeg_path", e.target.value || null)
            }
            placeholder="auto-detected if blank"
          />
          <div className="text-xs text-ink-400 mt-1">
            Detected: {ffmpeg ?? "not found"}
          </div>
        </div>
        <div>
          <label className="label">FFprobe path (optional override)</label>
          <input
            className="input"
            value={settings.ffprobe_path ?? ""}
            onChange={(e) =>
              update("ffprobe_path", e.target.value || null)
            }
            placeholder="auto-detected if blank"
          />
          <div className="text-xs text-ink-400 mt-1">
            Detected: {ffprobe ?? "not found"}
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label">Carving chunk size (bytes)</label>
            <input
              className="input"
              type="number"
              value={settings.carving_chunk_size}
              onChange={(e) =>
                update("carving_chunk_size", Number(e.target.value))
              }
            />
          </div>
          <div>
            <label className="label">Recovery confidence threshold</label>
            <input
              className="input"
              type="number"
              step="0.05"
              min={0}
              max={1}
              value={settings.recovery_confidence_threshold}
              onChange={(e) =>
                update("recovery_confidence_threshold", Number(e.target.value))
              }
            />
          </div>
        </div>
        <div>
          <label className="label">Log level</label>
          <select
            className="input"
            value={settings.log_level}
            onChange={(e) => update("log_level", e.target.value)}
          >
            <option>error</option>
            <option>warn</option>
            <option>info</option>
            <option>debug</option>
            <option>trace</option>
          </select>
        </div>
        <div className="flex items-center gap-2">
          <input
            id="ai"
            type="checkbox"
            checked={settings.ai_enabled}
            onChange={(e) => update("ai_enabled", e.target.checked)}
          />
          <label htmlFor="ai" className="text-sm text-ink-300">
            Enable AI analytics (motion / object / face detection)
          </label>
        </div>

        {msg && <div className="text-sm text-ink-300">{msg}</div>}
        <div className="flex justify-end">
          <button className="btn btn-primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </div>
  );
}