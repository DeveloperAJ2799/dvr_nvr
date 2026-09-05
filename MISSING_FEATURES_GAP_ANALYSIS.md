# DVR/NVR Forensic Platform — Detailed Gap Analysis: What's Missing vs Problem Statement

**Audit date:** 2026-09-04
**Scope:** `dvr-forensic-analyzer/` (Rust + Tauri v2 + React + Python sidecar) and `nyaya-forensics/` (earlier Tauri + Python prototype)
**Problem Statement (PS):** Unified vendor-agnostic DVR/NVR forensic analysis platform — standardized acquisition, recovery, analysis, validation, reporting across Dahua, CP Plus, Honeywell, HIKVISION, TP-Link, Godrej, Uniview, Matrix + AI analytics (face/object/motion) + MD5/SHA-256 + chain of custody + SOPs/reports.
**Verdict:** NOT fully implemented. Working foundation for cases/hashing/custody + thin working demo for 2 vendors at exported-file level. All deep forensic work (physical imaging, proprietary FS parsing, index-based recovery, true multi-cam correlation, full AI suite, one-click legal report) is missing, stubbed, or placeholder.

---

## 1. Executive Summary — Missing by Module

| # | PS Module | Status | % | What's actually there | What's missing (headline) |
|---|-----------|--------|---|----------------------|---------------------------|
| 1 | Device Identification (auto model/vendor/layout, 8 OEMs) | Partial / misleading | ~25% | 4-byte magic check on first 4 KiB (`core/device_detect.py`); folder-name substring match in Rust stubs | No model/firmware/channel/layout detection; 5 of 8 OEMs have zero byte signatures; Rust identify is filename matching only |
| 2 | Forensic Acquisition (bit-exact DD/RAW/E01, physical disk, write-block) | Partial | ~30% | Hash-only ingest of an existing file (`core/acquisition.py:acquire_raw`); streaming MD5+SHA-256 | No physical-drive listing/imaging, no image *creation*, `acquired=False` always, E01 path crashes without `libewf-python` |
| 3 | Proprietary FS & Format Parsing (DHFS/HIKFS/WFS/UFS, `.dav`/`.hik` decode, metadata) | Stub | ~10% | `plugins/dahua_wrapper.py` + `hikvision_wrapper.py` scan for `DHAV`/`HKVI`/`MPEG-PS` markers and remux via FFmpeg; `GenericExportedParser` lists `.mp4` files | All 8 Rust `VendorParser`s return empty (`parsers/stubs.rs`); no superblock/volume/index/channel-dir parser; no per-frame header demux; no metadata (camera/time/event) extraction |
| 4 | Deleted/Damaged Recovery | Generic carver only | ~20% | `plugins/recovery.py:carve` — H.264/H.265 NAL scan + cached SPS/PPS prepend + FFmpeg remux | No FS index-carving, no deleted-file reconstruction (name/channel/time), fixed 2 MB carve, 256 KB dedup heuristic, no fragmentation/GOP reassembly, Rust `recovery/carving.rs` is placeholder |
| 5 | Timestamp Normalization + Timeline + Multi-Camera Correlation | Manual CLI + mock UI | ~15% | `core/timestamps.py` converts a hand-typed BCD string / epoch int to IST; `src/pages/Timeline.tsx` has hardcoded `DEFAULT_EVENTS` + client-side ±window filter | No automatic timestamp extraction from DHAV/HKVI packets, no drift/sync correction, no backend correlation engine, Rust `timeline/timeline.rs` is `placeholder()` |
| 6 | AI Analytics (face + object + motion) | Partial | ~35% | `ai/analytics.py`: motion (OpenCV frame-diff) works; object has YOLOv8n-if-installed else contour fallback; face has YuNet/Haar code path | `ultralytics` not in installed env (falls back to `moving_subject` boxes); face model files (`models/*.onnx/*.xml`) not bundled; UI `Analytics.tsx` only exposes motion/object, no face; Rust `analytics/motion.rs`, `object_detection.rs`, `face_detection_stub.rs` are placeholders; detections use wall-clock, not DVR timebase |
| 7 | Integrity (MD5+SHA-256) + Chain of Custody | Strong foundation | ~85% | Streaming dual-hash in Python + Rust; hash-chained JSONL custody log (`core/audit.rs:append_to_chain_of_custody`, `verify_chain`) with tamper/delete tests | `verify_chain_of_custody` Tauri command (`commands/mod.rs:229`) does NOT call `verify_chain()` — it counts rows and returns `valid:true` always; custody events for extract/recover/analytics are not auto-recorded |
| 8 | Reporting + Legal (65B IEA / 63 BSA certificate, standardized PDF/HTML/JSON) | Script only, not integrated | ~40% | `report/pdf_report.py:build_pdf` — 7-section PDF with cert paragraph + limitations | Expects hand-made `case.json`; chain file read as plain JSON array (real chain file is JSONL — `json.load` fails); Rust `report/html_report.rs`, `json_export.rs` are thin/placeholder; UI `Reports.tsx` wired but inherits those bugs; no HTML/JSON export wired to case DB |
| 9 | SIH Deliverables (OEM matrix, test image, arch doc, prototype, SOP, validation, manual, final report) | Docs exist in old folder only | ~35% | `nyaya-forensics/docs/` has `OEM_Comparative_Analysis.md`, `SIH_PS_Requirement_Matrix.md`, `Standard_Operating_Procedure.md`, `User_Manual.md`, `Validation_Report.md`, `NYAYA_Forensics_SIH_Report.html` | No bundled synthetic DVR test image (only `test_data/sample.dav` + `test_clip.mp4`); no validation benchmarks with ground truth; SOP/manual describe aspirational flow, not actual clicks; no system-architecture doc for `dvr-forensic-analyzer`; two repos not unified |

