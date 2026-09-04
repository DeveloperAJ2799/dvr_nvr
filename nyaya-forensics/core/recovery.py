#!/usr/bin/env python3
"""
NYAYA Forensics - core/recovery.py
Deleted-recording carving engine (P3): scans a raw image for H.264 IDR
start codes (00 00 00 01 65) and groups hits whose byte-gap is below
`--join-gap` (default 2 MB - the space a ~2 s GOP needs at common DVR
bitrates; our byte-domain proxy for the "PTS gap < 2 s" grouping rule).
Each group is extracted as a clip (Python seek/read equivalent of
`dd skip/seek`), then every clip is remuxed to MP4 with FFmpeg.

Usage:
  python core/recovery.py <image.dd> --workdir ./recovered [--join-gap-mb 2]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

IDR = b"\x00\x00\x00\x01\x65"      # H.264 IDR (I-frame) NAL
NON_IDR = b"\x00\x00\x00\x01\x41"   # H.264 non-IDR slice NAL
CHUNK = 8 * 1024 * 1024
TAIL_PAD = 256 * 1024               # pad clip end past last IDR to keep P-frames


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
    probes = [("idr", IDR, 1.0), ("non_idr", NON_IDR, 0.6)]
    clips = []
    total_size = os.path.getsize(image)

    for label, pattern, confidence in probes:
        offs = scan(pattern, image)
        if not offs:
            continue
        for g in groups_from(offs, join_gap):
            if len(g) < 2 and label == "non_idr":
                continue  # single NAL - ignore isolated packets
            start = g[0]
            end = next_start_code(image, g[-1]) + TAIL_PAD
            end = min(end, total_size)
            if end - start < min_clip:
                continue
            clip = os.path.join(workdir, "clip_%05d_%s.bin"
                                % (len(clips), "idr" if label == "idr" else "x"))
            extract_clip(image, start, end, clip)
            mp4 = remux(clip, os.path.splitext(clip)[0] + ".mp4")
            clips.append({"index": len(clips), "nal_type": label,
                          "start_offset": start, "end_offset": end,
                          "size_bytes": end - start, "idr_count": len(g),
                          "confidence": confidence, "clip": clip, "mp4": mp4})

    return {"ok": True, "image": image, "workdir": workdir,
            "scan_region_bytes": total_size, "clips": clips,
            "recovered_count": len(clips),
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