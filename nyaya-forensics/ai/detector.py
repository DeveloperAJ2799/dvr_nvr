#!/usr/bin/env python3
"""
NYAYA Forensics - ai/detector.py
AI analytics worker (P5): runs Ultralytics YOLOv8n at a capped frame rate
(2 FPS, imgsz 640, conf 0.5) over an extracted MP4 and emits a JSON event
list: {timestamp, label, bbox, confidence}. Designed to be called from the
Tauri command layer; fails gracefully when heavy deps are absent so the
desktop app still works.

Usage:
  python ai/detector.py <video.mp4> [--fps 2] [--conf 0.5]
      [--imgsz 640] [--events events.json]
"""
import argparse
import json
import os
import sys


def load_optional():
    """Return (cv2, YOLO) or (None, None); heavy deps are lazy-loaded."""
    try:
        import cv2
    except Exception:
        return None, None
    try:
        from ultralytics import YOLO
        return cv2, YOLO
    except Exception:
        return cv2, None


def run(video, fps=2.0, conf=0.5, imgsz=640, events_path=None):
    if not os.path.exists(video):
        return {"ok": False, "error": "video not found: %s" % video}
    cv2, YOLO = load_optional()
    if cv2 is None:
        return {"ok": False, "error": "opencv-python not installed"}
    if YOLO is None:
        return {"ok": False,
                "error": "ultralytics not installed (pip install -r requirements.txt)"}

    model = YOLO("yolov8n.pt")  # auto-downloads once, cached locally
    cap = cv2.VideoCapture(video)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(video_fps / fps)))

    events, frame_idx, analyzed = [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            analyzed += 1
            ts = round(frame_idx / video_fps, 2)
            res = model(frame, conf=conf, imgsz=imgsz, verbose=False)[0]
            for b in res.boxes:
                cls = int(b.cls[0])
                label = res.names[cls]
                x1, y1, x2, y2 = [round(v, 1) for v in b.xyxy[0].tolist()]
                events.append({
                    "timestamp": ts, "label": label,
                    "bbox": [x1, y1, x2, y2],
                    "confidence": round(float(b.conf[0]), 3),
                })
        frame_idx += 1
    cap.release()

    result = {"ok": True, "video": video, "model": "yolov8n",
              "analyzed_fps": fps, "confidence_threshold": conf,
              "frame_count_analyzed": analyzed,
              "event_count": len(events), "events": events}
    if events_path:
        with open(events_path, "w") as f:
            json.dump(events, f, indent=2)
        result["events_file"] = events_path
    return result


def main():
    ap = argparse.ArgumentParser(description="NYAYA YOLOv8n detector")
    ap.add_argument("video", help="Extracted MP4")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--events", default=None, help="Save events JSON here")
    args = ap.parse_args()
    r = run(args.video, args.fps, args.conf, args.imgsz, args.events)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()