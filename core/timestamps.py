#!/usr/bin/env python3
"""
core/timestamps.py - Vendor timestamp normalisation to IST.

Implements ONLY the two conversions the PRD requires. No fake parsing.

  Dahua BCD  -> IST : offset 16 in the 24-byte DHAV frame header holds a
                      4-byte BCD datetime YYYYMMDDhhmmss (little-endian bytes).
                      Example bytes 18 26 06 15 -> 2026-06-15 18:26:00.
  Hikvision  -> IST : 32-bit little-endian Unix epoch at frame offset 12.

Both functions record the raw value AND the normalised IST so the assumption
is auditable. No timezone guessing beyond the explicit +05:30 IST offset.

Usage:
  python core/timestamps.py --dahua-bcd 18260615103000
  python core/timestamps.py --hik-epoch 1782924600
"""

import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def bcd_to_int(bcd_bytes):
    """Convert a BCD byte sequence to an integer (e.g. b'\\x18\\x26' -> 1826)."""
    result = 0
    for byte in bcd_bytes:
        result = result * 100 + ((byte >> 4) * 10 + (byte & 0x0F))
    return result


def dahua_bcd_to_ist(raw):
    """raw: 14-digit BCD string 'YYYYMMDDhhmmss' -> IST datetime string."""
    if len(raw) != 14 or not raw.isdigit():
        raise ValueError(f"Dahua BCD must be 14 digits, got {raw!r}")
    year = int(raw[0:4])
    month = int(raw[4:6])
    day = int(raw[6:8])
    hour = int(raw[8:10])
    minute = int(raw[10:12])
    second = int(raw[12:14])
    dt_utc = datetime(year, month, day, hour, minute, second, tzinfo=timezone.utc)
    dt_ist = dt_utc.astimezone(IST)
    return {
        "raw": raw,
        "raw_kind": "dahua_bcd",
        "utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ist": dt_ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "offset_hours": 5.5,
    }


def hik_epoch_to_ist(epoch):
    """epoch: Unix seconds (int) -> IST datetime string."""
    epoch = int(epoch)
    dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
    dt_ist = dt_utc.astimezone(IST)
    return {
        "raw": epoch,
        "raw_kind": "hik_unix_epoch",
        "utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ist": dt_ist.strftime("%Y-%m-%d %H:%M:%S %Z"),
        "offset_hours": 5.5,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA Forensics timestamp converter")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dahua-bcd", help="14-digit Dahua BCD YYYYMMDDhhmmss")
    g.add_argument("--hik-epoch", type=int, help="Hikvision Unix epoch seconds")
    args = ap.parse_args(argv)

    try:
        if args.dahua_bcd:
            out = dahua_bcd_to_ist(args.dahua_bcd)
        else:
            out = hik_epoch_to_ist(args.hik_epoch)
    except (ValueError, OverflowError, OSError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2

    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())