# NYAYA Forensics — User Manual

## 1. Installation (offline-capable)
1. **Python 3.11+** with: `pip install -r requirements.txt`
   (reportlab required; opencv-python enables AI modes; ultralytics optional;
   libewf-python optional for E01).
2. **Rust stable** + Tauri v2 prerequisites (WebView2 on Windows).
3. **FFmpeg** on PATH — optional but recommended (container remux).
4. Copy `ai/models/face_detection_yunet_2023mar.onnx` + Haar XML (bundled).

## 2. Running
```bash
cd nyaya-forensics
npm install
npm run tauri dev     # desktop app
# production: npm run tauri build
```

## 3. Pages
| Page | What you do there |
|------|-------------------|
| **Dashboard** | App/Python status, supported OEM list, layer map |
| **Case** | Case ID, examiner, organisation, timezone → `case.json` |
| **Evidence** | Drag/drop or browse image **or** *List physical drives* → pick `\\.\PhysicalDriveN`; *Detect Vendor*; *Acquire copy + hashes* (opens the custody ledger automatically) |
| **Timeline** | Load timeline/event JSONs, normalise timestamps (BCD/epoch → UTC/IST), **Correlate ±window** across cameras, visual timeline (zoom: ctrl+wheel) |
| **Recovery** | Carve deleted H.264/H.265 footage; decode `.dav`/`.hik` to MP4 (auto-fallback to DHAV carving without FFmpeg) |
| **Report** | Pre-fill paths, verify the custody hash-chain, generate the 9-section §65B PDF |

## 4. CLI equivalents (audit-friendly, scriptable)
```bash
python core/acquisition.py --list-drives
python core/acquisition.py "\\.\PhysicalDrive1" --output case1.dd --save-hashfile
python core/vendor_detect.py case1.dd
python core/timestamps.py --dahua-bcd 20260615182600
python core/timestamps.py --hik-epoch 1781552160
python plugins/dahua_wrapper.py case1.dd --outdir extracted/
python core/recovery.py case1.dd --workdir recovered/ --join-gap-mb 2
python ai/detector.py clip.mp4 --mode objects --events events.json
python ai/detector.py clip.mp4 --mode face    --events faces.json
python core/timeline.py --inputs events.json timeline.json --window 10 --out correlated.json
python core/custody.py append --ledger case.custody.jsonl --examiner "SI R. Kumar" --action carve
python core/custody.py verify --ledger case.custody.jsonl
python reporting/pdf_gen.py --case case.json --hash hashes.json --timeline timeline.json --custody custody.jsonl --out report.pdf
```

## 5. Troubleshooting
| Symptom | Cause / fix |
|---------|-------------|
| `cannot open \\. \PhysicalDriveN (WinError 5)` | Imaging needs Administrator; enumeration does not. Run as admin + write-blocker. |
| `mp4: null` on carved clips | FFmpeg missing — install it, or use the DHAV carve path. |
| `engine: opencv_mog2_fallback` | ultralytics not installed — `pip install ultralytics` for YOLOv8n. |
| Custody verify fails at seq N | Ledger edited after the fact — investigate; never hand-edit the file. |
