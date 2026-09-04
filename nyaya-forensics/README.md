# NYAYA Forensics

> **Unified vendor-agnostic DVR/NVR forensic analysis platform** — Smart India Hackathon (SIH) submission.
> Acquire, parse, recover, timeline, AI-triage and report CCTV evidence from **Dahua · CP Plus · Honeywell · TP-Link · Godrej · Uniview · HIKVISION · Matrix** in one offline desktop app.

**Stack :** Tauri v2 (Rust) + React + TypeScript + Tailwind + vis-timeline + shadcn/ui · Python 3.11 forensic sidecar (pytsk3, pyewf, ffmpeg-python, hashlib, SQLite) · ReportLab for PDFs.

---

## What's in this repo

```text
nyaya-forensics/
├─ docs/
│  ├─ NYAYA_Forensics_SIH_Report.html   # Single-file 20-section SIH report (inline CSS)
│  └─ architecture.png                    # Placeholder diagram (replace with real)
├─ core/
│  ├─ acquisition.py      # dd stream copy + MD5/SHA-256 (4 MiB chunks), python fallback
│  ├─ vendor_detect.py    # magic-bytes device ID (DHFS/HIKVISION/WFS/UNIVIEW...)
│  ├─ decoder.py          # strip 32B Dahua / 48B Hik header → ffmpeg remux to MP4
│  └─ recovery.py         # H.264 IDR (00 00 00 01 65) carving + gap grouping + remux
├─ plugins/
│  └─ dahua_wrapper.py    # subprocess wrapper around drcrecoverydata/dvr_dahua
├─ ai/
│  └─ detector.py         # YOLOv8n @2FPS (imgsz 640, conf .5) → events.json
├─ reporting/
│  └─ pdf_gen.py          # ReportLab: 9-section court PDF incl. §65B certificate
├─ src-tauri/             # Tauri v2 starter (Rust sidecar commands)
│  ├─ tauri.conf.json     # NYAYA windows, CSP, bundle
│  ├─ Cargo.toml / build.rs
│  └─ src/
│     ├─ main.rs           # thin binary → lib::run()
│     ├─ lib.rs            # 7 commands: detect_vendor, acquire_image, extract_dahua,
│     │                    #   decode_video, carve_deleted, run_ai, generate_report
│     └─ commands.rs       # python sidecar runner + get_python_info/app_info
└─ tools/
   └─ make_placeholder_png.py
```

## Quick install (Python core)

```powershell
cd nyaya-forensics
python -m pip install -r requirements.txt
```

Heavy deps are optional per module — the core pipeline (`vendor_detect.py`,
`acquisition.py`, `recovery.py`, `decoder.py`, `dahua_wrapper.py`) is
standard-library only (FFmpeg just needs to be on PATH). The AI stage needs
opencv/ultralytics; the report stage needs reportlab. `pytsk3` and
`libewf-python` (the `pyewf` module) are optional extensions — see the notes
in `requirements.txt`.

## Quick start (Tauri app)

```powershell
# desktop shell (repo root)
npm install
npm run tauri dev
```

The seven Tauri commands (`detect_vendor`, `acquire_image`, `extract_dahua`,
`decode_video`, `carve_deleted`, `run_ai`, `generate_report`) each run a Python
sidecar script via `std::process::Command` (see `commands.rs`) and surface the
JSON returned on stdout. Set `NYAYA_PYTHON` to point at a specific interpreter;
the default is `python` on Windows, `python3` elsewhere.

## Sidecar smoke tests (no GUI needed)

```bash
# 1. Vendor ID
python core/vendor_detect.py sample.dd

# 2. Acquisition (bit-exact copy + dual hash)
python core/acquisition.py sample.dd --output copy.dd --verify --save-hashfile

# 3. Deleted recovery (H.264 NAL carving)
python core/recovery.py sample.dd --workdir ./recovered

# 4. Decoder (strip vendor header → MP4)
python core/decoder.py extract.dav --header-bytes 32

# 5. AI events
python ai/detector.py out.mp4 --fps 2 --events events.json

# 6. Court-ready PDF
python reporting/pdf_gen.py --case case.json --hash hashes.json \
     --timeline timeline.json --custody custody.json --out report.pdf
```

## Design pillars

- **Reuse, don't reinvent** — existing parsers (dvr_dahua, Hikvision community
  parsers, X-Ways DHFS 4.1 logic, PhotoRec/Scalpel, FFmpeg) called via subprocess.
- **Plugin architecture** — a `BaseParser` per engine; 8 brands collapse to
  4 underlying engines (CP Plus = Dahua OEM, Godrej/Matrix = Hikvision OEM).
- **Hash-chained custody** — `custody.jsonl` where each action hashes the
  previous entry (blockchain-style) — §65B-ready.
- **Offline & lightweight** — Tauri v2 (<10 MB binary), no cloud, drag-and-drop UI.

## Legal note

For law enforcement / demonstration use. See the SIH report's §65B certificate
section for court-surrender requirements; validate according to your
jurisdiction's SOPs before production use.