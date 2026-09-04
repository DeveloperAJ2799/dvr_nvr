#!/usr/bin/env python3
"""
NYAYA Forensics - ai/detector.py
AI analytics worker (P5): runs Ultralytics YOLOv8n (capped 2 FPS, imgsz 640,
conf 0.5) OR an OpenCV-only fallback over an extracted MP4 and emits a JSON
event list {timestamp, label, bbox, confidence}. `--mode face` adds person
face detection with the bundled YuNet ONNX model (Haar cascade fallback).

Notice: AI output is an investigative aid ONLY - it is never conclusive
proof and must be examiner-verified before court submission (report §7).
Fails gracefully when heavy deps are absent so the desktop app still works.

Usage:
  python ai/detector.py <video.mp4> [--mode objects|face] [--fps 2]
      [--conf 0.5] [--imgsz 640] [--events events.json]
"""
import argparse
import json
import os
import sys

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
YUNET_PATH = os.path.join(MODELS_DIR, "face_detection_yunet_2023mar.onnx")
HAAR_PATH = os.path.join(MODELS_DIR, "haarcascade_frontalface_default.xml")


def load_optional():
    """Return (cv2, YOLO); YOLO is None when ultralytics is unavailable."""
    try:
        import cv2
    except Exception:
        return None, None
    try:
        from ultralytics import YOLO
        return cv2, YOLO
    except Exception:
        return cv2, None


def _save(events, events_path, result):
    if events_path:
        with open(events_path, "w") as f:
            json.dump(events, f, indent=2)
        result["events_file"] = events_path
    return result


def object_detect(video, fps=2.0, conf=0.5, imgsz=640, events_path=None):
    """Person/vehicle detection: YOLOv8n when available, else MOG2 fallback."""
    if not os.path.exists(video):
        return {"ok": False, "error": "video not found: %s" % video}
    cv2, YOLO = load_optional()
    if cv2 is None:
        return {"ok": False, "error": "opencv-python not installed"}

    cap = cv2.VideoCapture(video)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(video_fps / fps)))
    events, frame_idx, analyzed = [], 0, 0

    if YOLO is not None:
        engine = "yolov8n"
        model = YOLO("yolov8n.pt")  # auto-downloads once, cached locally
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
    else:
        # OpenCV-only fallback: MOG2 background subtraction at the same cap.
        engine = "opencv_mog2_fallback"
        sub = cv2.createBackgroundSubtractorMOG2(history=4, varThreshold=25)
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if frame_idx % step == 0:
                analyzed += 1
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                gray = cv2.GaussianBlur(gray, (21, 21), 0)
                fg = sub.apply(gray)
                thresh = cv2.threshold(fg, 200, 255, cv2.THRESH_BINARY)[1]
                thresh = cv2.dilate(thresh, None, iterations=2)
                contours, _ = cv2.findContours(
                    thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                for c in contours:
                    if cv2.contourArea(c) < 1200:
                        continue
                    x, y, w, h = cv2.boundingRect(c)
                    events.append({
                        "timestamp": round(frame_idx / video_fps, 2),
                        "label": "motion-object",
                        "bbox": [int(x), int(y), int(x + w), int(y + h)],
                        "confidence": 0.78,
                    })
            frame_idx += 1
    cap.release()

    result = {"ok": True, "video": video, "mode": "objects", "engine": engine,
              "analyzed_fps": fps, "confidence_threshold": conf,
              "frame_count_analyzed": analyzed,
              "event_count": len(events), "events": events}
    return _save(events, events_path, result)


def face_detect(video, fps=2.0, conf=0.6, events_path=None):
    """Face detection with the bundled YuNet ONNX model (no heavy deps)."""
    if not os.path.exists(video):
        return {"ok": False, "error": "video not found: %s" % video}
    cv2, _ = load_optional()
    if cv2 is None:
        return {"ok": False, "error": "opencv-python not installed"}
    if not hasattr(cv2, "FaceDetectorYN_create") or not os.path.exists(YUNET_PATH):
        return {"ok": False,
                "error": "YuNet face model missing (opencv without "
                         "FaceDetectorYN or onnx file absent)",
                "expected": YUNET_PATH}

    cap = cv2.VideoCapture(video)
    video_fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    step = max(1, int(round(video_fps / fps)))
    detector = cv2.FaceDetectorYN_create(YUNET_PATH, "", (320, 240),
                                         conf, 0.3, 5000)
    events, frame_idx, analyzed = [], 0, 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % step == 0:
            analyzed += 1
            h, w = frame.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
            for face in (faces if faces is not None else []):
                x, y, fw, fh = [int(v) for v in face[:4]]
                events.append({
                    "timestamp": round(frame_idx / video_fps, 2),
                    "label": "face",
                    "bbox": [x, y, x + fw, y + fh],
                    "confidence": round(float(face[-1]), 3),
                })
        frame_idx += 1
    cap.release()

    result = {"ok": True, "video": video, "mode": "face", "engine": "yunet-onnx",
              "analyzed_fps": fps, "confidence_threshold": conf,
              "frame_count_analyzed": analyzed,
              "event_count": len(events), "events": events}
    return _save(events, events_path, result)


def run(video, fps=2.0, conf=0.5, imgsz=640, events_path=None):
    """Backward-compatible alias (default object mode)."""
    return object_detect(video, fps, conf, imgsz, events_path)


def main():
    ap = argparse.ArgumentParser(description="NYAYA AI analytics (objects/face)")
    ap.add_argument("video", help="Extracted MP4")
    ap.add_argument("--mode", choices=["objects", "face"], default="objects")
    ap.add_argument("--fps", type=float, default=2.0)
    ap.add_argument("--conf", type=float, default=0.5)
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--events", default=None, help="Save events JSON here")
    args = ap.parse_args()
    if args.mode == "face":
        r = face_detect(args.video, args.fps, max(args.conf, 0.6), args.events)
    else:
        r = object_detect(args.video, args.fps, args.conf, args.imgsz,
                          args.events)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("ok") else 1)


if __name__ == "__main__":
    main()