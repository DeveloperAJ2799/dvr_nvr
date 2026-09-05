#!/usr/bin/env python3
"""
core/device_detect.py - Magic-byte vendor detector for NYAYA Forensics.

Reads the first 4 KiB of a file to identify the vendor signature, then
deep-scans up to 8 MiB to COMPUTE an evidence-based confidence:
frame-based formats (DHAV/HKVI/H.264) repeat their frame marker for every
frame, so the occurrence count in the window scales the confidence; a
single match at offset 0 could be coincidence and scores low. E01 files
are validated against the full 8-byte EWF signature. Does NOT
re-implement any vendor parser.

Usage:
  python core/device_detect.py --file sample.dd
  python core/device_detect.py --folder exported_dvr/
"""

import argparse
import json
import os
import sys

CHUNK = 4096                       # quick header probe
SCAN_WINDOW = 8 * 1024 * 1024      # deep-scan window (8 MiB) for evidence-based confidence

SIGNATURES = [
    {
        "vendor": "Dahua",
        "vendor_id": "dahua",
        "magic": b"DHAV",
        "full_magic": None,
        "offset": 0,
        "frame_based": True,
        "singleton_confidence": 0.55,
        "note": "DHAV per-frame framing; FFmpeg has a native dhav demuxer (>=4.2)",
    },
    {
        "vendor": "Hikvision",
        "vendor_id": "hikvision",
        "magic": b"HKVI",
        "full_magic": None,
        "offset": 0,
        "frame_based": True,
        "singleton_confidence": 0.55,
        "note": "Custom Hikvision frame header; exported clips are MPEG-PS containers",
    },
    {
        "vendor": "Uniview",
        "vendor_id": "uniview",
        "magic": b"WFS\x00",
        "full_magic": None,
        "offset": 0,
        "frame_based": False,
        "singleton_confidence": 0.85,
        "note": "Uniview WFS 0.4 file system",
    },
    {
        "vendor": "E01 (Expert Witness)",
        "vendor_id": "e01",
        "magic": b"EVTF",
        "full_magic": b"EVTF\x09\x0d\x0a\xff\x00",
        "offset": 0,
        "frame_based": False,
        "singleton_confidence": 0.70,
        "note": "EWF-E01 segment header; read via libewf-python",
    },
    {
        "vendor": "Generic H.264",
        "vendor_id": "h264_raw",
        "magic": b"\x00\x00\x00\x01",
        "full_magic": None,
        "offset": 0,
        "frame_based": True,
        "singleton_confidence": 0.50,
        "note": "Starts with Annex-B NAL unit start prefix; treat as raw H.264",
    },
]

# Evidence-based confidence: how many magic occurrences in the deep-scan
# window justify which confidence level (frame-based formats).
_REPEAT_CONFIDENCE = [
    (100, 0.98),
    (50, 0.96),
    (20, 0.93),
    (10, 0.90),
    (5, 0.85),
    (2, 0.75),
]


def _read_head(path):
    try:
        with open(path, "rb") as fh:
            return fh.read(CHUNK)
    except OSError as exc:
        return {"__error__": str(exc)}


def _match(head):
    if isinstance(head, dict) and "__error__" in head:
        return None
    best = None
    for sig in SIGNATURES:
        window = head[sig["offset"]:sig["offset"] + len(sig["magic"])]
        if window == sig["magic"]:
            if best is None or _base_confidence(sig) > _base_confidence(best):
                best = sig
    return best


def _read_window(path):
    """Read up to SCAN_WINDOW bytes for the deep-scan evidence check."""
    try:
        with open(path, "rb") as fh:
            return fh.read(SCAN_WINDOW)
    except OSError:
        return None


def _base_confidence(sig):
    """Confidence floor for a signature match before repetition evidence."""
    return sig.get("singleton_confidence", 0.55)


def _confidence_for(sig, head, occurrences):
    """Compute evidence-based confidence instead of a fixed value.

    - E01: the EWF header is a fixed 8-byte signature; matching all 8 bytes
      is near-certain evidence, matching only "EVTF" is weaker.
    - Frame-based formats (DHAV/HKVI/Annex-B H.264): real streams repeat the
      frame marker for every frame, so the occurrence count in the scanned
      window scales the confidence. A single occurrence at offset 0 could
      be coincidence and scores low.
    - Non-frame-based filesystem signatures (WFS) score on the exact
      magic match alone.
    """
    if sig["vendor_id"] == "e01":
        full = sig["full_magic"]
        if full and head[:len(full)] == full:
            return 0.99
        return 0.70
    if occurrences >= 2:
        for n, conf in _REPEAT_CONFIDENCE:
            if occurrences >= n:
                return conf
    return _base_confidence(sig)


def detect_file(path):
    head = _read_head(path)
    sig = _match(head)
    if sig is None:
        return {
            "path": path,
            "vendor": "Unknown",
            "vendor_id": "unknown",
            "confidence": 0.0,
            "hex_head": head[:16].hex() if isinstance(head, bytes) else None,
            "error": None,
        }

    # Gather real evidence instead of printing a hardcoded percentage:
    # deep-scan the leading window and count signature occurrences.
    window = _read_window(path) or head
    scanned = len(window)
    occurrences = window.count(sig["magic"])
    confidence = _confidence_for(sig, head, occurrences)

    return {
        "path": path,
        "vendor": sig["vendor"],
        "vendor_id": sig["vendor_id"],
        "confidence": confidence,
        "hex_head": head[:16].hex(),
        "note": sig["note"],
        "evidence": {
            "occurrences": occurrences,
            "scanned_bytes": scanned,
            "frame_based": sig["frame_based"],
            "method": "signature_repetition_scan" if sig["frame_based"] else "signature_match",
        },
        "error": None,
    }


def detect_folder(folder):
    results = []
    for root, _dirs, files in os.walk(folder):
        for name in sorted(files):
            p = os.path.join(root, name)
            try:
                if os.path.getsize(p) < 16:
                    continue
            except OSError:
                continue
            r = detect_file(p)
            if r["vendor"] != "Unknown":
                results.append(r)
                break
        else:
            continue
        break
    if not results:
        return {
            "path": folder,
            "vendor": "Unknown",
            "vendor_id": "unknown",
            "confidence": 0.0,
            "error": "No recognized signature in first files",
        }
    return results[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA Forensics vendor detector")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--file", help="Single file / disk image to inspect")
    g.add_argument("--folder", help="Folder to scan for a vendor signature")
    args = ap.parse_args(argv)

    if args.file:
        if not os.path.exists(args.file):
            print(json.dumps({"error": "file not found", "path": args.file}))
            return 2
        out = detect_file(args.file)
    else:
        if not os.path.isdir(args.folder):
            print(json.dumps({"error": "folder not found", "path": args.folder}))
            return 2
        out = detect_folder(args.folder)

    print(json.dumps(out, indent=2))
    return 0 if out.get("vendor") != "Unknown" else 1


if __name__ == "__main__":
    sys.exit(main())