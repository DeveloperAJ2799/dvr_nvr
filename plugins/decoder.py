#!/usr/bin/env python3
"""
plugins/decoder.py - Forensic proprietary video decoder -> playable MP4 via FFmpeg.

Supports:
  * Dahua .dav / DHAV streams (native FFmpeg DHAV demuxer)
  * Hikvision .hik / MPEG-PS containers
  * Uniview WFS / PS streams
  * Raw H.264 Annex-B streams
  * Generates MD5 + SHA-256 for chain of custody verification.

Usage:
  python plugins/decoder.py --input rec.dav --out extracted/rec.mp4
  python plugins/decoder.py --input rec.mp4 --out extracted/rec.mp4 --no-reencode
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

CHUNK = 1024 * 1024


def _find_ffmpeg():
    for name in ("ffmpeg", "ffmpeg.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _hash_file(path):
    if not os.path.exists(path):
        return "", ""
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            buf = fh.read(CHUNK)
            if not buf:
                break
            md5.update(buf)
            sha256.update(buf)
    return md5.hexdigest(), sha256.hexdigest()


def _run(cmd):
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600, check=False
        )
    except FileNotFoundError:
        return {"error": "ffmpeg binary missing", "cmd": " ".join(cmd), "returncode": -1}
    except subprocess.TimeoutExpired:
        return {"error": "ffmpeg timed out", "cmd": " ".join(cmd), "returncode": -1}
    return {
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-500:],
        "stderr_tail": (proc.stderr or "")[-800:],
        "error": None if proc.returncode == 0 else "ffmpeg failed",
    }


def detect_format(input_path):
    """Inspect the first 512 bytes for proprietary container signatures."""
    try:
        with open(input_path, "rb") as fh:
            head = fh.read(512)
    except OSError:
        return "unknown"

    if head.startswith(b"DHAV"):
        return "dhav"
    if head.startswith(b"HKVI"):
        return "hkvi"
    if head.startswith(b"\x00\x00\x01\xba"):
        return "mpeg_ps"
    if head.startswith(b"WFS"):
        return "wfs"
    if head.startswith(b"\x00\x00\x00\x01") or head.startswith(b"\x00\x00\x01"):
        return "h264_raw"
    return "auto"


def decode(input_path, out_path, strip=0, reencode=True):
    if not os.path.exists(input_path):
        return {"error": "input not found", "path": input_path}
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)

    ffmpeg = _find_ffmpeg()
    if ffmpeg is None:
        return {"error": "ffmpeg not found on PATH", "hint": "Ensure FFmpeg is installed and accessible."}

    in_md5, in_sha256 = _hash_file(input_path)
    fmt = detect_format(input_path)
    work = out_path

    # Step 1: Try format-specific direct copy remux
    cmd_copy = [ffmpeg, "-y"]
    if fmt == "dhav":
        cmd_copy += ["-f", "dhav"]
    cmd_copy += ["-i", input_path, "-c", "copy", work]

    result = _run(cmd_copy)

    # Step 2: If copy failed or user explicitly requested reencode, transcode with x264
    if result.get("returncode") != 0 or reencode:
        cmd_transcode = [ffmpeg, "-y"]
        if fmt == "dhav":
            cmd_transcode += ["-f", "dhav"]
        cmd_transcode += [
            "-i", input_path,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", work,
        ]
        result = _run(cmd_transcode)

    # Step 3: If still failing and strip > 0 was requested, try stripped fallback
    if result.get("returncode") != 0 and strip and strip > 0:
        stripped = out_path + ".raw"
        with open(input_path, "rb") as src, open(stripped, "wb") as dst:
            src.seek(strip)
            shutil.copyfileobj(src, dst, CHUNK)
        cmd_stripped = [
            ffmpeg, "-y", "-i", stripped,
            "-c:v", "libx264", "-preset", "fast", "-crf", "23",
            "-c:a", "aac", work,
        ]
        result = _run(cmd_stripped)
        if os.path.exists(stripped):
            try:
                os.remove(stripped)
            except OSError:
                pass

    out_exists = os.path.exists(work) and os.path.getsize(work) > 0
    out_md5, out_sha256 = _hash_file(work) if out_exists else ("", "")

    return {
        "ok": out_exists,
        "input": input_path,
        "input_md5": in_md5,
        "input_sha256": in_sha256,
        "detected_format": fmt,
        "output": work,
        "output_exists": out_exists,
        "output_size": os.path.getsize(work) if out_exists else 0,
        "output_md5": out_md5,
        "output_sha256": out_sha256,
        "returncode": result.get("returncode", 0 if out_exists else -1),
        "error": None if out_exists else result.get("error", "Failed to produce output MP4"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="DVR/NVR forensic video decoder")
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--strip", type=int, default=0,
                    help="Bytes to skip before payload (fallback)")
    ap.add_argument("--no-reencode", action="store_true",
                    help="Attempt copy remux without re-encoding")
    args = ap.parse_args(argv)

    result = decode(
        args.input, args.out,
        strip=args.strip,
        reencode=not args.no_reencode,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())