---

## 2. OEM Coverage Matrix — What's Missing Per Vendor

PS requires at least 5–6 of: Dahua, CP Plus, Honeywell, HIKVISION, TP-Link, Godrej, Uniview, Matrix.

| OEM | Magic/signature in code? | Parser? | Decode? | Verdict |
|-----|--------------------------|---------|---------|---------|
| Dahua | Yes — `DHAV` at offset 0 (`core/device_detect.py:29`, `plugins/decoder.py:76`) | Marker-scan only (`plugins/dahua_wrapper.py:57` — groups `DHAV` hits within 2 MB, cuts +512 KB, FFmpeg `-f dhav`) — no DHFS superblock/index/channel parse | FFmpeg `dhav` demuxer attempt, then libx264 re-encode fallback | Demo-level only. Missing: DHFS 4.1 master-block/volume/channel-dir parse, per-frame DHAV header strip, timestamp/channel extraction |
| HIKVISION | Yes — `HKVI` at offset 0 (`device_detect.py:36`, `decoder.py:78`) | Marker-scan only (`plugins/hikvision_wrapper.py:57` — `HKVI` + `00 00 01 BA` scan, same 2 MB grouping) | Copy-remux then re-encode | Demo-level only. Missing: HIKFS sysinfo/data-sector parse, HKVI frame-header parse, MPEG-PS map, event tables |
| Uniview | Weak — `WFS\x00` at offset 0 (`device_detect.py:44`); `WFS` prefix in `decoder.py:82` | Rust `UniviewParser` is stub (`parsers/stubs.rs:148` — matches folder name containing `unv`); no Python WFS wrapper at all | Falls through to `auto` FFmpeg path | Effectively missing. No WFS 0.4 superblock/index parser |
| CP Plus | None — no magic bytes | Rust `CpPlusParser` stub matches folder name `cpplus` (`stubs.rs:158`); UI `Extraction.tsx:144` just routes CP Plus button to Dahua parser | Reuses Dahua path (CP Plus is Dahua OEM, but no proof/branch) | Missing as independent vendor. No model map, no validation that CP Plus layout == Dahua |
| Honeywell | None | Rust `HoneywellParser` stub matches `honeywell`/`hwl` in filename (`stubs.rs:166`) | None | Completely missing |
| TP-Link | None | Rust `TpLinkParser` stub matches `tplink` in filename (`stubs.rs:176`) | None | Completely missing |
| Godrej | None | Rust `GodrejParser` stub matches `godrej` (`stubs.rs:184`); UI routes Godrej button to Hikvision parser (`Extraction.tsx:68`) | Reuses Hikvision path, unvalidated | Missing as independent vendor |
| Matrix | None | Rust `MatrixParser` stub matches `matrix`/`mtx` (`stubs.rs:193`); UI routes Matrix to Hikvision parser | Reuses Hikvision path, unvalidated | Missing as independent vendor |
| Generic MP4 | N/A | `parsers/generic_exported.rs:11` — only parser that actually returns `Recording`s (extension match on `.mp4/.mkv/.avi/.mov`) | Pass-through (no transcode, hashes empty — `generic_exported.rs:137` sets `md5/sha256=""`) | Only "working" Rust parser, and it handles the trivial case (already-exported files) |

