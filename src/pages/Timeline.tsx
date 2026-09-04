import { useState, useMemo } from "react";
import { useActiveCase } from "../hooks/useActiveCase";

export interface TimelineEntry {
  id: string;
  camera: string;
  timestamp: string; // ISO 8601
  seconds_epoch: number;
  event_type: "recording" | "motion" | "face" | "object" | "carved";
  label: string;
  confidence: number;
  details?: string;
  correlated_with?: string; // id of correlated event on another camera
}

const DEFAULT_EVENTS: TimelineEntry[] = [
  { id: "EV-001", camera: "CAM-01 (Entry)", timestamp: "2026-09-04T10:14:02Z", seconds_epoch: 1788516842, event_type: "recording", label: "Camera 1 Ingestion Stream", confidence: 1.0, details: "DHAV stream H.264 continuous" },
  { id: "EV-002", camera: "CAM-01 (Entry)", timestamp: "2026-09-04T10:14:15Z", seconds_epoch: 1788516855, event_type: "face", label: "Subject Face Detected", confidence: 0.89, details: "Frontal facial profile match" },
  { id: "EV-003", camera: "CAM-02 (Corridor)", timestamp: "2026-09-04T10:14:21Z", seconds_epoch: 1788516861, event_type: "motion", label: "Motion Surge (64%)", confidence: 0.94, details: "Subject rapid movement detected" },
  { id: "EV-004", camera: "CAM-02 (Corridor)", timestamp: "2026-09-04T10:14:24Z", seconds_epoch: 1788516864, event_type: "object", label: "Person Detected", confidence: 0.91, details: "Bounding box: [142, 60, 210, 480]" },
  { id: "EV-005", camera: "CAM-03 (Perimeter)", timestamp: "2026-09-04T10:15:30Z", seconds_epoch: 1788516930, event_type: "motion", label: "Vehicle Motion", confidence: 0.78, details: "Exterior movement detected" },
  { id: "EV-006", camera: "CAM-01 (Entry)", timestamp: "2026-09-04T10:18:40Z", seconds_epoch: 1788517120, event_type: "carved", label: "Carved Deleted Fragment", confidence: 0.85, details: "Recovered from unallocated sector 0x4B2000" },
];

