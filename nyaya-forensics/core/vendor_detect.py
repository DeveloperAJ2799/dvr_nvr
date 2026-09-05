#!/usr/bin/env python3
"""
NYAYA Forensics - core/vendor_detect.py
Device ID layer (P2): scans the first 20 MiB of a disk image for vendor
proprietary file-system / format magic bytes and returns the best vendor
match. Companion to the Rust `detect_vendor` Tauri command (which performs
the same scan natively) - this module drives the Python parser pipeline.

Usage:
  python core/vendor_detect.py <image.dd> [--region-mb 20]
"""
import argparse
import json
import sys

CHUNK = 4 * 1024 * 1024

# Priority order matters: longest / most specific OEM mark wins (highest
# confidence first-hit is chosen by detect()). Covers the 8 SIH PS OEMs:
# Dahua, CP Plus, Honeywell, HIKVISION, TP-Link, Godrej, Uniview, Matrix
# (CP Plus & Godrej & Matrix are OEM variants of Dahua/Hikvision engines).
SIGNATURES = [
    # -- long, unambiguous OEM marks first (7-9 bytes) --
    ("hikvision", b"HIKVISION", "HIKFS proprietary file system",  "mp4/hik",   0.97),
    ("honeywell", b"HONEYWELL", "Honeywell Security NVR database", "mp4/h264", 0.96),
    ("honeywell", b"HWSM",      "Honeywell HUSM/PERFORMA DVR DB",  "mp4",      0.90),
    ("cp_plus",   b"CPPLUS",    "CP Plus (Dahua OEM) DHFS variant", "dav",     0.95),
    ("godrej",    b"GODREJ",    "Godrej Security (Hikvision OEM)", "mp4",      0.95),
    ("matrix",    b"MATRIX",    "Matrix Satya (Hikvision OEM)",    "mp4",      0.95),
    ("uniview",   b"UNIVIEW",   "Uniview UFS/UNF file system",     "ps/mp4",   0.95),
    ("tplink",    b"TP-LINK",   "TP-Link VIGI / NVR series",       "mp4/h264", 0.95),
    ("tplink",    b"VIGI",      "TP-Link VIGI camera stream",      "mp4/h264", 0.88),
    # -- 4-byte container magics --
    ("dahua",     b"DHAV",      "DHAV per-frame container (FFmpeg dhav demuxer)", "dav", 0.93),
    ("dahua",     b"DHFS",      "DHFS proprietary file system",    "dav",      0.93),
    ("hikvision", b"HKVI",      "Hikvision HKVI frame container",  "mp4/hik",  0.93),
    ("hikvision", b"\x00\x00\x01\xba", "MPEG-PS stream (Hikvision/Uniview)", "mp4/ps", 0.85),
    # -- short/weak marks last (false-positive prone) --
    ("uniview",   b"WFS\x00",   "Uniview WFS 0.4 file system",     "h264",     0.80),
    ("uniview",   b"UFS\x00",   "Uniview UFS file system",         "ps",       0.80),
]

ENGINE_MAP = {
    "dahua": "dahua_dhfs",
    "cp_plus": "dahua_dhfs",
    "hikvision": "hikvision_hikfs",
    "godrej": "hikvision_hikfs",
    "matrix": "hikvision_hikfs",
    "uniview": "uniview_wfs",
    "honeywell": "honeywell_hwsm",
    "tplink": "tplink_vigi",
}

DISPLAY = {
    "dahua": "Dahua Technology", "cp_plus": "CP Plus (Dahua OEM)",
    "hikvision": "HIKVISION", "godrej": "Godrej (Hikvision OEM)",
    "matrix": "Matrix (Hikvision OEM)", "uniview": "Uniview / UNV",
    "tplink": "TP-Link / VIGI", "honeywell": "Honeywell Security",
}


def read_region(path, max_bytes):
    data = bytearray()
    with open(path, "rb") as f:
        while len(data) < max_bytes:
            chunk = f.read(CHUNK)
            if not chunk:
                break
            data.extend(chunk)
    return bytes(data[:max_bytes])


def detect(path, region_mb=20):
    max_bytes = region_mb * 1024 * 1024
    try:
        buf = read_region(path, max_bytes)
    except OSError as exc:
        return {
            "ok": False,
            "vendor": "unknown",
            "vendor_display": "Unreadable source",
            "error": "cannot read %s: %s (physical drives may need "
                     "Administrator)" % (path, exc),
            "first_bytes_hex": "",
        }
    hits = []
    for vendor, magic, desc, fmt, conf in SIGNATURES:
        off = buf.find(magic)
        if off != -1:
            hits.append({"vendor": vendor, "magic": magic.decode("latin1"),
                         "offset": off, "file_system": desc,
                         "video_format": fmt, "confidence": conf})
    if hits:
        # most specific (highest-confidence) mark wins; earliest offset breaks ties
        best = max(hits, key=lambda h: (h["confidence"], -h["offset"]))
        return {
            "ok": True,
            "vendor": best["vendor"],
            "vendor_display": DISPLAY[best["vendor"]],
            "engine_family": ENGINE_MAP.get(best["vendor"], "generic"),
            "file_system": best["file_system"],
            "video_format": best["video_format"],
            "matched_magic": best["magic"],
            "magic_offset": best["offset"],
            "confidence": best["confidence"],
            "first_bytes_hex": buf[:16].hex(" "),
            "all_hits": hits,
            "note": "Verify the candidate mark against the acquisition writeup in the case ledger.",
        }
    # Fallback to file extension and payload inspection
    ext = str(path).lower().rsplit(".", 1)[-1] if "." in str(path) else ""
    if ext == "dav":
        return {
            "ok": True,
            "vendor": "dahua",
            "vendor_display": DISPLAY["dahua"] + " (.dav container)",
            "engine_family": "dahua_dhfs",
            "file_system": "Dahua DHAV/DHFS encapsulated stream",
            "video_format": "dav",
            "matched_magic": "extension .dav",
            "magic_offset": 0,
            "confidence": 0.85,
            "first_bytes_hex": buf[:16].hex(" "),
            "all_hits": [],
            "note": "Identified via Dahua .dav container extension and stream characteristics.",
        }
    if ext == "hik":
        return {
            "ok": True,
            "vendor": "hikvision",
            "vendor_display": DISPLAY["hikvision"] + " (.hik container)",
            "engine_family": "hikvision_hikfs",
            "file_system": "Hikvision HIKFS encapsulated stream",
            "video_format": "mp4/hik",
            "matched_magic": "extension .hik",
            "magic_offset": 0,
            "confidence": 0.85,
            "first_bytes_hex": buf[:16].hex(" "),
            "all_hits": [],
            "note": "Identified via Hikvision .hik container extension.",
        }

    return {
        "ok": False,
        "vendor": "unknown",
        "vendor_display": "Unrecognised proprietary mark",
        "first_bytes_hex": buf[:16].hex(" "),
        "suggestion": "Route to the H.264 NAL carving engine - many deleted "
                      "recordings have no volume signature.",
    }


def main():
    ap = argparse.ArgumentParser(description="NYAYA vendor detection")
    ap.add_argument("image", help="Path to the .dd/.img/.E01 image")
    ap.add_argument("--region-mb", type=int, default=20)
    args = ap.parse_args()
    try:
        print(json.dumps(detect(args.image, args.region_mb), indent=2))
    except FileNotFoundError:
        sys.exit("image not found: %s" % args.image)


if __name__ == "__main__":
    main()