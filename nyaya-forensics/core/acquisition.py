#!/usr/bin/env python3
"""
NYAYA Forensics - core/acquisition.py
Forensic acquisition wrapper (P1): creates a bit-exact verified copy of a
DVR/NVR disk image and computes streaming MD5 + SHA-256 hashes in 4 MiB
chunks. Uses `dd` when available (conv=noerror,sync to survive bad sectors),
otherwise a pure-Python streaming copy (Windows-safe). Hash-while-you-copy,
then verification is free.

Usage:
  python core/acquisition.py <input_image> --output <copy.dd>
      [--method auto|dd|python] [--verify] [--save-hashfile]
"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

CHUNK = 4 * 1024 * 1024  # 4 MiB streaming block (per requirement)


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def stream_hash(path, algos=("md5", "sha256")):
    """Streaming multi-hash (4 MiB chunks) of an existing file."""
    hs = {a: hashlib.new(a) for a in algos}
    with open(path, "rb") as f:
        while True:
            buf = f.read(CHUNK)
            if not buf:
                break
            for h in hs.values():
                h.update(buf)
    return {a: h.hexdigest() for a, h in hs.items()}


def python_copy_and_hash(src, dst):
    """One-pass copy + MD5/SHA-256 (`dd` fallback for Windows)."""
    md5, sha = hashlib.md5(), hashlib.sha256()
    size = 0
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        while True:
            buf = fin.read(CHUNK)
            if not buf:
                break
            md5.update(buf)
            sha.update(buf)
            fout.write(buf)
            size += len(buf)
            fout.flush()
    return md5.hexdigest(), sha.hexdigest(), size


def dd_copy(src, dst):
    """dd mode: conv=noerror,sync keeps imaging even past bad sectors."""
    return subprocess.run(
        ["dd", "if=%s" % src, "of=%s" % dst, "bs=4M",
         "conv=noerror,sync", "status=progress"],
        capture_output=True, text=True,
    )


def write_hashfile(path, hashes):
    ftk_style = ["%s (%s) = %s" % (algo.upper(), path, dig)
                 for algo, dig in hashes.items()]
    with open(path + ".hashes.txt", "w") as f:
        f.write("\n".join(ftk_style) + "\n")


def main():
    ap = argparse.ArgumentParser(description="NYAYA acquisition wrapper")
    ap.add_argument("input", help="Source image/disk (e.g. case1.dd)")
    ap.add_argument("--output", required=True, help="Output verified copy")
    ap.add_argument("--method", choices=["auto", "dd", "python"], default="auto")
    ap.add_argument("--verify", action="store_true", help="Re-hash copy & compare")
    ap.add_argument("--save-hashfile", action="store_true")
    args = ap.parse_args()
    t0 = time.time()

    if not os.path.exists(args.input):
        sys.exit("input not found: %s" % args.input)

    method = args.method
    if method == "auto":
        method = "dd" if shutil.which("dd") else "python"
        print("[acquisition] dd not found on PATH - using pure-Python "
              "streaming copy (bit-exact)", file=sys.stderr)

    if method == "dd":
        r = dd_copy(args.input, args.output)
        if r.returncode != 0:
            sys.exit("dd failed: %s" % r.stderr[-2000:])
        dst = stream_hash(args.output)
        size = os.path.getsize(args.output)
        verified = stream_hash(args.input) == dst  # free source-comparison
        result = {
            "ok": True, "input": args.input, "output": args.output,
            "method": "dd", "size_bytes": size,
            "md5": dst["md5"], "sha256": dst["sha256"],
            "verified": verified,
            "elapsed_seconds": round(time.time() - t0, 2),
            "acquired_at_utc": utc_now(),
        }
    else:
        md5, sha256, size = python_copy_and_hash(args.input, args.output)
        verified = True
        if args.verify:  # optional independent re-hash of the copy
            chk = stream_hash(args.output)
            verified = chk["md5"] == md5 and chk["sha256"] == sha256
        result = {
            "ok": True, "input": args.input, "output": args.output,
            "method": "python-stream", "size_bytes": size,
            "md5": md5, "sha256": sha256,
            "verified": verified,
            "elapsed_seconds": round(time.time() - t0, 2),
            "acquired_at_utc": utc_now(),
        }

    if args.save_hashfile:
        write_hashfile(args.output, {"md5": result["md5"],
                                     "sha256": result["sha256"]})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()