Net: **2 of 8 vendors have a byte signature + demo path; 1 has a weak signature; 5 have filename-substring stubs only.** PS bar (5–6 real vendors) is not met.

---

## 3. Module-by-Module: Required vs Actual vs Missing

### M1 — Device Identification (PS: "automatically identify DVR models")

**Required:** vendor + model + firmware + channel count + storage layout + confidence, from raw image or export folder.
**Actual:**
- `core/device_detect.py:78` — `_match()` compares first 4 bytes against 5-entry table. Returns `Unknown` otherwise. Folder mode (`detect_folder`) stops at first file with a known 4-byte hit.
- `src-tauri/src/parsers/stubs.rs:33` — `identify()` never reads bytes; checks if folder/file *name* contains `dh/hik/unv/cpplus/honeywell/tplink/godrej/matrix`.
- `src/pages/Extraction.tsx:39` — `handleDetectVendor` displays `vendor/confidence/hex_head/note` only. No model/channel/firmware fields exist in `IdentificationResult` (`parsers/base.rs:9`).
**Missing:**
1. No DVR model database / firmware fingerprint table.
2. No partition/FS detection (DHFS vs HIKFS vs WFS vs ext4 vs FAT) — no superblock magic beyond offset 0.
3. No channel-count / disk-count / capacity inference.
4. No confidence calibration; `0.95` is hardcoded per signature.
5. No fallback chain (e.g., extension + entropy + frame-marker density).
6. `sidecar.py:67` dispatches `detect` with `--file` only; folder scan via `--folder` is unreachable from UI.

### M2 — Forensic Acquisition (PS: "create forensic images, extract videos and metadata")

**Required:** bit-exact physical-disk → DD/RAW/E01 image with write-blocking, hashing during imaging, manifest, re-verification.
**Actual:**
- `core/acquisition.py:49` — `acquire_raw()` opens an *already existing* file read-only, streams 4 MiB hashes, returns `acquired:False` with note "No copy made".
- `acquire_e01()` (`acquisition.py:67`) needs `import libewf`; `requirements.txt:5` pins `libewf-python==20240506` but env lacks it → returns `{"error":"libewf-python not installed"}`.
- Rust `core/evidence.rs` ingest hashes + stores row; `verify_evidence` re-hashes.
**Missing:**
1. No physical-drive enumeration (`\\.\PhysicalDriveX`, `/dev/sdX`, WMI/IOCTL) — `acquisition.py` takes `--image` path only.
2. No imaging engine (no `dd`/EWF writer call; requirements list `dd` as "reused" but nothing invokes it).
3. No write-blocker detection/enforcement or read-only device open flags.
4. No segmented/chunked output, no compression, no E01 metadata (examiner/notes/hash segments).
5. No acquisition log (speed, bad sectors, retry map) and no resume.
6. UI has no "Acquire Disk" flow — `Evidence` page ingests files, `Recovery`/`Extraction` pages expect a path string.

### M3 — File System & Format Parsing (PS core: "parse proprietary file systems, decode proprietary formats")

