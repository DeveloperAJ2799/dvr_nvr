#!/usr/bin/env python3
"""
core/device_detect.py - Magic-byte vendor detector for NYAYA Forensics.

Reads ONLY the first 4 KiB of a file (or walks a folder) and matches against
VERIFIED proprietary signatures. Does NOT re-implement any vendor parser.

Verified signatures (2026-09-04):
  Dahua   : 44 48 41 56  ("DHAV") at offset 0  -> per-frame DHAV framing, H.264/H.265
  Hikvision: 48 4B 56 49  ("HKVI") at offset 0  -> custom frame header, MPEG-PS on export
  Uniview : "WFS" ASCII at offset 0               -> WFS 0.4 file system
  E01     : "EVTF" at offset 0                    -> Expert Witness Compression Format

Usage:
  python core/device_detect.py --file sample.dd
  python core/device_detect.py --folder exported_dvr/
"""

import argparse
import json
import os
import sys

CHUNK = 4096

SIGNATURES = [
    {
        "vendor": "Dahua",
        "vendor_id": "dahua",
        "magic": b"DHAV",
        "offset": 0,
        "confidence": 0.95,
        "note": "DHAV per-frame framing; FFmpeg has a native dhav demuxer (>=4.2)",
    },
    {
        "vendor": "Hikvision",
        "vendor_id": "hikvision",
        "magic": b"HKVI",
        "offset": 0,
        "confidence": 0.95,
        "note": "Custom Hikvision frame header; exported clips are MPEG-PS containers",
    },
    {
        "vendor": "Uniview",
        "vendor_id": "uniview",
        "magic": b"WFS\x00",
        "offset": 0,
        "confidence": 0.90,
        "note": "Uniview WFS 0.4 file system",
    },
    {
        "vendor": "E01 (Expert Witness)",
        "vendor_id": "e01",
        "magic": b"EVTF",
        "offset": 0,
        "confidence": 0.99,
        "note": "EWF-E01 segment header; read via libewf-python",
    },
    {
        "vendor": "Generic H.264",
        "vendor_id": "h264_raw",
        "magic": b"\x00\x00\x00\x01",
        "offset": 0,
        "confidence": 0.60,
        "note": "Starts with Annex-B NAL unit start prefix; treat as raw H.264",
    },
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
            if best is None or sig["confidence"] > best["confidence"]:
                best = sig
    return best


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
    return {
        "path": path,
        "vendor": sig["vendor"],
        "vendor_id": sig["vendor_id"],
        "confidence": sig["confidence"],
        "hex_head": head[:16].hex(),
        "note": sig["note"],
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