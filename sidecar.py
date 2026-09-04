#!/usr/bin/env python3
"""
sidecar.py - NYAYA Forensics Python sidecar dispatcher.

Invoked by the Tauri Rust backend. Dispatches to the real modules:
  device_detect, acquisition, timestamps, dahua_wrapper, hikvision_wrapper,
  decoder, recovery, analytics, pdf_report.

Usage (from Rust):
  python sidecar.py detect --file sample.dd
  python sidecar.py acquire --image sample.dd --out cases/CASE-001
  python sidecar.py dahua --image sample.dd --out extracted/
  python sidecar.py hikvision --image sample.dd --out extracted/
  python sidecar.py decode --input rec.dav --out rec.mp4
  python sidecar.py recover --image sample.dd --out recovered/
  python sidecar.py motion --video clip.mp4
  python sidecar.py object --video clip.mp4
  python sidecar.py pdf --case case.json --out report.pdf
  python sidecar.py bcd --raw 18260615103000
  python sidecar.py epoch --raw 1782924600
"""

import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def _run(module, args):
    cmd = [sys.executable, "-m", module] + args
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=7200, check=False,
            cwd=HERE,
        )
    except FileNotFoundError:
        return {"error": "python interpreter missing", "cmd": " ".join(cmd)}
    except subprocess.TimeoutExpired:
        return {"error": "sidecar timed out", "cmd": " ".join(cmd)}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    try:
        payload = json.loads(out) if out else {}
    except json.JSONDecodeError:
        payload = {"raw_stdout": out}
    payload["returncode"] = proc.returncode
    if err and "error" not in payload:
        payload["stderr_tail"] = err[-400:]
    return payload


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print(json.dumps({
            "error": "no subcommand",
            "usage": "python sidecar.py <detect|acquire|dahua|hikvision|decode|recover|motion|object|pdf|bcd|epoch> ...",
        }))
        return 2

    cmd = argv[0]
    rest = argv[1:]

    dispatch = {
        "detect": ("core.device_detect", ["--file"] if rest and not rest[0].startswith("--") else []),
        "acquire": ("core.acquisition", []),
        "dahua": ("plugins.dahua_wrapper", []),
        "hikvision": ("plugins.hikvision_wrapper", []),
        "decode": ("plugins.decoder", []),
        "recover": ("plugins.recovery", []),
        "motion": ("ai.analytics", ["--mode", "motion"]),
        "object": ("ai.analytics", ["--mode", "object"]),
        "face": ("ai.analytics", ["--mode", "face"]),
        "pdf": ("report.pdf_report", []),
        "bcd": ("core.timestamps", ["--dahua-bcd"]),
        "epoch": ("core.timestamps", ["--hik-epoch"]),
    }

    if cmd not in dispatch:
        print(json.dumps({"error": f"unknown subcommand {cmd!r}", "valid": list(dispatch)}))
        return 2

    module, prefix = dispatch[cmd]
    args = prefix + rest
    result = _run(module, args)
    print(json.dumps(result, indent=2))
    return 0 if result.get("error") is None else 1


if __name__ == "__main__":
    sys.exit(main())