**Required:** DHFS (Dahua/CP Plus), HIKFS (Hikvision/Godrej/Matrix), WFS (Uniview), Honeywell/TP-Link variants; per-frame demux to MP4; per-clip metadata (camera, start/end, event type, codec).
**Actual:**
- Trait exists (`parsers/base.rs:96` — `identify/parse_filesystem/extract_videos/recover_deleted/validate_output`) and registry (`parsers/registry.rs`) — good scaffolding.
- `parse_filesystem` for all 8 OEMs returns `recordings:[]` + warning `stub; no recordings parsed` (`stubs.rs:82`).
- Python wrappers do marker-scan + FFmpeg remux (see §2). `plugins/decoder.py:103` tries `-c copy` with `-f dhav` when header is DHAV, then full libx264 re-encode, then `--strip` fallback. Re-encode alters pixels (forensically lossy) but is the only path that usually succeeds.
**Missing:**
1. DHFS: superblock, volume map, channel directories, DHAV frame-chunk walk, per-frame header (magic/len/timestamp/channel) parsing — none implemented.
2. HIKFS: sysinfo block, data sectors, HKVI frame headers, MPEG-PS pack mapping — none implemented.
3. WFS 0.4: superblock + index table — none implemented.
4. Honeywell / TP-Link / Godrej / Matrix native structures — entirely absent.
5. No `Recording` population from real bytes: `generic_exported.rs:184` fabricates `start/end=now()`, `duration=0`, `codec=unknown`, `camera_id=filename`.
6. External tools cited in `requirements.txt:20-21` (`hikextractor.py`, `dhfs_extractor`) are not vendored; old audit's "ghost dependency" bug is fixed only by *not calling them anymore* — capability was dropped, not replaced.
7. No handling of proprietary audio (G.711/ADPCM), subtitles/KLV, or encryption/scrambled streams.

### M4 — Recovery of Deleted/Damaged Recordings (PS: "recover deleted footage")

**Required:** carve from unallocated space *with* FS-index reconstruction (names/channels/timestamps), playable output, hash per candidate, false-positive control.
**Actual:**
- `plugins/recovery.py:100` — scans 2 MiB windows with 256 B carry for SPS/PPS/IDR (H.264) + VPS/SPS/PPS/IDR (H.265); caches first SPS/PPS (64 B each) and prepends to bare IDRs; dedups hits within 256 KB; carves fixed 2 MB per candidate; `remux_to_mp4()` tries `-c copy` then `-r 25` + libx264 re-encode; hashes raw carve.
- Rust `recovery/carving.rs:10` returns empty `offsets:[]`.
**Missing:**
1. No DHFS/HIKFS/WFS index-table carving — cannot recover filename, camera, or true start/stop time; every candidate gets `offset_hex` + synthetic `carved_NNN.mp4` name.
2. Fixed 2 MB carve truncates long clips and pads short ones with next-stream bytes; no GOP-boundary stop (no SPS→next-SPS cut), no PTS-based grouping (PS explicitly wants PTS grouping).
3. SPS/PPS cache is global-first-found (64 B slice) — wrong parameters for multi-resolution streams; no per-candidate SPS/PPS search backward from IDR.
4. No H.265 VPS handling beyond one NAL (`0x40`); no `0x42/0x44` validation; no H.264/H.265 entropy/validation filter → high false positives on random data.
5. No damaged-file repair (moov rebuild, index regeneration, timestamp interpolation).
6. No recovery-rate metrics / ground-truth harness (`Validation_Report.md` exists in old folder but has no measured numbers against these carvers).

### M5 — Timestamps, Timeline, Multi-Camera Correlation (PS: "normalize timestamps, correlate events across cameras")

**Required:** extract proprietary BCD/epoch/PTS times per frame, normalize to UTC/IST, correct drift, build unified timeline, ±10 s cross-camera correlation.
**Actual:**
- `core/timestamps.py:36,57` — pure functions `dahua_bcd_to_ist("YYYYMMDDhhmmss")` / `hik_epoch_to_ist(int)`; CLI takes hand-typed values. Correct IST math, auditable raw+normalized output.
- `src/pages/Timeline.tsx:16` — six hardcoded `DEFAULT_EVENTS`; "Run Multi-Cam Correlation" is O(n²) delta check on those constants; "Reset/Sync" restores constants. No fetch from backend/case DB.
- `ai/analytics.py:31` — `_format_timestamp()` uses `datetime.now(timezone.utc) + seconds` — event times float with analysis time, not recording time.
**Missing:**
1. No automatic timestamp extraction: nothing reads DHAV offset-16 BCD or HKVI offset-12 epoch from actual packets (docstring in `timestamps.py:7` describes the layout but no caller parses it).
2. No PTS/DTS extraction via FFprobe, no timezone/drift/DST correction, no NTP-offset handling.
3. No backend timeline store population: `Recording.start_time_utc` is `now()` for generic files, empty for OEM stubs.
4. No real correlation engine (track stitching, camera-topology, direction-of-travel, confidence scoring); UI correlation is a demo on fake data.
5. Rust timeline module is `pub fn placeholder() {}` (`timeline/timeline.rs:1`, `timeline/mod.rs` re-export only).

