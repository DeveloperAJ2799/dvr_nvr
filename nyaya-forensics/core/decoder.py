#!/usr/bin/env python3
"""
NYAYA Forensics - core/decoder.py
Decoder / stream extractor (P4): strips the proprietary container header
(Dahua .dav = 32 bytes, Hikvision .hik = 48 bytes; both configurable) to
expose the raw H.264 element, then remuxes to MP4 with FFmpeg using a
STREAM COPY (no re-encode = evidence-safe).

Usage:
  python core/decoder.py <input> [--output out.mp4] [--header-bytes 32]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

DEFAULT_HEADER = 32  # bytes; pass 48 for .hik-family, 0 for raw images
CHUNK = 4 * 1024 * 1024


def strip_header(src, header_bytes, dst):
    """Remove the proprietary vendor header, keep the rest byte-exact."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        fin.seek(header_bytes)
        while True:
            buf = fin.read(CHUNK)
            if not buf:
                break
            fout.write(buf)


def run_ffmpeg(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def decode(src, header_bytes=DEFAULT_HEADER, out_mp4=None, cleanup=False):
    if not os.path.exists(src):
        return {"ok": False, "error": "input not found: %s" % src}
    if not shutil.which("ffmpeg"):
        return {"ok": False, "error": "ffmpeg is not on PATH"}

    fd, raw = tempfile.mkstemp(suffix=".h264", prefix="nyaya_")
    os.close(fd)
    try:
        strip_header(src, header_bytes, raw)
        if out_mp4 is None:
            out_mp4 = os.path.splitext(src)[0] + "_decoded.mp4"

        # Primary: declare elementary h264, stream-copy to mp4 (no re-encode).
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "h264",
               "-i", raw, "-c:v", "copy", out_mp4]
        r = run_ffmpeg(cmd)
        if r.returncode != 0:
            # Fallback: let ffmpeg probe (some vendor streams lack in-band SPS).
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-i", raw, "-c:v", "copy", out_mp4]
            r = run_ffmpeg(cmd)
        if r.returncode != 0:
            # Fallback 2: FFmpeg ships native demuxers for several vendor
            # containers (e.g. Dahua DHAV since 4.3) - reuse them on the
            # untouched original before giving up.
            cmd = ["ffmpeg", "-y", "-loglevel", "error",
                   "-i", src, "-c:v", "copy", out_mp4]
            r = run_ffmpeg(cmd)
        if r.returncode != 0:
            return {"ok": False,
                    "error": "ffmpeg could not remux stream (corrupt or "
                             "missing SPS)", "ffmpeg_stderr": r.stderr[-1500:],
                    "stripped": raw}
        return {"ok": True, "input": src, "header_bytes_removed": header_bytes,
                "raw_h264": raw, "output": out_mp4,
                "size_bytes": os.path.getsize(out_mp4),
                "ffmpeg_cmd": " ".join(cmd)}
    finally:
        # keep raw h264 for later re-parse; delete on request with --cleanup
        if cleanup and os.path.exists(raw):
            os.remove(raw)


def main():
    ap = argparse.ArgumentParser(description="NYAYA decoder (.dav/.h264)")
    ap.add_argument("input", help="Encapsulated vendor video (.dav/.hik/.bin)")
    ap.add_argument("--output", help="Output .mp4 path")
    ap.add_argument("--header-bytes", type=int, default=DEFAULT_HEADER,
                    help="Vendor header size (Dahua 32, Hikvision 48)")
    ap.add_argument("--cleanup", action="store_true",
                    help="Delete the temp stripped .h264 file when done")
    args = ap.parse_args()
    print(json.dumps(
        decode(args.input, args.header_bytes, args.output, args.cleanup),
        indent=2))


if __name__ == "__main__":
    main()