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

# Priority order matters: most specific marker wins (first hit returned).
SIGNATURES = [
    ("dahua",     b"DHFS",      "DHFS proprietary file system", "dav"),
    ("cp_plus",   b"CPPLUS",    "CP Plus (Dahua OEM)",          "dav"),
    ("hikvision", b"HIKVISION", "HIKFS proprietary file system","mp4/hik"),
    ("godrej",    b"GODREJ",    "Godrej (Hikvision OEM)",       "mp4"),
    ("matrix",    b"MATRIX",    "Matrix (Hikvision OEM)",       "mp4"),
    ("uniview",   b"UNIVIEW",   "UFS proprietary file system",  "ps/mp4"),
    ("tplink",    b"TP-LINK",   "TP-Link VIGI / NVR series",    "mp4/h264"),
    ("wfs",       b"WFS",       "WFS",                          "h264"),
    ("ufs",       b"UFS",       "UFS",                          "ps"),
]

DISPLAY = {
    "dahua": "Dahua Technology", "cp_plus": "CP Plus (Dahua OEM)",
    "hikvision": "HIKVISION", "godrej": "Godrej (Hikvision OEM)",
    "matrix": "Matrix (Hikvision OEM)", "uniview": "Uniview / UNV",
    "tplink": "TP-Link", "wfs": "WFS vendor", "ufs": "UFS vendor",
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
    buf = read_region(path, max_bytes)
    hits = []
    for vendor, magic, desc, fmt in SIGNATURES:
        off = buf.find(magic)
        if off != -1:
            hits.append({"vendor": vendor, "magic": magic.decode("latin1"),
                         "offset": off, "file_system": desc, "video_format": fmt})
    if hits:
        best = hits[0]
        return {
            "ok": True,
            "vendor": best["vendor"],
            "vendor_display": DISPLAY[best["vendor"]],
            "file_system": best["file_system"],
            "video_format": best["video_format"],
            "matched_magic": best["magic"],
            "magic_offset": best["offset"],
            "first_bytes_hex": buf[:16].hex(" "),
            "all_hits": hits,
            "note": "Verify the candidate mark against the acquisition writeup in the case ledger.",
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