### M6 — AI Analytics: Face, Object, Motion (PS explicitly requires all three)

**Required:** face + object + motion detection mapped to DVR timestamps.
**Actual:**
- `ai/analytics.py:38` `face_detect()` — tries YuNet ONNX then Haar cascade; `motion_detect()` (`:140`) — frame-diff + 2% ratio gate; `object_detect()` (`:212`) — YOLOv8n if importable, else contour fallback labeled `moving_subject` @ 0.78.
- `sidecar.py:73` dispatches `motion/object/face`.
**Missing:**
1. Face models absent: `ai/models/` contains no `.onnx`/`.xml` in repo → `face_detect` returns `{"error":"Face detection models missing"}` on clean checkout.
2. `ultralytics==8.3.201` pinned but not installed in test env → object mode silently degrades to motion-contours mislabeled as objects (precision/recall unusable for court).
3. UI `Analytics.tsx:6` — `type AnalyticsMode = "motion" | "object"`; no face option, no bounding-box overlay, no frame preview, no threshold tuning.
4. `src/ipc.ts:161` — `runAiAnalytics(mode: "motion"|"object")` excludes `"face"` even though sidecar supports it.
5. Rust `analytics/motion.rs`, `object_detection.rs`, `face_detection_stub.rs` are all `placeholder()`.
6. No timestamp mapping: detections carry `seconds=frame/fps` + wall-clock UTC, never DVR packet time; no export of crops/snapshots with hashes.
7. No model versioning, no confidence calibration, no eval metrics.

### M7 — Integrity, Chain of Custody, Validation (PS: "hashes, chain-of-custody, validation")

**Required:** MD5+SHA-256 everywhere, tamper-evident custody, re-verification, output validation.
**Actual (strongest area):**
- Dual hash on ingest/extract/carve/decode (`acquisition.py`, `decoder.py:36`, `recovery.py:52`, `evidence.rs`, `hasher.rs`).
- `core/audit.rs:44` — JSONL hash chain `SHA256(seq|prev_hash|canonical_event)`; genesis hash; legacy-array migration; read-only `verify_chain()`; 5 unit tests incl. tamper/delete/corrupt cases.
**Missing / bugs:**
1. **Critical:** `commands/mod.rs:229` `verify_chain_of_custody` ignores `verify_chain()` and returns `valid:true` with `total_entries = audit_events row count`. Tampered JSONL still reports "Chain Intact." UI `Reports.tsx:18` calls this command, so the green checkmark is meaningless until wired to `AuditLogger::verify_chain()`.
2. Custody events are recorded for ingest/verify only; extract/decode/recover/analytics successes do not append entries (sidecar calls bypass `AuditLogger`).
3. `Recording`/`ExtractedFile` validation (`validate_output`) is `valid:true` stub for OEM parsers; generic parser only checks non-empty.
4. No write-once enforcement on evidence dir; no OS-level immutability flag.

### M8 — Reporting, SOPs, Docs, Legal Defensibility (PS: "generate reports ... legally defensible")

**Required:** one-click standardized PDF/HTML/JSON report per case + 65B/63 certificate + SOP + manual + validation report.
**Actual:**
- `report/pdf_report.py:27` builds a 7-section ReportLab PDF from a `case.json` dict + optional chain file; includes 65B/63 paragraph, limitations, examiner statement.
- `src/pages/Reports.tsx:26` wires case-dir `case.json` + `chain_of_custody.json` → `generatePdfReport`.
**Missing / bugs:**
1. `pdf_report.py:92` does `json.load(chain_path)` but real chain file is JSONL (`audit.rs:173` writes one JSON object per line) → `json.load` raises on any real case; report generation fails exactly when custody exists.
2. `case.json` schema expected by the script (`evidence/extracted/recovered/timeline` keys) is never written by `CaseManager` — no code produces that file, so the button needs a hand-crafted JSON.
3. Counts-only sections: extracted/recovered/timeline sections print `Total: N`, no per-file tables (hashes, offsets, timestamps, examiner notes).
4. No HTML/JSON exporters wired (`report/html_report.rs`, `json_export.rs` are placeholder/thin; `sidecar.py` has no `html`/`json-report` subcommand).
5. Certificate block is static text — missing examiner name/signature/date, device/method details, hash-verification table, per-exhibit annexures required for 65B/63.
6. `nyaya-forensics/docs/*.md` (SOP, manual, OEM matrix, validation) describe the *intended* tool, not the shipped clicks; no architecture doc for `dvr-forensic-analyzer`; no measured validation numbers.

