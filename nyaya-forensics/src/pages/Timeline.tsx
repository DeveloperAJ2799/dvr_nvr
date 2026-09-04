import { useEffect, useRef, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { readTextFile } from "@tauri-apps/plugin-fs";
import { Timeline } from "vis-timeline";
import { DataSet } from "vis-data";
import "vis-timeline/styles/vis-timeline-graph2d.min.css";
import { TimelineEvent } from "../ipc";

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

const SAMPLE: TimelineEvent[] = [
  { utc: "2026-09-04T06:00:00Z", camera: "CAM-01", event: "person-enter", confidence: 0.92 },
  { utc: "2026-09-04T06:00:07Z", camera: "CAM-02", event: "vehicle-stop", confidence: 0.87 },
  { utc: "2026-09-04T06:00:12Z", camera: "CAM-01", event: "face-capture", confidence: 0.81 },
  { utc: "2026-09-04T06:01:30Z", camera: "CAM-03", event: "motion", confidence: 0.66 },
];

export default function TimelinePage() {
  const ref = useRef<HTMLDivElement>(null);
  const [items, setItems] = useState<Item[]>([]);
  const [loaded, setLoaded] = useState("");

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
    } catch (e) {
      setLoaded("Failed to parse: " + String(e));
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
          <button className="btn-primary" onClick={() => render(SAMPLE)}>
            Load sample
          </button>
          <button className="btn-secondary" onClick={loadFile}>
            Open timeline.json
          </button>
        </div>
      </header>

      <div className="card">
        <div className="mb-2 text-xs text-slate-400">
          {loaded || "No data loaded yet."}
        </div>
        <div ref={ref} className="rounded-lg bg-slate-900 [&_.vis-timeline]:!bg-slate-900 [&_.vis-item]:!bg-brand-700 [&_.vis-item]:!border-brand-500" />
      </div>
    </div>
  );
}