#!/usr/bin/env python3
"""
NYAYA Forensics - plugins/dahua_wrapper.py
Dahua DHFS/DHAV plugin (P2). Two-tier adapter, both NON-INTERACTIVE:

  1. Preferred: invoke the existing open-source parser
     drcrecoverydata/dvr_dahua via subprocess - we never re-implement DHFS
     decoding. Located at $DAHUA_PARSER_SCRIPT or
     ./vendor/dvr_dahua/Python_3.12.3_Dahua_23.4.24.py
  2. Built-in fallback (no external repo needed): scan the image for DHAV
     frame-sync magics ("DHAV" ... "dhav"), carve each contiguous frame run
     (byte-gap <= 8 MB), and remux every run to MP4 with FFmpeg's native
     `dhav` demuxer. This recovers playable video directly from raw DHAV
     images/clips without any third-party script.

The wrapper returns a manifest of extracted files for the case ledger.

Usage:
  python plugins/dahua_wrapper.py <image.dd> --outdir <dir> [--no-ffmpeg]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

SCRIPT_NAME = "Python_3.12.3_Dahua_23.4.24.py"
REPO = "https://github.com/drcrecoverydata/dvr_dahua"
DHAV_MAGIC = b"DHAV"
RUN_GAP = 8 * 1024 * 1024   # max byte gap between frames of one run
CHUNK = 4 * 1024 * 1024


def locate_script():
    env = os.environ.get("DAHUA_PARSER_SCRIPT")
    if env and os.path.exists(env):
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(root, "vendor", "dvr_dahua", SCRIPT_NAME)
    return cand if os.path.exists(cand) else None


def _scan_magic(path, magic, chunk=CHUNK):
    offsets, carry, pos = [], b"", 0
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            data = carry + buf
            base = pos - len(carry)
            i = data.find(magic)
            while i != -1:
                offsets.append(base + i)
                i = data.find(magic, i + 1)
            carry = data[-(len(magic) - 1):]
            pos += len(buf)
    return offsets


def _copy_range(image, start, end, dst):
    with open(image, "rb") as fin, open(dst, "wb") as fout:
        fin.seek(start)
        remaining = end - start
        while remaining > 0:
            buf = fin.read(min(CHUNK, remaining))
            if not buf:
                break
            fout.write(buf)
            remaining -= len(buf)


def _remux_dhav(src, dst):
    """Remux a carved DHAV run using FFmpeg's native dhav demuxer."""
    if not shutil.which("ffmpeg"):
        return None
    r = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "dhav", "-i", src,
         "-c", "copy", dst],
        capture_output=True, text=True)
    return dst if r.returncode == 0 and os.path.exists(dst) else None


def native_dhav_extract(image, outdir):
    """Fallback adapter: carve DHAV frame runs and remux each to MP4."""
    os.makedirs(outdir, exist_ok=True)
    offs = _scan_magic(image, DHAV_MAGIC)
    if not offs:
        # Fallback to elementary stream decoder
        try:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from core.decoder import decode
            dec_out = os.path.join(outdir, "extracted_stream.mp4")
            res = decode(image, header_bytes=32, out_mp4=dec_out)
            if res.get("ok"):
                return {
                    "ok": True,
                    "method": "stream-decoder-fallback",
                    "extracted_files": [{
                        "path": dec_out,
                        "size_bytes": res.get("size_bytes", 0),
                        "relative": os.path.basename(dec_out),
                        "format": "mp4"
                    }],
                    "extracted_count": 1
                }
        except Exception:
            pass
        return {"ok": False, "method": "native-dhav",
                "error": "no DHAV frame magic found in image"}
    groups = [[offs[0]]]
    for o in offs[1:]:
        if o - groups[-1][-1] <= RUN_GAP:
            groups[-1].append(o)
        else:
            groups.append([o])
    size = os.path.getsize(image)
    files = []
    for gi, g in enumerate(groups):
        start = g[0]
        end = min(size, g[-1] + RUN_GAP)
        raw = os.path.join(outdir, "dhav_run_%03d.raw" % gi)
        _copy_range(image, start, end, raw)
        mp4 = _remux_dhav(raw, os.path.splitext(raw)[0] + ".mp4")
        files.append({"path": mp4 or raw,
                      "size_bytes": os.path.getsize(mp4 or raw),
                      "relative": os.path.basename(mp4 or raw),
                      "frame_magic_count": len(g),
                      "start_offset": start, "end_offset": end,
                      "format": "mp4" if mp4 else "raw-dhav"})
    return {"ok": True, "method": "native-dhav-ffmpeg",
            "extracted_files": files, "extracted_count": len(files)}


def run(image, outdir):
    script = locate_script()
    if script is None:
        # Non-interactive built-in fallback - never fails the pipeline.
        try:
            return native_dhav_extract(image, outdir)
        except OSError as exc:
            return {"ok": False, "error": "native DHAV extraction failed: %s" % exc}
    os.makedirs(outdir, exist_ok=True)
    cmd = [sys.executable, script, image, "--output", outdir]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=7200)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "dahua parser timed out (2h limit)"}

    files = []
    for root, _, names in os.walk(outdir):
        for nm in names:
            p = os.path.join(root, nm)
            files.append({"path": p,
                          "size_bytes": os.path.getsize(p),
                          "relative": os.path.relpath(p, outdir)})
    return {"ok": r.returncode == 0, "script": script,
            "command": " ".join(cmd), "returncode": r.returncode,
            "stderr_tail": r.stderr[-1200:],
            "extracted_files": files, "extracted_count": len(files)}


def main():
    ap = argparse.ArgumentParser(description="Dahua DHFS/DHAV adapter")
    ap.add_argument("image", help="Path to acquired DHFS/DHAV image (.dd/.dav)")
    ap.add_argument("--outdir", default="./extracted", help="Extraction folder")
    args = ap.parse_args()
    print(json.dumps(run(args.image, args.outdir), indent=2))


if __name__ == "__main__":
    main()