---

## 4. Frontend / Wiring Gaps (Why the Prototype Feels Broken)

1. `src/pages/Analytics.tsx` — no face mode; `src/ipc.ts:161` type blocks it even though backend supports `face`.
2. `src/pages/Timeline.tsx` — 100% mock data; no `api.*` call except `useActiveCase`; "correlation" runs on constants.
3. `src/pages/Extraction.tsx:67` — vendor routing is `if hikvision/matrix/godrej → hik parser else → dahua parser`; Uniview/CP Plus/Honeywell/TP-Link buttons don't exist; Uniview images go down the Dahua path.
4. `src/pages/Parsers.tsx` (not excerpted) lists registry entries — all 8 show "stub; full parsing not available yet" with 0 recordings; easily mistaken for breakage.
5. `src/pages/MediaLibrary.tsx`, `Recovery.tsx:184` — `hex(c.offset_bytes)` references undefined `hex` in render scope for some rows (local `hex()` defined at file bottom works, but `c.offset_hex` missing on some paths → `0x0` shown).
6. No progress streaming for multi-GB images: sidecar `timeout=7200` with single JSON at end; UI shows spinner with no %, no cancel.
7. Python module imports assume `cwd=HERE` + `python -m plugins.x` — packaged Tauri binary has no interpreter; no bundled runtime plan.

## 5. Dependencies & Environment Gaps

| Dependency | Declared | Reality | Impact |
|------------|----------|---------|--------|
| `libewf-python` | `requirements.txt:5` | Not installed; `acquire_e01` returns error dict | E01 ingest dead |
| `ultralytics` | `requirements.txt:9` | Not installed in test env | Object detection = contour fallback |
| `opencv-python-headless` | `requirements.txt:10` | Required for all 3 AI modes; missing → `{"error":"opencv-python not installed"}` | AI dead without manual pip |
| Face models | Expected at `ai/models/*` | Directory absent from repo | Face mode always errors |
| `reportlab` | `requirements.txt:12` | Needed for PDF; missing → sidecar `pdf` fails | Reporting dead without manual pip |
| `ffmpeg/ffprobe` | "Reused, not reimplemented" | `_find_ffmpeg()` returns None → decode/recovery return `ffmpeg not found` | All video output dead without system FFmpeg |
| `hikextractor.py`, `dhfs_extractor` | Cited `requirements.txt:20-21` | Not vendored, no longer called | No loss today, but no replacement capability either |
| Node/Rust toolchains | `package.json`, `src-tauri/Cargo.toml` | Needed to build Tauri app; no prebuilt binary in repo | Reviewers must build from source |

## 6. SIH Deliverables Checklist — What's Still Owed

- [x] Draft OEM comparative analysis (`nyaya-forensics/docs/OEM_Comparative_Analysis.md` + HTML report) — needs refresh for 8-OEM byte-signature table + DHFS/HIKFS/WFS structure diagrams.
- [x] Draft architecture doc (HTML report) — needs standalone `ARCHITECTURE.md` for `dvr-forensic-analyzer` (Rust core + sidecar contract + data flow diagram).
- [ ] Single unified functional prototype (unify the two folders; delete or archive the loser; one README; one build).
- [ ] Synthetic DVR test images with ground truth (e.g., 50 MB DHFS-like + HIK-like images with known clip count/offsets/timestamps) + a `test_data/README.md` explaining expected outputs. (Checked-in `test_data/` fixtures were removed; `test_sidecar.sh` now synthesizes its own throwaway input at runtime.)
- [ ] Real SOP (`docs/SOP.md`): examiner steps (acquire → detect → extract → normalize → correlate → AI → verify → report) mapped to actual buttons/commands.
- [ ] Validation report with numbers: detection precision, extraction success rate, carve recall/false-positive rate, hash re-verify rate, report-generation success — measured on the synthetic images.
- [ ] User manual with screenshots for each page + error catalog (ffmpeg missing, models missing, libewf missing, no signatures found).
- [ ] Final project report + demo script + slide deck outline.

