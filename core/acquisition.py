#!/usr/bin/env python3
"""
core/acquisition.py - Evidence acquisition with streaming hashes.

Real behaviour:
  * Raw images (.dd/.img/.raw): hashed with hashlib in 4 MiB chunks (never loads
    the whole image into memory). Mirrors what `dd` would stream.
  * EWF images (.E01): read through libewf-python (the pip-installable Python
    bindings for libewf). Falls back gracefully if the wheel is missing.
  * Original evidence is OPENED READ-ONLY and never written to.

Usage:
  python core/acquisition.py --image sample.dd --out cases/CASE-001/evidence
  python core/acquisition.py --image sample.001 --out cases/CASE-001/evidence
"""

import argparse
import hashlib
import json
import os
import sys

CHUNK = 4 * 1024 * 1024  # 4 MiB streaming chunk


def _is_e01(path):
    """EWF-E01 segments start with the ASCII 'EVTF' magic at offset 0."""
    try:
        with open(path, "rb") as fh:
            return fh.read(4) == b"EVTF"
    except OSError:
        return False


def _hash_stream(fh, size):
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    remaining = size
    while remaining > 0:
        block = fh.read(min(CHUNK, remaining))
        if not block:
            break
        md5.update(block)
        sha256.update(block)
        remaining -= len(block)
    return md5.hexdigest(), sha256.hexdigest()


def acquire_raw(image_path, out_dir):
    if not os.path.exists(image_path):
        raise FileNotFoundError(image_path)
    size = os.path.getsize(image_path)
    with open(image_path, "rb") as fh:
        md5, sha256 = _hash_stream(fh, size)
    return {
        "source": image_path,
        "size_bytes": size,
        "md5": md5,
        "sha256": sha256,
        "method": "raw_stream",
        "acquired": False,
        "note": "Original opened read-only; hash computed by streaming. "
                "No copy made - evidence manifest records hashes only.",
    }


def acquire_e01(image_path, out_dir):
    try:
        import pyewf as libewf  # libewf-python installs its module as "pyewf"
    except ImportError as exc:
        return {
            "source": image_path,
            "error": "libewf-python not installed",
            "detail": str(exc),
            "install": "pip install libewf-python",
        }

    handle = libewf.handle()
    handle.open(image_path)
    try:
        size = handle.get_media_size()
        md5 = hashlib.md5()
        sha256 = hashlib.sha256()
        offset = 0
        while offset < size:
            count = min(CHUNK, size - offset)
            data = handle.read_random(offset, count)
            if not data:
                break
            md5.update(data)
            sha256.update(data)
            offset += len(data)
    finally:
        handle.close()

    return {
        "source": image_path,
        "size_bytes": size,
        "md5": md5.hexdigest(),
        "sha256": sha256.hexdigest(),
        "method": "ewf_stream",
        "acquired": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA Forensics evidence acquisition")
    ap.add_argument("--image", required=True, help="Path to .dd/.img/.raw or .001/.E01")
    ap.add_argument("--out", required=True, help="Case output directory")
    args = ap.parse_args(argv)

    if not os.path.exists(args.image):
        print(json.dumps({"error": "image not found", "path": args.image}))
        return 2

    os.makedirs(args.out, exist_ok=True)

    if _is_e01(args.image):
        result = acquire_e01(args.image, args.out)
    else:
        result = acquire_raw(args.image, args.out)

    manifest_path = os.path.join(args.out, "evidence_manifest.json")
    with open(manifest_path, "w") as fh:
        json.dump(result, fh, indent=2)

    result["manifest"] = manifest_path
    print(json.dumps(result, indent=2))
    return 0 if "error" not in result else 1


if __name__ == "__main__":
    sys.exit(main())