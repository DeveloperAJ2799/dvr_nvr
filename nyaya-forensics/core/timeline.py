#!/usr/bin/env python3
"""
NYAYA Forensics - core/timeline.py
Multi-camera timeline normaliser + ±window event correlation (SIH PS §D).

Accepts one or more event JSON files. Each file is either a bare list of
events or {"events": [...]}. Recognised time fields (first match wins):
  epoch | seconds_epoch | hik_epoch  -> absolute Unix seconds
  utc | timestamp | ist              -> ISO-8601 (naive = UTC)
  dahua_bcd                          -> 14-digit BCD, device-local (IST)
Extra fields kept: camera, event/label, confidence, source_file.

Correlation rule (PS: "±10 s cross-camera event correlation"):
  1. pair every two events on DIFFERENT cameras with |Δt| <= window;
  2. greedily union them into tracks so CAM-01 → CAM-02 → CAM-03 subject
     movement forms a single correlated track.

Usage:
  python core/timeline.py --inputs t1.json t2.json --window 10 --out correlated.json
  python core/timeline.py --inputs ai_events.json --window 10
"""
import argparse
import json
import sys

from timestamps import normalize_any  # same folder when run as script


def load_events(paths):
    events = []
    for p in paths or []:
        with open(p, "r", encoding="utf-8") as f:
            raw = json.load(f)
        items = raw if isinstance(raw, list) else raw.get("events", [])
        for e in items:
            if isinstance(e, dict):
                e = dict(e)
                e.setdefault("source_file", p)
                events.append(e)
    return events


def normalize_all(events):
    norm, errors = [], []
    for i, e in enumerate(events):
        try:
            n = normalize_any(e)
            n.setdefault("camera", "CAM-?")
            n.setdefault("event", n.get("label", "event"))
            norm.append(n)
        except (ValueError, TypeError, OSError, OverflowError) as exc:
            errors.append({"index": i, "error": str(exc), "event": e})
    norm.sort(key=lambda x: x.get("epoch_utc") or 0)
    return norm, errors


def correlate(events, window=10.0):
    pairs = []
    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            a, b = events[i], events[j]
            ta = a.get("epoch_utc")
            tb = b.get("epoch_utc")
            if ta is None or tb is None or a.get("camera") == b.get("camera"):
                continue
            delta = abs(ta - tb)
            if delta <= window:
                pairs.append({
                    "delta_seconds": round(delta, 3),
                    "a": {"camera": a.get("camera"), "event": a.get("event"),
                          "utc": a.get("utc")},
                    "b": {"camera": b.get("camera"), "event": b.get("event"),
                          "utc": b.get("utc")},
                })
    # union-find over pair edges -> subject tracks
    parent = list(range(len(events)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[rx] = ry

    for i in range(len(events)):
        for j in range(i + 1, len(events)):
            a, b = events[i], events[j]
            ta, tb = a.get("epoch_utc"), b.get("epoch_utc")
            if ta is None or tb is None or a.get("camera") == b.get("camera"):
                continue
            if abs(ta - tb) <= window:
                union(i, j)

    tracks = {}
    for i, e in enumerate(events):
        tracks.setdefault(find(i), []).append(e)
    track_list = []
    for members in tracks.values():
        cams = sorted({m.get("camera", "?") for m in members})
        if len(cams) < 2:
            continue  # single-camera clusters are not "correlations"
        times = [m.get("epoch_utc") for m in members if m.get("epoch_utc") is not None]
        track_list.append({
            "cameras": cams,
            "event_count": len(members),
            "span_seconds": round(max(times) - min(times), 3) if times else 0,
            "events": [{"camera": m.get("camera"), "event": m.get("event"),
                        "utc": m.get("utc"), "ist": m.get("ist"),
                        "confidence": m.get("confidence")} for m in members],
        })
    track_list.sort(key=lambda t: -t["event_count"])
    return pairs, track_list


def run(inputs, window=10.0, out_path=None):
    events, errors = normalize_all(load_events(inputs))
    pairs, tracks = correlate(events, window)
    result = {
        "ok": True,
        "window_seconds": window,
        "event_count": len(events),
        "parse_errors": errors,
        "events": [{"utc": e.get("utc"), "ist": e.get("ist"),
                    "epoch_utc": e.get("epoch_utc"),
                    "camera": e.get("camera"), "event": e.get("event"),
                    "confidence": e.get("confidence"),
                    "source_file": e.get("source_file")} for e in events],
        "correlated_pairs": pairs,
        "correlation_count": len(pairs),
        "tracks": tracks,
    }
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2)
        result["out"] = out_path
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA multi-camera correlation")
    ap.add_argument("--inputs", nargs="+", required=True,
                    help="timeline / AI-events JSON files")
    ap.add_argument("--window", type=float, default=10.0,
                    help="± correlation window in seconds (default 10)")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    try:
        r = run(args.inputs, args.window, args.out)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(r, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())