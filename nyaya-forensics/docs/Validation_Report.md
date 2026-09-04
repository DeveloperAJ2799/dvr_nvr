# NYAYA Forensics — Validation Report

**Environment:** Windows 11, Python 3.11.15, OpenCV **5.0.0**, ultralytics
**not installed** (fallback path exercised), FFmpeg **not installed**
(graceful-degradation paths exercised), Rust stable + Tauri v2.
**Date:** 2026-09-04. All commands were executed in `nyaya-forensics/`.

## 1. Build verification

| Check | Command | Result |
|---|---|---|
| TypeScript | `npx tsc -b --force` | **exit 0** |
| Rust | `cargo check` (src-tauri) | **exit 0**, `Finished dev profile` |
| Python syntax | `py_compile` of all 9 modules | **OK** |

## 2. Timestamp normalisation (`core/timestamps.py`)

| Input | Output (UTC) | Output (IST) | Assumption recorded |
|---|---|---|---|
| Dahua BCD `20260615182600` | 2026-06-15T18:26:00Z | 2026-06-15 18:26:00 IST | device-local (case tz) |
| Hik epoch `1781552160` | 2026-06-15T19:36:00Z | 2026-06-16 01:06:00 IST | absolute UTC |
| BCD bytes `182606151030` | parsed via `--bcd-bytes` | ✓ | device-local |

## 3. Custody ledger (`core/custody.py`)

- Append ×2 (ingest, carve) → verify: `valid: true, total_entries: 2`,
  head hash `6ec1c6ae…`.
- **Tamper test:** edited entry 1 in the file →
  `valid: false, broken_at_seq: 1, "entry_hash mismatch (entry modified)"`.
- Genesis `prev_hash` = 64×"0"; each `entry_hash` = SHA-256 of canonical
  entry JSON.

## 4. Device identification (`core/vendor_detect.py`)

`sample.dd` → `vendor: dahua`, magic `DHFS` @ offset 4096, confidence 0.93,
`all_hits` populated. Signature set covers 8 PS OEMs (14 signatures).

## 5. Timeline normalisation + ±10 s correlation (`core/timeline.py`)

Fixture (2 cameras, Δ9 s): `event_count: 2`, `correlated_pairs: 1`
(`delta_seconds: 9.0`), `tracks: 1` (`CAM-01 → CAM-02`, span 9 s),
`parse_errors: []`. IST conversions attached per event.

## 6. Deleted-footage carving (`core/recovery.py`)

`sample.dd` (12 MB synthetic): **2 clips** (`idr_h264`, confidence 1.0),
param-set lookback active, `signatures: H.264 65/67/68 + H.265 26/28/40/42/44`.
`mp4: null` because FFmpeg is absent on this machine (disclosed limitation;
the carve step itself succeeded).

## 7. Dahua extraction adapter (`plugins/dahua_wrapper.py`)

External `dvr_dahua` parser absent → **built-in non-interactive fallback
ran** (no more `ok:false` blocker). On the non-DHAV fixture
`wrapped.dav` it correctly reports
`"no DHAV frame magic found in image"`; DHAV-bearing images are carved into
runs and remuxed when FFmpeg is present.

## 8. Physical drives (`core/acquisition.py --list-drives`)

Enumerated without elevation:
`\\.\PhysicalDrive0 — 476.9 GiB — KINGSTON OM8SEP4512Q-AA`, plus volumes
`C:\` (237.8 GiB) and `D:\` (237.8 GiB). Imaging path opens devices
GENERIC_READ-only with FILE_SHARE_READ|WRITE (elevation required, by OS
design — surfaced as a clear error message).

## 9. AI analytics (`ai/detector.py`)

| Mode | Engine used | Result |
|---|---|---|
| `--mode objects` | `opencv_mog2_fallback` (ultralytics absent) | 5 frames analysed, 1 motion-object event, bbox emitted |
| `--mode face` | **`yunet-onnx`** (bundled model) | exit 0, 5 frames analysed, 0 faces (synthetic clip has none) |

## 10. IPC surface (Rust ↔ React)

New Tauri commands registered and type-checked:
`list_drives`, `timestamp_convert`, `timeline_correlate`,
`custody_append`, `custody_verify`, `run_ai_mode`.
Frontend wrappers added in `src/ipc.ts` and wired into
`Evidence.tsx` (drive picker + ledger), `Timeline.tsx` (correlation UI),
`Report.tsx` (chain verification), `Recovery.tsx` (FFmpeg fallback).

## Verdict
All SIH PS functional gaps identified in the audit report are implemented
and validated at the level possible on this machine (no physical evidence
HDD, no FFmpeg, no ultralytics — all three degrade gracefully and are
disclosed in the requirement matrix).
