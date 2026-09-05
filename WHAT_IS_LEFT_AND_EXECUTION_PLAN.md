# NYAYA Forensics — What Is Left & Complete Execution Plan

**Project:** NYAYA Forensics — Tauri Desktop App for Police DVR/NVR Forensic Recovery  
**Target Event:** Smart India Hackathon (SIH)  
**Target OEMs:** Dahua, CP Plus, Hikvision, Godrej, Matrix, Uniview, Honeywell, TP-Link  
**Baseline Completion:** ~30% (Split between `nyaya-forensics/` and `dvr-forensic-analyzer/`)  
**Target Completion:** 100% Fully Functional, Court-Admissible Desktop Application  

---

## 1. Executive Summary: Current State vs. What's Left

| Layer / Component | What Is Currently Built | What Is Left to Build | Status |
|---|---|---|:---:|
| **Workspace Architecture** | Two fragmented folders (`nyaya-forensics` & `dvr-forensic-analyzer`) with conflicting build setups and duplicate scripts. | Unify into single stable Tauri v2 app; fix `.git` submodule corruption; clean single pipeline. | 🔴 0% Unified |
| **Layer 1: Device Detection** | Simple 4KB–20MB signature check for 12 hardcoded strings/magic bytes. ASCII "CPPLUS" and "GODREJ" checks. | True superblock parser (DHFS, HIKFS, WFS); OEM hierarchy map (CP Plus → Dahua; Godrej/Matrix → Hikvision); channel/capacity inference. | 🟡 30% Left |
| **Layer 2: Acquisition & Hashing** | Streaming MD5 + SHA-256 calculation; basic copy of existing `.dd` files; Windows disk sizing script. | Real physical drive acquisition (`\\.\PhysicalDriveX`) with write-block check; error-tolerant raw sector streaming (`noerror,sync`); native E01 support or fallback. | 🟡 40% Left |
| **Layer 2b: Video Demuxing** | Stripping 32 or 48 bytes from file start (offset 0) via Python. | True DHAV per-frame packet demuxer (`ffmpeg -f dhav -i ...`); HKVI/MPEG-PS stream unwrapper; multi-channel audio (G.711/ADPCM) handling. | 🔴 75% Left |
| **Layer 3: Proprietary FS Parsing** | Python wrappers looking for missing external repos; Rust parsers returning empty stubs. | Bundle real open-source parsers (`drcrecoverydata/dvr_dahua`, Hikvision parser) in `vendor/`; extract clip metadata (channel, timestamps, resolution) directly from disk blocks. | 🔴 85% Left |
| **Layer 4: Recovery & Carving** | Naive Python H.264 NAL scanner clustering into 2MB blocks; Rust `carving.rs` writes dummy `size: 0` records. | Smart H.264/H.265 GOP carving with SPS/PPS extraction; recover deleted clip indexes from unallocated DHFS/HIKFS tables; stitch fragmented runs. | 🔴 75% Left |
| **Layer 5: Timeline & Clock Sync** | Dahua BCD & Hikvision Epoch converters; ±10s Python pairing script; basic `vis-timeline` page. | Automatic timestamp extraction from carved video packets; time-drift calibration; feeding real case evidence into `vis-timeline` UI. | 🟡 45% Left |
| **Layer 6: Chain of Custody** | Append-only SHA-256 hash-chained JSONL ledger in Python (`custody.py`) & Rust (`audit.rs`). | Automatic logging hook for every UI action (ingest, carve, detect, export); fix JSONL vs JSON parsing bug in report engine; tamper-verification UI badge. | 🟢 15% Left |
| **Layer 7: AI Search & Reporting** | YOLOv8n script (`detector.py`) with MOG2 fallback; standalone 9-section ReportLab PDF script (`pdf_gen.py`). | Bundle offline YOLOv8n & YuNet face weights; UI search filter for Person/Vehicle; one-click PDF generation pulling directly from active case SQLite database. | 🟡 40% Left |

---

## 2. Architectural Unification Plan (Immediate Prerequisite)

The workspace currently contains two disjointed folders. They must be merged into one cohesive application:

