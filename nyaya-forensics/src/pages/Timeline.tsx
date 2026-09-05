import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { readTextFile } from "@tauri-apps/plugin-fs";
import { Timeline } from "vis-timeline";
import { DataSet } from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import {
  TimelineEvent,
  nyaya,
  errMsg,
  type CorrelationResult,
} from "../ipc";

type Item = { id: number; group: number; content: string; start: string };

const GROUP_COLORS = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#a855f7"];

function eventsToItems(events: TimelineEvent[]): Item[] {
  const groupMap = new Map<string, number>();
  return events
    .filter((e) => e.utc)
    .map((e, i) => {
      const cam = e.camera ?? "CAM-?";
      if (!groupMap.has(cam)) groupMap.set(cam, groupMap.size);
      return {
        id: i,
        group: groupMap.get(cam)!,
        content: `${e.event ?? "event"}${e.confidence ? " (" + e.confidence + ")" : ""}`,
        start: e.utc!,
      };
    });
}

export default function TimelinePage() {
  const ref = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [loaded, setLoaded] = useState("");
  const [eventFiles, setEventFiles] = useState<string[]>([]);
  const [windowSec, setWindowSec] = useState<number>(10);
  const [corr, setCorr] = useState<CorrelationResult | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const render = (evts: TimelineEvent[]) => {
    setItems(eventsToItems(evts));
    setLoaded(`${evts.filter((e) => e.utc).length} events`);
  };

  const loadFile = async () => {
    const p = await open({
      filters: [{ name: "Timeline JSON", extensions: ["json"] }],
    });
    if (typeof p !== "string") return;
    try {
      const raw = JSON.parse(await readTextFile(p));
      const evts = Array.isArray(raw) ? raw : raw.events ?? [];
      render(evts);
      setEventFiles((f) => (f.includes(p) ? f : [...f, p]));
    } catch (e) {
      setLoaded("Failed to parse: " + String(e));
    }
  };

  const addEventFile = async () => {
    const p = await open({
      multiple: true,
      filters: [{ name: "Events JSON", extensions: ["json"] }],
    });
    const paths = Array.isArray(p) ? p : typeof p === "string" ? [p] : [];
    setEventFiles((f) => [...f, ...paths.filter((x) => !f.includes(x))]);
  };

  const correlate = async () => {
    setBusy("Normalising timestamps + correlating…");
    setError(null);
    if (eventFiles.length === 0) {
      setError("Please add at least one events JSON file to perform cross-camera correlation.");
      setBusy(null);
      return;
    }
    try {
      const r = await nyaya.correlateTimeline(eventFiles, windowSec);
      setCorr(r);
      render(r.events as TimelineEvent[]);
      setLoaded((l) => l + " · correlated ±" + windowSec + "s");
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(null);
    }
  };

  useEffect(() => {
    if (!ref.current || items.length === 0) return;
    const groups = new DataSet(
      [...new Set(items.map((i) => i.group))].map((g) => ({
        id: g,
        content: `CAM-${g + 1}`,
      })),
    );
    const ds = new DataSet(items);
    const tl = new Timeline(ref.current, ds, {
      groups,
      height: "430px",
      minHeight: "300px",
      start: items[0].start,
      end: items[items.length - 1].start,
      selectable: true,
      editable: false,
      zoomKey: "ctrlKey",
    });
    return () => tl.destroy();
  }, [items]);

  return (
    <div className="max-w-5xl space-y-5">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold text-white">Timeline</h1>
          <p className="mt-1 text-sm text-slate-400">
            Normalised multi-camera events — BCD→UTC converted, zoom &amp; pan with mouse.
          </p>
        </div>
        <div className="flex gap-3">
          <button className="btn-secondary" onClick={loadFile}>
            Open timeline.json
          </button>
        </div>
      </header>

      <section className="card space-y-3">
        <h3 className="text-sm font-semibold text-slate-200">
          Cross-camera correlation (±10 s subject tracking)
        </h3>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-secondary" onClick={addEventFile}>
            Add events JSON
          </button>
          {eventFiles.map((f) => (
            <span
              key={f}
              className="flex items-center gap-1 rounded bg-slate-800 px-2 py-1 text-xs text-slate-300"
            >
              {f.split(/[\\/]/).pop()}
              <button
                className="text-slate-500 hover:text-red-400"
                onClick={() => setEventFiles((fs) => fs.filter((x) => x !== f))}
              >
                ✕
              </button>
            </span>
          ))}
          <label className="ml-2 text-xs text-slate-400">
            window (s)
            <input
              className="input ml-1 w-20"
              type="number"
              min={1}
              value={windowSec}
              onChange={(e) => setWindowSec(Number(e.target.value))}
            />
          </label>
          <button className="btn-primary" onClick={correlate} disabled={!!busy}>
            Correlate
          </button>
        </div>
        <p className="text-xs text-slate-500">
          Add one or more JSON event files from AI analytics, CCTV event logs, or DHAV-derived extractions. All events are normalised to UTC/IST before cross-camera correlation.
        </p>
        {busy && <div className="text-sm text-amber-400">⏳ {busy}</div>}
        {error && <div className="text-sm text-red-400">⚠ {error}</div>}
      </section>

      {corr && (
        <section className="card space-y-3">
          <h3 className="text-sm font-semibold text-slate-200">
            Correlation result — {corr.correlation_count} pair(s),{" "}
            {corr.tracks.length} track(s), {corr.parse_errors.length} parse
            error(s)
          </h3>
          {corr.tracks.map((t, i) => (
            <div key={i} className="rounded border border-slate-700 bg-slate-800/40 p-3">
              <div className="text-xs font-semibold text-brand-300">
                Track {i + 1}: {t.cameras.join(" → ")} · {t.event_count} events ·
                span {t.span_seconds}s
              </div>
              <div className="mt-1 space-y-0.5 text-xs text-slate-400">
                {t.events.map((e, j) => (
                  <div key={j}>
                    {e.utc} ({e.ist}) — {e.camera}: {e.event}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </section>
      )}

      <div className="card">
        <div className="mb-2 text-xs text-slate-400">
          {loaded || "No data loaded yet."}
        </div>
        <div ref={ref} className="rounded-lg bg-slate-900 [&_.vis-timeline]:!bg-slate-900 [&_.vis-item]:!bg-brand-700 [&_.vis-item]:!border-brand-500" />
      </div>
    </div>
  );
}