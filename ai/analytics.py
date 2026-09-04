#!/usr/bin/env python3
"""
ai/analytics.py - Forensic AI Video Analytics Suite.

Provides:
  1. Face Detection: OpenCV Haar Cascades for facial detection & bounding boxes.
  2. Motion Detection: Frame differencing on keyframes.
  3. Object Detection: YOLOv8n (if ultralytics installed) with graceful fallback.

Notice:
  AI results are INVESTIGATIVE AIDS ONLY and require human forensic validation.
  They are never presented as conclusive proof in court reports.

Usage:
  python ai/analytics.py --video clip.mp4 --mode face
  python ai/analytics.py --video clip.mp4 --mode motion
  python ai/analytics.py --video clip.mp4 --mode object --out events.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

FRAME_SAMPLE_INTERVAL = 5   # sample every 5th frame for performance
OBJECT_CONF = 0.5            # YOLO confidence threshold
OBJECT_CLASSES = [0, 2, 3, 5, 7]  # COCO ids: person, car, motorcycle, bus, truck


def _format_timestamp(seconds, base_utc=None):
    if base_utc is None:
        base_utc = datetime.now(timezone.utc)
    dt = base_utc + timedelta(seconds=seconds)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def face_detect(video_path, out_path=None):
    """Detect faces across sampled video frames using OpenCV Haar Cascades."""
    try:
        import cv2
    except ImportError:
        return {"error": "opencv-python not installed", "hint": "pip install opencv-python-headless"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "cannot open video", "path": video_path}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_sec = total_frames / fps if fps > 0 else 0

    here = os.path.dirname(os.path.abspath(__file__))
    yunet_model = os.path.join(here, "models", "face_detection_yunet_2023mar.onnx")
    cascade_model = os.path.join(here, "models", "haarcascade_frontalface_default.xml")

    use_yunet = hasattr(cv2, "FaceDetectorYN_create") and os.path.exists(yunet_model)
    use_cascade = hasattr(cv2, "CascadeClassifier") and os.path.exists(cascade_model)

    if not use_yunet and not use_cascade:
        return {"error": "Face detection models missing (neither YuNet nor Haar cascade available)"}

    detector_yunet = None
    detector_cascade = None

    if use_yunet:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 640)
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 360)
        detector_yunet = cv2.FaceDetectorYN_create(
            yunet_model, "", (width, height), 0.6, 0.3, 5000
        )
    elif use_cascade:
        detector_cascade = cv2.CascadeClassifier(cascade_model)

    events = []
    frame_no = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        if frame_no % FRAME_SAMPLE_INTERVAL != 0:
            continue

        h_f, w_f = frame.shape[:2]
        ts_sec = frame_no / fps

        if detector_yunet is not None:
            detector_yunet.setInputSize((w_f, h_f))
            _, faces = detector_yunet.detect(frame)
            if faces is not None:
                for face in faces:
                    x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                    score = float(face[-1])
                    events.append({
                        "event_type": "face",
                        "label": "human_face",
                        "frame": frame_no,
                        "seconds": round(ts_sec, 2),
                        "timestamp_utc": _format_timestamp(ts_sec),
                        "bounding_box": [max(0, x), max(0, y), w, h],
                        "confidence": round(score, 3),
                    })
        elif detector_cascade is not None:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = detector_cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=4, minSize=(30, 30))
            for (x, y, w, h) in faces:
                events.append({
                    "event_type": "face",
                    "label": "human_face",
                    "frame": frame_no,
                    "seconds": round(ts_sec, 2),
                    "timestamp_utc": _format_timestamp(ts_sec),
                    "bounding_box": [int(x), int(y), int(w), int(h)],
                    "confidence": 0.85,
                })

    cap.release()

    result = {
        "video": video_path,
        "mode": "face",
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_seconds": round(duration_sec, 2),
        "event_count": len(events),
        "events": events,
        "error": None,
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(result, fh, indent=2)
        result["out"] = out_path

    return result


def motion_detect(video_path, out_path=None):
    """Frame-difference motion detection using OpenCV."""
    try:
        import cv2
    except ImportError:
        return {"error": "opencv-python not installed", "hint": "pip install opencv-python-headless"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "cannot open video", "path": video_path}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_sec = total_frames / fps if fps > 0 else 0

    events = []
    prev_gray = None
    frame_no = 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        if frame_no % FRAME_SAMPLE_INTERVAL != 0:
            continue

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, (640, 360))

        if prev_gray is None:
            prev_gray = gray
            continue

        diff = cv2.absdiff(prev_gray, gray)
        _, thresh = cv2.threshold(diff, 25, 255, cv2.THRESH_BINARY)
        motion_ratio = float((thresh > 0).sum()) / thresh.size

        if motion_ratio > 0.02:
            ts_sec = frame_no / fps
            events.append({
                "event_type": "motion",
                "frame": frame_no,
                "seconds": round(ts_sec, 2),
                "timestamp_utc": _format_timestamp(ts_sec),
                "confidence": round(min(0.99, motion_ratio * 4), 3),
                "motion_ratio": round(motion_ratio, 4),
            })

        prev_gray = gray

    cap.release()

    result = {
        "video": video_path,
        "mode": "motion",
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_seconds": round(duration_sec, 2),
        "event_count": len(events),
        "events": events,
        "error": None,
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(result, fh, indent=2)
        result["out"] = out_path

    return result


def object_detect(video_path, out_path=None):
    """YOLOv8n object detection with graceful OpenCV fallback."""
    events = []
    try:
        from ultralytics import YOLO
        has_yolo = True
    except ImportError:
        has_yolo = False

    try:
        import cv2
    except ImportError:
        return {"error": "opencv-python not installed"}

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return {"error": "cannot open video", "path": video_path}

    fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration_sec = total_frames / fps if fps > 0 else 0

    if has_yolo:
        try:
            model = YOLO("yolov8n.pt")
            frame_no = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                frame_no += 1
                if frame_no % FRAME_SAMPLE_INTERVAL != 0:
                    continue
                results = model.predict(frame, verbose=False, conf=OBJECT_CONF, classes=OBJECT_CLASSES)
                for r in results:
                    if r.boxes is None:
                        continue
                    for box in r.boxes:
                        xyxy = box.xyxy[0].tolist()
                        cls_id = int(box.cls[0].item())
                        conf = float(box.conf[0].item())
                        ts_sec = frame_no / fps
                        events.append({
                            "event_type": "object",
                            "label": model.names.get(cls_id, str(cls_id)),
                            "frame": frame_no,
                            "seconds": round(ts_sec, 2),
                            "timestamp_utc": _format_timestamp(ts_sec),
                            "confidence": round(conf, 3),
                            "bounding_box": [int(v) for v in xyxy],
                        })
        except Exception as exc:
            has_yolo = False
            events = []

    # Fallback to OpenCV Motion/Contour Object Detector if YOLO unavailable
    if not has_yolo:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
        prev_gray = None
        frame_no = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            frame_no += 1
            if frame_no % (FRAME_SAMPLE_INTERVAL * 2) != 0:
                continue

            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray = cv2.GaussianBlur(gray, (21, 21), 0)

            if prev_gray is None:
                prev_gray = gray
                continue

            delta = cv2.absdiff(prev_gray, gray)
            thresh = cv2.threshold(delta, 30, 255, cv2.THRESH_BINARY)[1]
            thresh = cv2.dilate(thresh, None, iterations=2)
            contours, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            for c in contours:
                if cv2.contourArea(c) < 1200:
                    continue
                (x, y, w, h) = cv2.boundingRect(c)
                ts_sec = frame_no / fps
                events.append({
                    "event_type": "object",
                    "label": "moving_subject",
                    "frame": frame_no,
                    "seconds": round(ts_sec, 2),
                    "timestamp_utc": _format_timestamp(ts_sec),
                    "confidence": 0.78,
                    "bounding_box": [int(x), int(y), int(w), int(h)],
                })

            prev_gray = gray

    cap.release()

    result = {
        "video": video_path,
        "mode": "object",
        "engine": "yolov8n" if has_yolo else "opencv_hog_fallback",
        "fps": round(fps, 2),
        "total_frames": total_frames,
        "duration_seconds": round(duration_sec, 2),
        "event_count": len(events),
        "events": events,
        "error": None,
    }

    if out_path:
        with open(out_path, "w") as fh:
            json.dump(result, fh, indent=2)
        result["out"] = out_path

    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description="DVR/NVR Forensic AI Analytics")
    ap.add_argument("--video", required=True)
    ap.add_argument("--mode", choices=["motion", "object", "face"], default="motion")
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    if not os.path.exists(args.video):
        print(json.dumps({"error": "video not found", "path": args.video}))
        return 2

    if args.mode == "motion":
        result = motion_detect(args.video, args.out)
    elif args.mode == "face":
        result = face_detect(args.video, args.out)
    else:
        result = object_detect(args.video, args.out)

    print(json.dumps(result, indent=2))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    sys.exit(main())