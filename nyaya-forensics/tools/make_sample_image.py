#!/usr/bin/env python3
"""Build a small synthetic DVR image for sidecar smoke tests.

Plant:
  - a "DHFS" volume magic near the start (vendor_detect should find it)
  - two clusters of H.264 IDR NAL start codes (00 00 00 01 65) ~4 MB apart
    (recovery.py should carve them into 2 clips)

Usage: python tools/make_sample_image.py [path] [size_mb]
"""
import os
import sys

IDR = b"\x00\x00\x00\x01\x65"


def build(path="test_evidence/sample.dd", size_mb=12):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    real_h264 = b""
    base_dir = os.path.dirname(os.path.abspath(path))
    h264_path = os.path.join(base_dir, "real.h264")
    if os.path.exists(h264_path):
        with open(h264_path, "rb") as f:
            real_h264 = f.read()
    if not real_h264:
        real_h264 = IDR + b"\x12\x34\x56" + os.urandom(2000)

    with open(path, "wb") as f:
        f.write(os.urandom(4 * 1024))      # junk head
        f.write(b"DHFS")                    # magic bytes for Dahua/CP Plus vendor ID
        f.seek(int(0.3 * size_mb * 1024 * 1024))
        f.write(real_h264)
        f.seek(int(0.65 * size_mb * 1024 * 1024))
        f.write(real_h264)
        f.seek(size_mb * 1024 * 1024 - 1)
        f.write(b"\x00")
    print("synthetic image:", path, os.path.getsize(path), "bytes")


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else "test_evidence/sample.dd"
    s = int(sys.argv[2]) if len(sys.argv) > 2 else 12
    build(p, s)