```
d:\axn\trc\nyaya-forensics/          <-- Master Application Root
├── src-tauri/                       <-- Tauri v2 (Rust shell, IPC, Fast Hasher, SQLite DB)
│   ├── src/
│   │   ├── commands.rs              <-- Unified IPC command handlers
│   │   ├── db.rs                    <-- SQLite Case & Evidence Schema
│   │   └── lib.rs                   <-- Tauri plugins & registration
│   └── tauri.conf.json
├── src/                             <-- React 18 + Tailwind CSS + Lucide Icons + vis-timeline
│   ├── pages/
│   │   ├── Dashboard.tsx            <-- System health, disk drives, quick actions
│   │   ├── Acquisition.tsx          <-- Physical drive picker, bit-exact copy, dual hashing
│   │   ├── Extraction.tsx           <-- OEM auto-detect, filesystem parsing, channel list
│   │   ├── Recovery.tsx             <-- Deleted footage carving, GOP preview, playable clips
│   │   ├── Timeline.tsx             <-- vis-timeline interactive multi-camera view
│   │   ├── AiSearch.tsx             <-- Person / Vehicle / Face search on evidence
│   │   └── Reports.tsx              <-- §65B Certificate preview, 1-click PDF download
│   └── ipc.ts                       <-- Strongly typed Tauri IPC wrapper
├── core/                            <-- Python Forensic Engine (Called via Tauri Sidecar)
│   ├── acquisition.py               <-- Physical drive & raw image streaming + dual-hash
│   ├── vendor_detect.py             <-- 8-OEM magic-byte & superblock detector
│   ├── decoder.py                   <-- FFmpeg DHAV / HKVI demuxer and MP4 remuxer
│   ├── recovery.py                  <-- Smart GOP H.264/H.265 carver with SPS/PPS
│   ├── timestamps.py                <-- BCD / Epoch / UTC / IST normalization
│   ├── timeline.py                  <-- Multi-camera ±10s correlation engine
│   └── custody.py                   <-- Append-only SHA-256 hash-chained JSONL ledger
├── plugins/                         <-- OEM-Specific Filesystem Parsers
│   ├── dahua_plugin.py              <-- Dahua / CP Plus DHFS 4.1 index walker
│   ├── hikvision_plugin.py          <-- Hikvision / Godrej / Matrix HIKFS parser
│   └── uniview_plugin.py            <-- Uniview WFS 0.4 parser
├── vendor/                          <-- Bundled Proven Open-Source Repositories
│   ├── dvr_dahua/                   <-- Cloned drcrecoverydata/dvr_dahua
│   └── hik_parser/                  <-- Community Hikvision disk parser
├── ai/                              <-- AI Forensic Analytics
│   ├── detector.py                  <-- YOLOv8n + Face Detection (YuNet/Haar)
│   └── models/                      <-- Pre-packaged offline weights (yolov8n.pt, yunet.onnx)
└── reporting/                       <-- Legal Reporting Engine
    └── pdf_gen.py                   <-- ReportLab Section 65B (IEA) / Section 63 (BSA) generator
```

---

## 3. Detailed Breakdown of What Is Left to Build

### Layer 1: Device Detection & Multi-OEM Identification
- **Current Deficit:** Only matches simple byte strings. Does not understand that CP Plus runs Dahua DHFS, or that Godrej/Matrix run Hikvision HIKFS.
- **What Is Left to Build:**
  1. **Superblock Deep Scan:** Scan offsets `0x0`, `0x200`, `0x400`, `0x1000`, `0x200000` for:
     - Dahua / CP Plus: `DHFS` (Dahua Hard Disk File System), `DHAV` packet streams.
     - Hikvision / Godrej / Matrix: `HIKVISION`, `HKVI`, `HIKFS`, `MPEG-PS` (`00 00 01 BA`).
     - Uniview: `WFS\x00` (WFS 0.4), `UFS\x00`.
     - Honeywell / TP-Link: `HWSM`, `VIGI`, standard embedded FAT/ext4 with proprietary stream layouts.
  2. **Model & Geometry Inference:** Read partition table headers to infer total drive capacity, sector size, and configured channel count (e.g., 4-ch, 8-ch, 16-ch, 32-ch).
  3. **Auto-Routing Engine:** Feed detection result into the backend to automatically activate the matching parser without requiring manual user selection.

