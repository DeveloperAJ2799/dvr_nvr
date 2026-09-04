#!/usr/bin/env python3
"""
NYAYA Forensics - plugins/dahua_wrapper.py
Dahua DHFS plugin (P2): INVOKES the existing open-source parser
drcrecoverydata/dvr_dahua via subprocess - we never re-implement DHFS
decoding. The parser script is located at:

  1. $DAHUA_PARSER_SCRIPT  (environment override)
  2. ./vendor/dvr_dahua/Python_3.12.3_Dahua_23.4.24.py  (repo checkout)

The plugin returns a manifest of extracted files for the case ledger.

Usage:
  python plugins/dahua_wrapper.py <image.dd> --outdir <dir>
"""
import argparse
import json
import os
import subprocess
import sys

SCRIPT_NAME = "Python_3.12.3_Dahua_23.4.24.py"
REPO = "https://github.com/drcrecoverydata/dvr_dahua"


def locate_script():
    env = os.environ.get("DAHUA_PARSER_SCRIPT")
    if env and os.path.exists(env):
        return env
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cand = os.path.join(root, "vendor", "dvr_dahua", SCRIPT_NAME)
    return cand if os.path.exists(cand) else None


def run(image, outdir):
    script = locate_script()
    if script is None:
        return {"ok": False,
                "error": "dvr_dahua parser not found - clone it first:",
                "hint": "git clone %s vendor/dvr_dahua" % REPO}
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
    ap = argparse.ArgumentParser(description="Dahua DHFS open-source wrapper")
    ap.add_argument("image", help="Path to acquired DHFS image (.dd)")
    ap.add_argument("--outdir", default="./extracted", help="Extraction folder")
    args = ap.parse_args()
    print(json.dumps(run(args.image, args.outdir), indent=2))


if __name__ == "__main__":
    main()