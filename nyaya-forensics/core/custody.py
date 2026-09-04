#!/usr/bin/env python3
"""
NYAYA Forensics - core/custody.py
Append-only hash-chained chain-of-custody ledger (SIH PS §F "legal
defensibility"). Every forensic action is appended as a JSONL entry:

  {"seq": 1, "ts_utc": "...", "examiner": "...", "action": "...",
   "details": {...}, "prev_hash": "<64hex>", "entry_hash": "<64hex>"}

entry_hash = SHA-256 over the canonical JSON of the entry WITHOUT entry_hash.
Genesis prev_hash = 64 x "0". Appends are O(1); verification recomputes the
whole chain and pinpoints the first tampered sequence (court-auditable).

Usage:
  python core/custody.py append --ledger case.custody.jsonl \
      --examiner "SI R. Kumar" --action ingest \
      --details '{"image": "sample.dd", "sha256": "..."}'
  python core/custody.py verify  --ledger case.custody.jsonl
"""
import argparse
import hashlib
import json
import os
import sys
import time

GENESIS = "0" * 64


def _canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def entry_hash(entry):
    payload = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()


def read_ledger(path):
    entries = []
    if not os.path.exists(path):
        return entries
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                entries.append({"seq": len(entries) + 1, "corrupt_line": line[:200]})
    return entries


def append(ledger_path, examiner, action, details=None):
    entries = read_ledger(ledger_path)
    prev = entries[-1].get("entry_hash", GENESIS) if entries else GENESIS
    entry = {
        "seq": len(entries) + 1,
        "ts_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "examiner": examiner or "unknown",
        "action": action,
        "details": details or {},
        "prev_hash": prev,
    }
    entry["entry_hash"] = entry_hash(entry)
    os.makedirs(os.path.dirname(os.path.abspath(ledger_path)), exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as f:
        f.write(_canonical(entry) + "\n")
    return {"ok": True, "ledger": ledger_path, "appended": entry,
            "total_entries": len(entries) + 1}


def verify(ledger_path):
    entries = read_ledger(ledger_path)
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        if "corrupt_line" in e:
            return {"ok": False, "valid": False, "total_entries": len(entries),
                    "broken_at_seq": i, "message": "corrupt JSONL line"}
        if e.get("seq") != i:
            return {"ok": False, "valid": False, "total_entries": len(entries),
                    "broken_at_seq": i, "message": "sequence gap/renumber"}
        if e.get("prev_hash") != prev:
            return {"ok": False, "valid": False, "total_entries": len(entries),
                    "broken_at_seq": i, "message": "prev_hash mismatch (tampering)"}
        if entry_hash(e) != e.get("entry_hash"):
            return {"ok": False, "valid": False, "total_entries": len(entries),
                    "broken_at_seq": i, "message": "entry_hash mismatch (entry modified)"}
        prev = e["entry_hash"]
    return {"ok": True, "valid": True, "total_entries": len(entries),
            "broken_at_seq": None, "head_hash": prev,
            "message": "chain intact: all %d entries verified" % len(entries)}


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA custody ledger")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("append")
    a.add_argument("--ledger", required=True)
    a.add_argument("--examiner", default="unknown")
    a.add_argument("--action", required=True)
    a.add_argument("--details", default=None, help="JSON string")
    v = sub.add_parser("verify")
    v.add_argument("--ledger", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "append":
        try:
            details = json.loads(args.details) if args.details else {}
        except json.JSONDecodeError as exc:
            print(json.dumps({"ok": False, "error": "bad --details JSON: %s" % exc}))
            return 2
        out = append(args.ledger, args.examiner, args.action, details)
        ok = out["ok"]
    else:
        out = verify(args.ledger)
        ok = out["valid"]
    print(json.dumps(out, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())