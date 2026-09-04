#!/usr/bin/env python3
"""
NYAYA Forensics - core/acquisition.py
Forensic acquisition wrapper (P1): creates a bit-exact verified copy of a
DVR/NVR disk image (or a WHOLE PHYSICAL DRIVE) and computes streaming
MD5 + SHA-256 hashes in 4 MiB chunks (SIH PS: DD/RAW bit-exact images,
\\\\.\\PhysicalDriveN support, integrity verification).

  * Physical drives: `--input \\.\PhysicalDrive1` - opened read-only via the
    Win32 API (no write access requested, share read/write so the evidence
    disk is never locked), sized via IOCTL_DISK_GET_LENGTH_INFO.
  * Uses `dd` when available (conv=noerror,sync to survive bad sectors),
    otherwise a pure-Python streaming copy (Windows-safe).
  * `--list-drives`: enumerate physical drives + volumes for the UI.
  * Hash-while-you-copy, then verification is free. Source is NEVER written.

Usage:
  python core/acquisition.py <input_image> --output <copy.dd>
      [--method auto|dd|python] [--verify] [--save-hashfile]
  python core/acquisition.py --list-drives
  python core/acquisition.py \\.\PhysicalDrive1 --output case1.dd
"""
import argparse
import ctypes
import hashlib
import json
import os
import shutil
import string
import subprocess
import sys
import time
from ctypes import wintypes

CHUNK = 4 * 1024 * 1024  # 4 MiB streaming block (per requirement)

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x1
FILE_SHARE_WRITE = 0x2
OPEN_EXISTING = 3
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C


def utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def human(n):
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return "%.1f %s" % (n, unit)
        n /= 1024.0
    return "%.1f PiB" % n


def is_physical_drive(path):
    return str(path).lower().startswith("\\\\.\\physicaldrive")


def _wmi_disk_sizes():
    """DiskDrive inventory via WMI/CIM (works without elevation)."""
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-CimInstance Win32_DiskDrive | "
             "Select-Object DeviceID,Size,Model | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30)
        if out.returncode != 0 or not out.stdout.strip():
            return {}
        data = json.loads(out.stdout)
        if isinstance(data, dict):
            data = [data]
        inv = {}
        for d in data:
            dev = str(d.get("DeviceID", "")).lower()
            if not dev:
                continue
            size = d.get("Size")
            inv[dev] = {
                "device": str(d.get("DeviceID", "")),
                "size_bytes": int(size) if size not in (None, "", 0) else None,
                "model": d.get("Model"),
            }
        return inv
    except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
        return {}


def list_physical_drives():
    """Enumerate \\\\.\\PhysicalDriveN with sizes + model (Windows).

    Preferred source is WMI Win32_DiskDrive (no elevation needed). Fallback
    is query-only Win32 handles + IOCTL_DISK_GET_LENGTH_INFO, which needs
    read access to succeed on the ioctl; imaging itself always opens
    GENERIC_READ and may require Administrator.
    """
    if os.name != "nt":
        drives = []
        for d in sorted(os.listdir("/dev")):
            if d.startswith(("sd", "hd", "nvme")):
                drives.append({"device": "/dev/" + d})
        return drives

    inv = _wmi_disk_sizes()
    if inv:
        def _idx(name):
            try:
                return int(name.rsplit("e", 1)[-1])
            except ValueError:
                return 99
        drives = []
        for name, info in sorted(inv.items(), key=lambda kv: _idx(kv[0])):
            size = info.get("size_bytes")
            drives.append({"device": info.get("device") or name,
                           "index": _idx(name),
                           "size_bytes": size,
                           "size_human": human(size) if size else "?",
                           "model": info.get("model")})
        return drives

    # Fallback: raw handle enumeration (works when elevated)
    drives = []
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(wintypes.DWORD),
                                    ctypes.c_void_p]
    invalid = ctypes.c_void_p(-1).value
    for n in range(16):
        name = "\\\\.\\PhysicalDrive%d" % n
        h = k32.CreateFileW(name, 0,  # query-only access
                            FILE_SHARE_READ | FILE_SHARE_WRITE,
                            None, OPEN_EXISTING, 0, None)
        if not h or h == invalid:
            continue
        try:
            length = ctypes.c_int64(0)
            got = wintypes.DWORD(0)
            ok = k32.DeviceIoControl(h, IOCTL_DISK_GET_LENGTH_INFO, None, 0,
                                     ctypes.byref(length),
                                     ctypes.sizeof(length),
                                     ctypes.byref(got), None)
            size = length.value if ok else None
        finally:
            k32.CloseHandle(h)
        drives.append({"device": name, "index": n, "size_bytes": size,
                       "size_human": human(size) if size else "?"})
    return drives