export default function TimelinePage() {
  const { active } = useActiveCase();
  const [events, setEvents] = useState<TimelineEntry[]>(DEFAULT_EVENTS);
  const [filterCamera, setFilterCamera] = useState<string>("ALL");
  const [filterType, setFilterType] = useState<string>("ALL");
  const [correlationWindow, setCorrelationWindow] = useState<number>(10);
  const [correlatedPairs, setCorrelatedPairs] = useState<any[]>([]);

  const cameras = useMemo(() => {
    return Array.from(new Set(events.map((e) => e.camera)));
  }, [events]);

  const filteredEvents = useMemo(() => {
    return events.filter((e) => {
      if (filterCamera !== "ALL" && e.camera !== filterCamera) return false;
      if (filterType !== "ALL" && e.event_type !== filterType) return false;
      return true;
    });
  }, [events, filterCamera, filterType]);

  const runCrossCameraCorrelation = () => {
    const matches: any[] = [];
    for (let i = 0; i < events.length; i++) {
      for (let j = i + 1; j < events.length; j++) {
        const e1 = events[i];
        const e2 = events[j];
        if (e1.camera !== e2.camera) {
          const delta = Math.abs(e1.seconds_epoch - e2.seconds_epoch);
          if (delta <= correlationWindow) {
            matches.push({
              source: e1,
              target: e2,
              deltaSeconds: delta,
              summary: `${e1.camera} ➔ ${e2.camera} (Δ ${delta}s)`,
            });
          }
        }
      }
    }
    setCorrelatedPairs(matches);
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-ink-100">Multi-Camera Timeline &amp; Event Correlation</h1>
          <p className="text-sm text-ink-400 mt-1">
            Normalized IST/UTC temporal analysis with cross-camera spatial-temporal event correlation.
          </p>
        </div>
        <div className="flex gap-2">
          <button className="btn" onClick={() => setEvents([...DEFAULT_EVENTS])}>
            Reset / Sync Events
          </button>
          <button className="btn btn-primary" onClick={runCrossCameraCorrelation}>
            Run Multi-Cam Correlation (±{correlationWindow}s)
          </button>
        </div>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Open an active case to synchronize timeline data.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div>
              <label className="text-xs text-ink-400 font-medium">Filter by Camera</label>
              <select
                className="input w-full mt-1"
                value={filterCamera}
                onChange={(e) => setFilterCamera(e.target.value)}
              >
                <option value="ALL">All Cameras ({cameras.length})</option>
                {cameras.map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-ink-400 font-medium">Filter Event Type</label>
              <select
                className="input w-full mt-1"
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
              >
                <option value="ALL">All Event Types</option>
                <option value="recording">Recordings (Continuous/Scheduled)</option>
                <option value="motion">Motion Triggers</option>
                <option value="face">Face Detections</option>
                <option value="object">Object Detections</option>
                <option value="carved">Carved Candidates</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-ink-400 font-medium">Correlation Window (Seconds)</label>
              <input
                type="number"
                min={1}
                max={60}
                className="input w-full mt-1"
                value={correlationWindow}
                onChange={(e) => setCorrelationWindow(Number(e.target.value))}
              />
            </div>
          </div>

          {correlatedPairs.length > 0 && (
            <div className="card border-blue-600/40 bg-ink-900/60 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-md font-semibold text-blue-300">
                  Cross-Camera Temporal Matches ({correlatedPairs.length})
                </h3>
                <span className="badge badge-info text-xs">±{correlationWindow}s window</span>
              </div>
              <p className="text-xs text-ink-300">
                The following events occurred in close succession across different camera feeds, indicating possible subject movement across physical checkpoints:
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                {correlatedPairs.map((pair, idx) => (
                  <div key={idx} className="border border-ink-700 bg-ink-800 p-3 rounded space-y-1">
                    <div className="text-xs font-semibold text-blue-300 flex items-center justify-between">
                      <span>{pair.summary}</span>
                      <span className="text-emerald-400">Δ {pair.deltaSeconds}s</span>
                    </div>
                    <div className="text-xs text-ink-200">
                      <b>{pair.source.label}</b> ({pair.source.event_type}) at {pair.source.timestamp.split("T")[1]}
                    </div>
                    <div className="text-xs text-ink-200">
                      <b>{pair.target.label}</b> ({pair.target.event_type}) at {pair.target.timestamp.split("T")[1]}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="card space-y-3">
            <h3 className="text-lg font-semibold text-ink-100">
              Normalized Chronological Event Log ({filteredEvents.length})
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-ink-700 text-ink-400">
                    <th className="py-2">Time (UTC)</th>
                    <th className="py-2">Camera / Channel</th>
                    <th className="py-2">Type</th>
                    <th className="py-2">Event Description</th>
                    <th className="py-2">Confidence</th>
                    <th className="py-2">Forensic Metadata</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredEvents.map((ev) => (
                    <tr key={ev.id} className="border-b border-ink-800 hover:bg-ink-800/40">
                      <td className="py-2 font-mono text-xs text-ink-200">{ev.timestamp}</td>
                      <td className="py-2 font-medium text-ink-100">{ev.camera}</td>
                      <td className="py-2">
                        <span className={`badge ${badgeForType(ev.event_type)} text-xs uppercase`}>
                          {ev.event_type}
                        </span>
                      </td>
                      <td className="py-2 text-ink-200">{ev.label}</td>
                      <td className="py-2 font-semibold text-emerald-400">
                        {Math.round(ev.confidence * 100)}%
                      </td>
                      <td className="py-2 text-xs text-ink-400 max-w-xs truncate">{ev.details || "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function badgeForType(type: string) {
  switch (type) {
    case "face":
      return "badge-primary";
    case "motion":
      return "badge-warning";
    case "object":
      return "badge-info";
    case "carved":
      return "badge-danger";
    default:
      return "badge-neutral";
  }
}