## 7. Prioritized Build Order to Close the Gaps

1. **Unify + stabilize:** pick one app root; wire `verify_chain_of_custody` → `AuditLogger::verify_chain()`; fix `pdf_report.py` JSONL read; generate real `case.json` from SQLite; add face to `Analytics.tsx` + `ipc.ts`.
2. **Real acquisition:** physical-drive list + `dd`-based imaging with progress + write-block check + manifest; or explicitly scope to "logical ingest only" and update PS claims.
3. **Two real FS parsers first (DHFS + HIKFS):** superblock → volume → channel → frame-chunk walk; emit `Recording`s with true start/end/channel/event; demux per-frame headers (don't just remux whole blobs).
4. **Index-aware recovery:** carve FS index tables first, fall back to NAL carve with GOP-boundary cut + backward SPS/PPS search + PTS grouping; report recall/FP on synthetic images.
5. **True timeline:** extract packet timestamps during parse, store per-recording + per-AI-event DVR time, backend correlation query (±10 s join across cameras), UI reads from DB not constants.
6. **AI completion:** vendor `yolov8n.pt` or document download; bundle Haar cascade (small) + optional YuNet; snapshot crops with hashes; map every event to DVR timebase.
7. **Legal hardening:** per-exhibit hash tables in PDF, examiner signature block, HTML/JSON exports, custody entries for every sidecar success, read-only evidence enforcement.
8. **Docs + validation:** synthetic images, measured validation report, SOP/manual/architecture, final report.

---

## 8. File-Level Evidence Index (where each claim was verified)

- Identification: `dvr-forensic-analyzer/core/device_detect.py:26-67,78-87` · `src-tauri/src/parsers/stubs.rs:33-80,130-200` · `src-tauri/src/parsers/base.rs:9-14` · `src/pages/Extraction.tsx:39-56`
- Acquisition: `dvr-forensic-analyzer/core/acquisition.py:26-64,67-103` · `src-tauri/src/core/evidence.rs` · `src-tauri/src/core/hasher.rs`
- Parsing/decoding: `dvr-forensic-analyzer/plugins/decoder.py:68-156` · `plugins/dahua_wrapper.py:57-140` · `plugins/hikvision_wrapper.py:57-153` · `src-tauri/src/parsers/generic_exported.rs:73-117,168-207` · `src-tauri/src/parsers/registry.rs`
- Recovery: `dvr-forensic-analyzer/plugins/recovery.py:34-41,100-233` · `src-tauri/src/recovery/carving.rs:10-16` · `src-tauri/src/recovery/mod.rs` · `src/pages/Recovery.tsx:37-60`
- Time/timeline: `dvr-forensic-analyzer/core/timestamps.py:28-68` · `ai/analytics.py:31-35` · `src/pages/Timeline.tsx:16-65` · `src-tauri/src/timeline/timeline.rs:1`
- AI: `dvr-forensic-analyzer/ai/analytics.py:38-137,140-209,212-328` · `src/pages/Analytics.tsx:6,98-112` · `src/ipc.ts:161-165` · `src-tauri/src/analytics/motion.rs:1` · `object_detection.rs:1` · `face_detection_stub.rs:1` · `sidecar.py:73-75`
- Custody/reporting: `src-tauri/src/core/audit.rs:44-77,92-129,155-236,240-320` · `src-tauri/src/commands/mod.rs:229-247` · `dvr-forensic-analyzer/report/pdf_report.py:27-132` · `src-tauri/src/report/html_report.rs:1` · `src/pages/Reports.tsx:14-54` · `sidecar.py:31-51`
- Deps/docs: `dvr-forensic-analyzer/requirements.txt:1-21` · `nyaya-forensics/docs/` (6 files) · former `dvr-forensic-analyzer/test_data/` removed (mock cull 2026-09-04; smoke script synthesizes input in `$TMPDIR`)