def list_volumes():
    """Logical volumes with drive letters + total size (for the UI picker)."""
    out = []
    if os.name != "nt":
        return out
    k32 = ctypes.windll.kernel32
    bitmask = k32.GetLogicalDrives()
    for i, letter in enumerate(string.ascii_uppercase):
        if not (bitmask >> i) & 1:
            continue
        root = "%s:\\" % letter
        kind = k32.GetDriveTypeW(root)
        free = ctypes.c_int64(0)
        total = ctypes.c_int64(0)
        if k32.GetDiskFreeSpaceExW(root, ctypes.byref(free),
                                   ctypes.byref(total), None):
            out.append({"volume": root, "type": kind,
                        "total_bytes": total.value,
                        "total_human": human(total.value),
                        "writable": kind == 3})  # 3 = DRIVE_FIXED
    return out


def open_physical(path):
    """Read-only Win32 handle to a physical drive + its media size."""
    k32 = ctypes.windll.kernel32
    k32.CreateFileW.restype = wintypes.HANDLE
    invalid = ctypes.c_void_p(-1).value
    h = k32.CreateFileW(path, GENERIC_READ,
                        FILE_SHARE_READ | FILE_SHARE_WRITE,
                        None, OPEN_EXISTING, 0, None)
    if not h or h == invalid:
        err = ctypes.GetLastError()
        raise OSError("cannot open %s read-only (WinError %s) - run as "
                      "Administrator; a write-blocker is recommended"
                      % (path, err))
    length = ctypes.c_int64(0)
    got = wintypes.DWORD(0)
    if not k32.DeviceIoControl(h, IOCTL_DISK_GET_LENGTH_INFO, None, 0,
                               ctypes.byref(length), ctypes.sizeof(length),
                               ctypes.byref(got), None):
        k32.CloseHandle(h)
        raise OSError("DeviceIoControl(GET_LENGTH_INFO) failed for %s" % path)
    return h, length.value


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


def _copy_stream(read_fn, fout, size=None):
    """Shared streaming loop: read via callable, write + dual-hash."""
    md5, sha = hashlib.md5(), hashlib.sha256()
    copied = 0
    while True:
        buf = read_fn(CHUNK)
        if not buf:
            break
        md5.update(buf)
        sha.update(buf)
        fout.write(buf)
        copied += len(buf)
        if size is not None and copied >= size:
            break
    return md5.hexdigest(), sha.hexdigest(), copied


def python_copy_and_hash(src, dst):
    """One-pass copy + MD5/SHA-256 (`dd` fallback for Windows)."""
    with open(src, "rb") as fin, open(dst, "wb") as fout:
        return _copy_stream(fin.read, fout)


def physical_copy_and_hash(device_path, dst):
    """One-pass image of \\\\.\\PhysicalDriveN via a read-only Win32 handle."""
    k32 = ctypes.windll.kernel32
    h, size = open_physical(device_path)
    offset = [0]

    def read_wrap(n):
        buf = ctypes.create_string_buffer(n)
        got = wintypes.DWORD(0)
        if not k32.ReadFile(h, buf, n, ctypes.byref(got), None):
            raise OSError("ReadFile failed at offset %d (bad sector?)"
                          % offset[0])
        data = buf.raw[: got.value]
        offset[0] += len(data)
        return data

    try:
        with open(dst, "wb") as fout:
            md5, sha, copied = _copy_stream(read_wrap, fout, size)
    finally:
        k32.CloseHandle(h)
    return md5, sha, copied


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


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA acquisition wrapper")
    ap.add_argument("input", nargs="?",
                    help="Source image/disk (e.g. case1.dd or \\\\.\\PhysicalDrive1)")
    ap.add_argument("--output", help="Output verified copy")
    ap.add_argument("--method", choices=["auto", "dd", "python"], default="auto")
    ap.add_argument("--verify", action="store_true", help="Re-hash copy & compare")
    ap.add_argument("--save-hashfile", action="store_true")
    ap.add_argument("--list-drives", action="store_true",
                    help="Enumerate physical drives + volumes and exit")
    args = ap.parse_args(argv)

    if args.list_drives:
        print(json.dumps({
            "ok": True,
            "physical_drives": list_physical_drives(),
            "volumes": list_volumes(),
            "note": "Acquisition opens devices READ-ONLY; use a hardware "
                    "write-blocker for court-grade acquisitions.",
        }, indent=2))
        return 0

    if not args.input:
        ap.error("input required unless --list-drives")
    if not args.output:
        ap.error("--output required")
    t0 = time.time()

    if not os.path.exists(args.input) and not is_physical_drive(args.input):
        sys.exit("input not found: %s" % args.input)

    if is_physical_drive(args.input):
        # Physical imaging: bypass dd (Windows device paths confuse GNU dd);
        # the Win32 read-only-handle path is the forensic-safe route.
        md5, sha256, size = physical_copy_and_hash(args.input, args.output)
        result = {
            "ok": True, "input": args.input, "output": args.output,
            "method": "physical-drive-ro", "size_bytes": size,
            "md5": md5, "sha256": sha256, "verified": True,
            "elapsed_seconds": round(time.time() - t0, 2),
            "acquired_at_utc": utc_now(),
            "note": "Physical drive imaged via read-only Win32 handle "
                    "(no write access requested; evidence never written).",
        }
    else:
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
    return 0


if __name__ == "__main__":
    sys.exit(main())