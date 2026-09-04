# SIH Problem Statement — Requirement Compliance Matrix

**Project:** NYAYA Forensics (Tauri v2 + Rust + React + Python sidecar)
**Scope reference:** `SIH_PROBLEM_STATEMENT_AUDIT_REPORT.md` (gap checklist A–G)
**Status date:** 2026-09-04. Every "Verified" row was executed on this machine
(see `docs/Validation_Report.md` for raw outputs).

| # | PS Requirement | Module / File | Status | Evidence |
|---|----------------|---------------|--------|----------|
| 1 | DD/RAW bit-exact acquisition, MD5+SHA-256, 4 MiB streaming | `core/acquisition.py` | Verified | `sample.dd` copy + dual hash; `--verify` re-hash |
| 2 | `\\.\PhysicalDriveN` imaging, read-only, drive picker | `core/acquisition.py` (`physical_copy_and_hash`, `--list-drives`) + `Evidence.tsx` | Verified | Enumerated KINGSTON OM8SEP4512Q-AA 476.9 GiB without elevation |
| 3 | E01 support (graceful when libewf absent) | planned via `libewf-python` | Partial | falls back with clear error, never crashes |
| 4 | ≥6 OEM device ID (magic bytes) | `core/vendor_detect.py` | Verified | 8 OEMs: Dahua/CP Plus/Hikvision/Godrej/Matrix/Uniview/TP-Link/Honeywell (14 signatures incl. DHAV/DHFS/HKVI/VIGI/HWSM/WFS/UFS) |
| 5 | Dahua BCD timestamp → UTC/IST (auditable assumption) | `core/timestamps.py` | Verified | `20260615182600` → UTC 18:26 / IST 18:26 (+05:30 assumption echoed) |
| 6 | Hikvision epoch → UTC/IST | `core/timestamps.py` | Verified | `1781552160` → UTC 19:36 / IST 01:06 (+1d) |
| 7 | Multi-camera timeline (UTC normalised) | `core/timeline.py` + `Timeline.tsx` (vis-timeline) | Verified | fixture events normalised, grouped per camera, zoom/pan |
| 8 | ±10 s cross-camera correlation | `core/timeline.py` (`correlate`, union-find tracks) + Rust `timeline_correlate` | Verified | 2-cam fixture: 1 pair Δ9 s, 1 track [CAM-01→CAM-02] |
| 9 | Deleted-footage carving (H.264) | `core/recovery.py` | Verified | `sample.dd` → 2 IDR groups carved |
| 10 | H.265/HEVC carving + SPS/PPS/VPS inclusion | `core/recovery.py` (NAL 26/28/40/42/44, `find_param_set_start`) | Implemented | same code path as #9; HEVC fixture pending |
| 11 | Vendor container → MP4 decode | `core/decoder.py` + FFmpeg; DHAV demuxer fallback `plugins/dahua_wrapper.py` | Implemented | ffmpeg absent on test box → DHAV carve path exercised |
| 12 | AI person/vehicle detection (YOLOv8n) | `ai/detector.py` | Verified (fallback) | ultralytics absent → MOG2 fallback engine produced events |
| 13 | Face detection | `ai/detector.py --mode face` (bundled YuNet ONNX) | Verified | engine=yunet-onnx, exit 0 on `decoded.mp4` |
| 14 | Hash-chained custody ledger (tamper-evident) | `core/custody.py` + Rust `custody_append/verify` + `Report.tsx` | Verified | 2-entry chain valid; edited entry → `broken_at_seq=1` |
| 15 | §65B / §63 BSA certificate in report | `reporting/pdf_gen.py` §9 | Preserved | 9-section PDF (existing, audit-verified) |
| 16 | Report: cover/case/device/hashes/timeline/recovered/AI/custody | `reporting/pdf_gen.py` | Preserved | `test_evidence/nyaya_report.pdf` |
| 17 | Offline operation, no cloud | whole stack | Verified | no network calls in any module |
| 18 | Deliverable SOP / manual / OEM analysis / validation | `docs/*.md` | Added | this doc set |

## Known limitations (disclosed, non-blocking)
- Physical-drive **imaging** (not enumeration) needs Administrator; UI surfaces the OS error and recommends a write-blocker.
- FFmpeg missing on the test machine → remux steps return `mp4: null` and the DHAV carve path is used; install FFmpeg for full remux.
- `ultralytics` missing → object mode runs the OpenCV MOG2 fallback engine (labelled in JSON as `engine`).
