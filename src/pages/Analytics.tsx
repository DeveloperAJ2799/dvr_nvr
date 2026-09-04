import { useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useActiveCase } from "../hooks/useActiveCase";
import { api } from "../ipc";

export default function AnalyticsPage() {
  const { active } = useActiveCase();
  const [videoPath, setVideoPath] = useState<string>("");
  const [mode, setMode] = useState<"face" | "motion" | "object">("face");
  const [analyzing, setAnalyzing] = useState<boolean>(false);
  const [analyticsResult, setAnalyticsResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const browseVideo = async () => {
    const sel = await open({
      multiple: false,
      title: "Select video clip for forensic AI analytics",
      filters: [{ name: "Video Files", extensions: ["mp4", "mkv", "avi", "mov", "dav", "hik"] }],
    });
    if (typeof sel === "string") {
      setVideoPath(sel);
    }
  };

  const runAnalytics = async () => {
    if (!videoPath) return;
    setAnalyzing(true);
    setError(null);
    setAnalyticsResult(null);

    try {
      const resp = await api.runAiAnalytics(videoPath, mode);
      if (resp.json) {
        if (resp.json.error) {
          setError(resp.json.error);
        } else {
          setAnalyticsResult(resp.json);
        }
      } else {
        setError(resp.stderr || "AI analytics returned unexpected output");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Intelligent Video Analytics Suite</h1>
        <p className="text-sm text-ink-400 mt-1">
          Automated event detection: facial identification, person/vehicle object tracking, and motion analysis.
        </p>
      </div>

      <div className="card border-amber-700/40 bg-amber-950/20">
        <div className="text-amber-300 text-sm font-medium">
          Forensic Admissibility Notice:
        </div>
        <p className="text-xs text-ink-300 mt-1">
          AI analytics outputs are investigative aids intended to accelerate CCTV triage. Under Section 65B/63 guidelines, automated detections must be reviewed and confirmed by the forensic examiner before submission into evidence.
        </p>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Open a case to run AI analytics.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">Analytics Configuration</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2 space-y-1">
                <label className="text-xs text-ink-400 font-medium">Target Video Clip</label>
                <div className="flex gap-2">
                  <input
                    className="input flex-1"
                    placeholder="Path to extracted or recovered MP4 video clip"
                    value={videoPath}
                    onChange={(e) => setVideoPath(e.target.value)}
                  />
                  <button className="btn" onClick={browseVideo}>
                    Browse
                  </button>
                </div>
              </div>
              <div className="space-y-1">
                <label className="text-xs text-ink-400 font-medium">Analytics Mode</label>
                <select
                  className="input w-full"
                  value={mode}
                  onChange={(e) => setMode(e.target.value as any)}
                >
                  <option value="face">Face Detection (Haar Cascades)</option>
                  <option value="motion">Motion Detection (Frame Diff)</option>
                  <option value="object">Object Detection (Persons / Vehicles)</option>
                </select>
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                className="btn btn-primary"
                onClick={runAnalytics}
                disabled={analyzing || !videoPath}
              >
                {analyzing ? `Processing ${mode.toUpperCase()} Detections...` : `Run ${mode.toUpperCase()} Analytics`}
              </button>
              <span className="text-xs text-ink-400">
                Runs locally on CPU/GPU without uploading evidence to any remote server.
              </span>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-700/50 rounded text-red-300 text-sm">
              {error}
            </div>
          )}

          {analyticsResult && (
            <div className="space-y-4">
              <div className="card border-blue-600/40 bg-ink-900/60 flex flex-wrap justify-between items-center">
                <div>
                  <div className="text-sm font-semibold text-blue-300 uppercase">
                    {analyticsResult.mode} Analytics Complete
                  </div>
                  <div className="text-xs text-ink-400 mt-1">
                    FPS: {analyticsResult.fps} · Total Frames: {analyticsResult.total_frames} · Duration: {analyticsResult.duration_seconds}s
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-emerald-400">
                    {analyticsResult.event_count || 0}
                  </div>
                  <div className="text-xs text-ink-400">Detected Events</div>
                </div>
              </div>

              {analyticsResult.events && analyticsResult.events.length > 0 ? (
                <div className="card space-y-3">
                  <h3 className="text-lg font-semibold text-ink-100">
                    Detections List ({analyticsResult.events.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-ink-700 text-ink-400">
                          <th className="py-2">Time (UTC)</th>
                          <th className="py-2">Frame</th>
                          <th className="py-2">Detection Type</th>
                          <th className="py-2">Confidence</th>
                          <th className="py-2">Bounding Coordinates [x, y, w, h]</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analyticsResult.events.map((ev: any, idx: number) => (
                          <tr key={idx} className="border-b border-ink-800 hover:bg-ink-800/40">
                            <td className="py-2 font-mono text-xs text-ink-200">
                              {ev.timestamp_utc} ({ev.seconds}s)
                            </td>
                            <td className="py-2 text-ink-300">#{ev.frame}</td>
                            <td className="py-2">
                              <span className="badge badge-primary text-xs">
                                {ev.label || ev.event_type}
                              </span>
                            </td>
                            <td className="py-2 font-semibold text-emerald-400">
                              {Math.round((ev.confidence || 0) * 100)}%
                            </td>
                            <td className="py-2 font-mono text-xs text-ink-400">
                              {ev.bounding_box ? `[${ev.bounding_box.join(", ")}]` : (ev.motion_ratio ? `Ratio: ${ev.motion_ratio}` : "—")}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              ) : (
                <div className="card text-ink-400 text-sm">
                  No {mode} triggers exceeded the confidence threshold in this video segment.
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}