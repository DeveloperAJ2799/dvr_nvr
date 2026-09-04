#!/usr/bin/env python3
"""
NYAYA Forensics - core/recovery.py
Deleted-recording carving engine (P3): scans a raw image for H.264/H.265
IDR start codes and groups hits whose byte-gap is below `--join-gap`
(default 2 MB - the space a ~2 s GOP needs at common DVR bitrates; our
byte-domain proxy for the "PTS gap < 2 s" grouping rule). Each group is
extracted as a clip (Python seek/read equivalent of `dd skip/seek`),
extended backwards to include the nearest SPS/PPS/VPS parameter sets
(within 1 MiB) so carved streams decode standalone, then remuxed to MP4
with FFmpeg.

Signatures (H.264 Annex-B / H.265 (HEVC) NAL headers):
  H.264 : IDR slice 65, SPS 67, PPS 68, non-IDR 41
  H.265 : VPS 40, SPS 42, PPS 44, IDR_W_RADL 26, IDR_N_LP 28

Usage:
  python core/recovery.py <image.dd> --workdir ./recovered [--join-gap-mb 2]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

IDR_H264 = b"\x00\x00\x00\x01\x65"     # H.264 IDR (I-frame) NAL
IDR_H265 = (b"\x00\x00\x00\x01\x26",   # H.265 IDR_W_RADL
            b"\x00\x00\x00\x01\x28")   # H.265 IDR_N_LP
NON_IDR = b"\x00\x00\x00\x01\x41"      # H.264 non-IDR slice NAL
PARAM_H264 = (b"\x00\x00\x00\x01\x67", b"\x00\x00\x00\x01\x68")        # SPS, PPS
PARAM_H265 = (b"\x00\x00\x00\x01\x40", b"\x00\x00\x00\x01\x42",
              b"\x00\x00\x00\x01\x44")                                  # VPS, SPS, PPS
PARAM_SEARCH = 1024 * 1024             # look back up to 1 MiB for param sets
CHUNK = 8 * 1024 * 1024
TAIL_PAD = 256 * 1024                  # pad clip end past last IDR to keep P-frames


def scan(pattern, path, chunk=CHUNK):
    """Return all byte offsets of `pattern` (overlapping chunk boundary safe)."""
    offsets, carry, pos = [], b"", 0
    with open(path, "rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            data = carry + buf
            base = pos - len(carry)
            i = data.find(pattern)
            while i != -1:
                offsets.append(base + i)
                i = data.find(pattern, i + 1)
            carry = data[-(len(pattern) - 1):]
            pos += len(buf)
    return offsets


def next_start_code(path, offset, search=4 * 1024 * 1024):
    """Nearest NAL boundary after `offset` - defines the clip end."""
    with open(path, "rb") as f:
        f.seek(offset + 4)
        buf = f.read(search)
    i = buf.find(b"\x00\x00\x01")
    return offset + 4 + i if i != -1 else offset + 4 + search


def groups_from(offsets, join_gap):
    groups = [[offsets[0]]]
    for o in offsets[1:]:
        if o - groups[-1][-1] <= join_gap:
            groups[-1].append(o)
        else:
            groups.append([o])
    return groups


def find_param_set_start(path, start):
    """Earliest SPS/PPS/VPS offset within PARAM_SEARCH before `start`.

    Extending the clip start to include the parameter sets lets FFmpeg
    decode a carved GOP without external SPS/PPS injection (the donor
    'prepend SPS/PPS' technique, done by widening the carve window).
    """
    lo = max(0, start - PARAM_SEARCH)
    with open(path, "rb") as f:
        f.seek(lo)
        region = f.read(start - lo)
    best = start
    for pat in PARAM_H264 + PARAM_H265:
        i = region.find(pat)
        while i != -1:
            best = min(best, lo + i)
            i = region.find(pat, i + 1)
    return best


def extract_clip(image, start, end, dst):
    """Seek/read extraction (portable `dd skip/seek`)."""
    with open(image, "rb") as fin, open(dst, "wb") as fout:
        fin.seek(start)
        remaining = end - start
        while remaining > 0:
            buf = fin.read(min(CHUNK, remaining))
            if not buf:
                break
            fout.write(buf)
            remaining -= len(buf)


def remux(path, out_mp4):
    if not shutil.which("ffmpeg"):
        return None
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error",
                        "-i", path, "-c:v", "copy", out_mp4],
                       capture_output=True, text=True)
    return out_mp4 if r.returncode == 0 else None


def recover(image, workdir, join_gap_mb=2, min_clip=256 * 1024):
    os.makedirs(workdir, exist_ok=True)
    join_gap = join_gap_mb * 1024 * 1024
    probes = [
        ("idr_h264", IDR_H264, 1.0),
        ("idr_h265", IDR_H265[0], 1.0),
        ("idr_h265b", IDR_H265[1], 1.0),
        ("non_idr_h264", NON_IDR, 0.6),
    ]
    clips = []
    total_size = os.path.getsize(image)

    for label, pattern, confidence in probes:
        offs = scan(pattern, image)
        if not offs:
            continue
        codec = "h265" if "h265" in label else "h264"
        for g in groups_from(offs, join_gap):
            if len(g) < 2 and label.startswith("non_idr"):
                continue  # single NAL - ignore isolated packets
            start = find_param_set_start(image, g[0])  # include SPS/PPS/VPS
            end = next_start_code(image, g[-1]) + TAIL_PAD
            end = min(end, total_size)
            if end - start < min_clip:
                continue
            clip = os.path.join(workdir, "clip_%05d_%s.bin"
                                % (len(clips), codec))
            extract_clip(image, start, end, clip)
            mp4 = remux(clip, os.path.splitext(clip)[0] + ".mp4")
            clips.append({"index": len(clips), "nal_type": label,
                          "codec": codec,
                          "start_offset": start, "idr_offset": g[0],
                          "end_offset": end,
                          "size_bytes": end - start, "idr_count": len(g),
                          "confidence": confidence, "clip": clip, "mp4": mp4})

    return {"ok": True, "image": image, "workdir": workdir,
            "scan_region_bytes": total_size, "clips": clips,
            "recovered_count": len(clips),
            "signatures": "H.264 65/67/68 + H.265 26/28/40/42/44 (SPS/PPS/VPS "
                          "auto-included in carve window)",
            "note": "Byte-gap grouping approximates PTS-gap<2s at typical "
                    "DVR bitrates; advanced PTS parsing is a pluggable "
                    "enhancement."}


def main():
    ap = argparse.ArgumentParser(description="NYAYA H.264 carving engine")
    ap.add_argument("image", help="Raw image (.dd/.img)")
    ap.add_argument("--workdir", default="./recovered")
    ap.add_argument("--join-gap-mb", type=int, default=2)
    ap.add_argument("--min-kb", type=int, default=256,
                    help="Minimum clip size in KB")
    args = ap.parse_args()
    r = recover(args.image, args.workdir, args.join_gap_mb,
                args.min_kb * 1024)
    print(json.dumps(r, indent=2))
    sys.exit(0 if r["recovered_count"] > 0 else 1)


if __name__ == "__main__":
    main()