### Layer 2 & 2b: Bit-Exact Acquisition & Stream Demuxing
- **Current Deficit:** Only hashes files already saved on disk. Video decoding naively strips 32 bytes from file offset 0, which corrupts real DHAV multi-frame files.
- **What Is Left to Build:**
  1. **Physical Drive Enumeration & Imaging:**
     - Query `Win32_DiskDrive` on Windows to list physical devices (`\\.\PhysicalDrive0`, `\\.\PhysicalDrive1`).
     - Read-only streaming acquisition using 4 MiB buffers with bad sector recovery (`noerror,sync` behavior in Python/Rust).
     - Write-blocking validation: Verify drive is mounted read-only and emit warning if hardware write-blocker is not detected.
  2. **DHAV Per-Frame Demuxer:**
     - Instead of byte-stripping, invoke FFmpeg's native `dhav` demuxer:
       ```bash
       ffmpeg -y -f dhav -i input.dav -c copy -movflags +faststart output.mp4
       ```
     - For fragmented/damaged streams, build a frame-level parser that strips 24/32-byte DHAV headers preceding each frame while preserving standard H.264/H.265 NAL units.
  3. **Dual Cryptographic Verification:** Calculate MD5 and SHA-256 simultaneously in a single read pass and immediately record the genesis entry into `custody.jsonl`.

### Layer 3: Proprietary Filesystem Parsing (The Core Challenge)
- **Current Deficit:** All 8 Rust parsers in `parsers/stubs.rs` return empty arrays. `dahua_wrapper.py` tries to call `vendor/dvr_dahua/Python_3.12.3_Dahua_23.4.24.py` which was never cloned into the repository.
- **What Is Left to Build:**
  1. **Vendor Repository Integration:**
     - Clone `drcrecoverydata/dvr_dahua` directly into `vendor/dvr_dahua/`.
     - Adapt its non-interactive CLI so NYAYA can invoke it with disk path and output directory.
     - Bundle Hikvision open-source disk parser logic for HIKFS master sector extraction.
  2. **Pure-Python DHFS 4.1 Index Parser (Built-in Standalone):**
     - Parse DHFS Superblock and Volume Descriptor.
     - Extract partition table, channel allocation maps, and file record headers (Start Time, End Time, Channel Number, File Size, Sector Offset).
  3. **Export Manifest Generation:** Generate a standardized JSON manifest of all extracted recordings:
     ```json
     {
       "channel": 1,
       "filename": "CAM01_20260905_100000.mp4",
       "start_time_utc": "2026-09-05T04:30:00Z",
       "end_time_utc": "2026-09-05T04:45:00Z",
       "duration_sec": 900,
       "codec": "H.264",
       "sha256": "..."
     }
     ```

### Layer 4: Forensic Recovery & Smart Carving
- **Current Deficit:** Scans for H.264 IDR slices without extracting or caching SPS/PPS, making carved videos unplayable. Rust carver writes zero-byte dummy files.
- **What Is Left to Build:**
  1. **SPS/PPS Parameter Set Preservation:**
     - In H.264, an IDR frame (`00 00 00 01 65`) cannot be decoded without Sequence Parameter Set (`00 00 00 01 67`) and Picture Parameter Set (`00 00 00 01 68`).
     - In H.265, extract VPS (`40`), SPS (`42`), and PPS (`44`).
     - Carver must cache the nearest valid parameter sets and prepend them to every carved IDR frame chunk.
  2. **GOP-Level Stitching & PTS Boundary Grouping:**
     - Group consecutive NAL units into complete Groups of Pictures (GOPs).
     - Use Presentation Time Stamps (PTS) or byte proximity (< 2 MB) to stitch contiguous video fragments into playable clips.
  3. **Deleted Index Reconstruction:** Scan unallocated sectors for residual DHFS/HIKFS index tables to recover the original camera channel and timestamp of deleted footage.

### Layer 5: Multi-Camera Timeline Normalization & Temporal Correlation
- **Current Deficit:** Manual CLI string parser exists, but timeline UI currently displays hardcoded mock data. Timestamps are not linked to carved evidence.
- **What Is Left to Build:**
  1. **Automated Stream Timestamp Extraction:**
     - Extract Dahua 14-digit BCD timestamps directly from DHAV frame headers (offset 16).
     - Extract 32-bit Unix epoch from Hikvision HKVI packet headers.
     - Convert all to both UTC and Indian Standard Time (IST: UTC + 05:30).
  2. **Temporal Correlation Engine (±10s Cross-Camera Window):**
     - For any event on Camera A, search all other cameras within a ±10-second window.
     - Greedily group multi-camera events to track suspect movements (e.g., Gate 1 → Lobby → Corridor).
  3. **Dynamic `vis-timeline` Integration:**
     - Bind the React `vis-timeline` component to the real SQLite case database.
     - Display multi-channel tracks with color-coded event markers (Normal Recording, Motion Event, AI Detection, Recovered Deleted Footage).

