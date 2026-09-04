#!/usr/bin/env python3
"""
plugins/hikvision_wrapper.py - Hikvision / Godrej / Matrix Forensic Parser Bridge.

Natively handles:
  1. Exported folders containing .hik / .mp4 / .264 files -> decodes to standard MP4.
  2. Raw disk images (.dd/.img) -> scans HKVI & MPEG-PS stream markers,
     carves video streams and converts to MP4 with MD5/SHA-256 verification.

Usage:
  python plugins/hikvision_wrapper.py --image sample.dd --out extracted/
"""

import argparse
import json
import os
import shutil
import sys

from plugins.decoder import decode, _hash_file

CHUNK = 1024 * 1024
HKVI_MAGIC = b"HKVI"
MPEG_PS_MAGIC = b"\x00\x00\x01\xba"


def extract_from_folder(folder_path, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    extracted = []

    for root, _, files in os.walk(folder_path):
        for name in sorted(files):
            ext = os.path.splitext(name)[1].lower()
            if ext in (".hik", ".mp4", ".264", ".h264", ".mpg", ".mpeg"):
                src = os.path.join(root, name)
                dst = os.path.join(out_dir, f"{os.path.splitext(name)[0]}_decoded.mp4")
                res = decode(src, dst)
                if res.get("ok"):
                    extracted.append({
                        "source": src,
                        "output": dst,
                        "format": res.get("detected_format", "hikvision"),
                        "size_bytes": res.get("output_size", 0),
                        "md5": res.get("output_md5", ""),
                        "sha256": res.get("output_sha256", ""),
                    })

    return {
        "engine": "hikvision_native_folder_extractor",
        "extracted_files": [e["output"] for e in extracted],
        "extracted_count": len(extracted),
        "details": extracted,
        "error": None,
    }


def extract_from_image(image_path, out_dir, max_clips=25):
    os.makedirs(out_dir, exist_ok=True)
    extracted = []
    total_size = os.path.getsize(image_path)

    # Scan for HKVI or MPEG-PS pack headers
    stream_offsets = []
    with open(image_path, "rb") as fh:
        pos = 0
        carry = b""
        while pos < total_size:
            buf = fh.read(CHUNK)
            if not buf:
                break
            data = carry + buf
            base = pos - len(carry)

            # Check HKVI
            idx = data.find(HKVI_MAGIC)
            while idx != -1:
                stream_offsets.append(base + idx)
                if len(stream_offsets) >= 500:
                    break
                idx = data.find(HKVI_MAGIC, idx + 4)

            # Check MPEG-PS
            idx = data.find(MPEG_PS_MAGIC)
            while idx != -1:
                stream_offsets.append(base + idx)
                if len(stream_offsets) >= 500:
                    break
                idx = data.find(MPEG_PS_MAGIC, idx + 4)

            if len(stream_offsets) >= 500:
                break
            carry = data[-3:]
            pos += len(buf)

    stream_offsets = sorted(list(set(stream_offsets)))

    if not stream_offsets:
        return {
            "engine": "hikvision_native_image_scanner",
            "extracted_files": [],
            "extracted_count": 0,
            "details": [],
            "error": "No HKVI or MPEG-PS signatures found in disk image",
        }

    # Group contiguous stream frames (gap < 2MB)
    groups = [[stream_offsets[0]]]
    for o in stream_offsets[1:]:
        if o - groups[-1][-1] <= 2 * 1024 * 1024:
            groups[-1].append(o)
        else:
            groups.append([o])

    for i, grp in enumerate(groups[:max_clips]):
        start = grp[0]
        end = min(total_size, grp[-1] + 512 * 1024)
        raw_clip = os.path.join(out_dir, f"hik_stream_{i:03d}.raw")
        out_mp4 = os.path.join(out_dir, f"hik_stream_{i:03d}.mp4")

        with open(image_path, "rb") as src, open(raw_clip, "wb") as dst:
            src.seek(start)
            remaining = end - start
            while remaining > 0:
                b = src.read(min(CHUNK, remaining))
                if not b:
                    break
                dst.write(b)
                remaining -= len(b)

        res = decode(raw_clip, out_mp4)
        if res.get("ok"):
            extracted.append({
                "stream_id": i,
                "start_offset": start,
                "end_offset": end,
                "output": out_mp4,
                "size_bytes": res.get("output_size", 0),
                "md5": res.get("output_md5", ""),
                "sha256": res.get("output_sha256", ""),
            })
        if os.path.exists(raw_clip):
            try:
                os.remove(raw_clip)
            except OSError:
                pass

    return {
        "engine": "hikvision_native_image_scanner",
        "extracted_files": [e["output"] for e in extracted],
        "extracted_count": len(extracted),
        "details": extracted,
        "error": None if extracted else "Hikvision signatures found but failed to convert to MP4",
    }


def run(image_path, out_dir):
    if not os.path.exists(image_path):
        return {"error": "image not found", "path": image_path}

    if os.path.isdir(image_path):
        return extract_from_folder(image_path, out_dir)
    return extract_from_image(image_path, out_dir)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Hikvision / Godrej / Matrix parser bridge")
    ap.add_argument("--image", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    result = run(args.image, args.out)
    print(json.dumps(result, indent=2))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    sys.exit(main())