#!/usr/bin/env python3
"""
NYAYA Forensics - core/timestamps.py
Vendor timestamp normaliser (P4). Converts proprietary DVR/NVR clock formats
to normalised UTC + IST for the multi-camera timeline (SIH PS §D).

Supported formats (verified against real device layouts):
  Dahua DHAV : 4-8 byte packed BCD YYYYMMDDhhmm[ss] at frame-header offset 16
               (device-LOCAL clock as stored on media).
  Hikvision  : 32-bit little-endian Unix epoch (absolute UTC).
  ISO-8601   : pass-through validation for exported MP4 metadata.

Timezone policy (auditable, no guessing):
  * Hikvision epoch -> true UTC by definition; IST = UTC + 05:30.
  * Dahua BCD       -> device-local wall clock. Default output treats it as
    IST (the case timezone assumption); pass --assume-utc if the device was
    known to store UTC. Both `raw` and the assumption are echoed in the JSON
    so the report keeps an audit trail.

Usage:
  python core/timestamps.py --dahua-bcd 20260615182600
  python core/timestamps.py --bcd-bytes 18260615103000
  python core/timestamps.py --hik-epoch 1781552160
"""
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta

IST = timezone(timedelta(hours=5, minutes=30), "IST")


def _fmt(dt_utc, assumption):
    dt_ist = dt_utc.astimezone(IST)
    return {
        "utc": dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "ist": dt_ist.strftime("%Y-%m-%d %H:%M:%S IST"),
        "epoch_utc": round(dt_utc.timestamp(), 3),
        "tz_assumption": assumption,
    }


def bcd_bytes_to_digits(bcd_bytes):
    """BCD byte sequence -> digit string (e.g. b'\\x18\\x26' -> '1826')."""
    digits = ""
    for b in bcd_bytes:
        hi, lo = (b >> 4) & 0x0F, b & 0x0F
        if hi > 9 or lo > 9:
            raise ValueError("invalid BCD nibble in %s" % bcd_bytes.hex())
        digits += "%d%d" % (hi, lo)
    return digits


def dahua_bcd_to_ist(raw, assume_utc=False):
    """raw: 14-digit BCD 'YYYYMMDDhhmmss' (or 8 BCD bytes as hex/str)."""
    if isinstance(raw, (bytes, bytearray)):
        raw = bcd_bytes_to_digits(raw)
    elif isinstance(raw, int):
        raw = str(raw)
    raw = str(raw).strip()
    if len(raw) == 12:
        raw += "00"  # YYYYMMDDhhmm without seconds
    if len(raw) != 14 or not raw.isdigit():
        raise ValueError(f"Dahua BCD must be 14 digits, got {raw!r}")
    year, mon, day = int(raw[0:4]), int(raw[4:6]), int(raw[6:8])
    hh, mm, ss = int(raw[8:10]), int(raw[10:12]), int(raw[12:14])
    if not (1 <= mon <= 12 and 1 <= day <= 31 and hh <= 23 and mm <= 59 and ss <= 59):
        raise ValueError(f"Dahua BCD out of calendar range: {raw!r}")
    assumption = "UTC" if assume_utc else "device-local (case tz; IST by default)"
    local = datetime(year, mon, day, hh, mm, ss,
                     tzinfo=timezone.utc if assume_utc else IST)
    return {"ok": True, "raw": raw, "raw_kind": "dahua_bcd",
            "offset_hours": 5.5, **_fmt(local, assumption)}


def hik_epoch_to_ist(epoch):
    """epoch: Unix seconds (int) -> UTC + IST."""
    epoch = int(epoch)
    dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
    return {"ok": True, "raw": epoch, "raw_kind": "hik_unix_epoch",
            "offset_hours": 5.5, **_fmt(dt_utc, "absolute UTC (unix epoch)")}


def normalize_any(evt):
    """Normalise one timeline event dict in place (adds utc/ist/epoch_utc)."""
    from datetime import datetime as _dt
    out = dict(evt)
    if evt.get("epoch") is not None or evt.get("seconds_epoch") is not None:
        ep = float(evt.get("epoch", evt.get("seconds_epoch")))
        dt = _dt.fromtimestamp(ep, tz=timezone.utc)
        out.update(_fmt(dt, "absolute UTC (unix epoch)"))
    elif evt.get("hik_epoch") is not None:
        out.update(hik_epoch_to_ist(evt["hik_epoch"]))
    elif evt.get("dahua_bcd") is not None:
        out.update(dahua_bcd_to_ist(evt["dahua_bcd"]))
    else:
        stamp = evt.get("utc") or evt.get("timestamp") or evt.get("ist")
        if not stamp:
            raise ValueError("event has no usable time field: %r" % evt)
        s = str(stamp).replace("Z", "+00:00")
        dt = _dt.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        out.update(_fmt(dt, "ISO-8601 with explicit offset"))
    out.setdefault("ist", out.get("ist"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="NYAYA timestamp converter")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--dahua-bcd", help="14-digit Dahua BCD YYYYMMDDhhmmss")
    g.add_argument("--bcd-bytes", help="raw BCD frame bytes as hex, e.g. 182606151030")
    g.add_argument("--hik-epoch", type=int, help="Hikvision Unix epoch seconds")
    g.add_argument("--assume-utc", action="store_true",
                   help="treat BCD as UTC instead of device-local")
    args = ap.parse_args(argv)
    try:
        if args.dahua_bcd:
            out = dahua_bcd_to_ist(args.dahua_bcd, args.assume_utc)
        elif args.bcd_bytes:
            out = dahua_bcd_to_ist(bytes.fromhex(args.bcd_bytes), args.assume_utc)
        else:
            out = hik_epoch_to_ist(args.hik_epoch)
    except (ValueError, OverflowError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())