### Layer 6: Chain-of-Custody Audit System
- **Current Deficit:** Strong logic, but `pdf_gen.py` attempts to load the JSONL file with `json.load()` (which crashes), and IPC commands in the UI don't log all actions automatically.
- **What Is Left to Build:**
  1. **Unified Auto-Logging Middleware:**
     - Automatically record an audit entry for every action: Drive Mount, Ingest, Hash Verification, Carving, Video Remuxing, AI Inference, and PDF Generation.
  2. **Tamper Verification & Badging:**
     - Expose a "Verify Ledger" button in the UI that validates the entire SHA-256 hash chain from genesis (`64 * "0"`) to the current entry.
     - Highlight any broken sequences or missing lines with cryptographic proof.
  3. **JSONL Format Consistency:** Update all Python and Rust readers/writers to strictly adhere to newline-delimited JSON (`.jsonl`).

### Layer 7: AI Search & Court-Admissible Reporting
- **Current Deficit:** Requires internet to download YOLOv8n; face detection models not bundled; PDF script requires 4 manually prepared JSON files.
- **What Is Left to Build:**
  1. **Offline AI Bundle:**
     - Bundle `yolov8n.pt` (~6 MB) and OpenCV YuNet face detection ONNX model (`face_detection_yunet_2023mar.onnx`, ~300 KB).
     - Provide person (`class 0`) and vehicle (`classes 2, 3, 5, 7`) filtering at 2 FPS sampling rate.
  2. **One-Click Court PDF Generation:**
     - Update `pdf_gen.py` to accept a single `--case-db` path (SQLite database) or auto-load the case files.
     - Format a 9-section court report:
       1. Cover Page & Case Metadata
       2. Examiner Credentials & Forensic Workstation Specs
       3. Physical Evidence & Disk Image Details
       4. Dual Hash Verification Table (MD5 + SHA-256 matching certificate)
       5. Proprietary File System & Camera Channel Allocation
       6. Recovered Deleted Footage Manifest
       7. AI Investigative Triage (Person/Vehicle sightings with timestamps)
       8. Complete Hash-Chained Chain-of-Custody Ledger
       9. **Certificate Under Section 65B of Indian Evidence Act (IEA) / Section 63 of Bharatiya Sakshya Adhiniyam (BSA)**.

---

## 4. Step-by-Step 5-Day Remediation Plan

```mermaid
graph TD
    subgraph Day 1 : Architecture & Acquisition
        A1[Consolidate into nyaya-forensics] --> A2[Fix IPC & Frontend Build]
        A2 --> A3[Implement Physical Drive Listing & Dual Hashing]
    end

    subgraph Day 2 : FS Parsing & Video Demuxing
        B1[Bundle dvr_dahua & Hikvision Parsers] --> B2[Implement FFmpeg DHAV Demuxer]
        B2 --> B3[Automated OEM Superblock Detection]
    end

    subgraph Day 3 : Recovery & Timeline
        C1[Smart H.264/H.265 GOP Carver with SPS/PPS] --> C2[Extract BCD/Epoch Timestamps]
        C2 --> C3[Wire vis-timeline to SQLite Case DB]
    end

    subgraph Day 4 : AI Analytics & Court Report
        D1[Bundle Offline YOLOv8n & YuNet Models] --> D2[One-Click §65B/§63 ReportLab PDF Generator]
        D2 --> D3[Audit Chain Auto-Logging on all UI Actions]
    end

    subgraph Day 5 : Testing, Benchmarking & Demo
        E1[Test with Synthetic Multi-OEM Images] --> E2[Verify Hash Chains & Time Offsets]
        E3[Package Tauri Installer & Prep SIH Demo]
    end

    A3 --> B1
    B3 --> C1
    C3 --> D1
    D3 --> E1
```

### Day 1: Consolidation, IPC Fixes & Physical Acquisition
- **Task 1.1:** Merge `nyaya-forensics/` and `dvr-forensic-analyzer/` into a single root folder. Clean up broken submodule indexes.
- **Task 1.2:** Ensure `npm run build` and `cargo check` compile cleanly without TypeScript or Rust warnings.
- **Task 1.3:** Complete `core/acquisition.py` with Windows `Win32_DiskDrive` enumeration and read-only physical sector copying with real-time MD5 + SHA-256 calculation.
- **Deliverable:** Working Tauri app that can detect physical disks or raw images and perform verified dual-hash ingestion.

### Day 2: Proprietary Parsing & DHAV Demuxing
- **Task 2.1:** Vendor `drcrecoverydata/dvr_dahua` in `vendor/dvr_dahua/` and wrap its batch extraction logic.
- **Task 2.2:** Build the FFmpeg DHAV demuxer pipeline (`-f dhav -c copy`) to produce clean MP4 files without losing audio or corrupting video headers.
- **Task 2.3:** Enhance `core/vendor_detect.py` to identify OEM family (Dahua/CP Plus vs. Hikvision/Godrej/Matrix vs. Uniview vs. Others) and auto-dispatch parsing.
- **Deliverable:** Ingest a Dahua `.dav` or Hikvision `.hik` disk image and extract playable MP4 files with metadata.

### Day 3: Forensic Carving & Dynamic Timeline
- **Task 3.1:** Implement SPS/PPS parameter set extraction and prepend logic in `core/recovery.py` to guarantee playable carved clips.
- **Task 3.2:** Extract embedded frame timestamps (Dahua BCD / Hikvision Epoch) and normalize to UTC and IST (`+05:30`).
- **Task 3.3:** Connect the React `vis-timeline` component to the active case SQLite database and implement the ±10s cross-camera event correlation algorithm.
- **Deliverable:** Recover deleted video fragments and visualize multi-camera playback on an interactive timeline.

### Day 4: Offline AI Analytics & Section 65B PDF Reporting
- **Task 4.1:** Bundle `yolov8n.pt` and `face_detection_yunet_2023mar.onnx` into `ai/models/` for 100% offline inference.
- **Task 4.2:** Integrate AI event markers directly into the multi-camera timeline.
- **Task 4.3:** Overhaul `reporting/pdf_gen.py` to pull data directly from the case database and generate a court-admissible Section 65B/Section 63 certificate in PDF.
- **Task 4.4:** Hook the chain-of-custody logger into all IPC commands so every action is immutably recorded in `custody.jsonl`.
- **Deliverable:** One-click PDF generation producing a defensible court report with verifiable cryptographic chain-of-custody.

### Day 5: Validation, Benchmarks & SIH Demo Preparation
- **Task 5.1:** Generate synthetic test images representing Dahua, Hikvision, CP Plus, and Uniview.
- **Task 5.2:** Run end-to-end benchmark validation: measure acquisition speed, carving recovery percentage, and hash verification accuracy.
- **Task 5.3:** Build production installer (`npm run tauri build`) for 64-bit Windows.
- **Task 5.4:** Finalize examiner Standard Operating Procedure (SOP), user manual, and judge presentation slides.
- **Deliverable:** Production-ready executable, validated test case, and full documentation package.

---

## 5. Summary Checklist of Required Deliverables

- [ ] **Unified Codebase:** Single repository with working Tauri v2 + React UI and Python sidecar.
- [ ] **8-OEM Support:** Real parsing or valid wrapper demuxing for Dahua, CP Plus, Hikvision, Godrej, Matrix, Uniview, Honeywell, and TP-Link.
- [ ] **Bit-Exact Acquisition:** Physical disk selection + dual MD5 & SHA-256 calculation.
- [ ] **Playable Video Recovery:** H.264/H.265 smart GOP carving with SPS/PPS extraction.
- [ ] **Synchronized Timeline:** Interactive `vis-timeline` with BCD/Epoch to IST normalization and ±10s correlation.
- [ ] **Offline AI Search:** Pre-packaged YOLOv8n (Person/Vehicle) and YuNet (Face) detection.
- [ ] **Tamper-Evident Custody:** SHA-256 hash-chained append-only JSONL log with verification badge.
- [ ] **Legal Reporting:** One-click Section 65B (IEA) / Section 63 (BSA) court-ready PDF.
- [ ] **Test Evidence:** Bundled synthetic test images for live jury demonstration.
- [ ] **Documentation:** SOP manual, architecture specification, and validation benchmark report.
