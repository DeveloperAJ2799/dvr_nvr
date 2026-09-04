# DVR/NVR Forensic Analyzer

A vendor-agnostic forensic desktop application built with **Rust + Tauri 2**, **React + TypeScript**, and **Tailwind CSS**, for acquiring, parsing, recovering, analyzing, validating, and reporting surveillance video evidence from multiple DVR/NVR vendors.

## Status

- ✅ Day 1 (current): App skeleton, case management, evidence ingestion + streaming hashing, audit/chain of custody, parser framework + 8 vendor stubs + generic exported parser, settings, FFmpeg/FFprobe detection.
- ⏭️ Day 2–5: Working vendor parser (sample data dependent), FFmpeg extraction, recovery, timeline, reports.

## Project layout

```text
dvr-forensic-analyzer/
├── package.json              # Vite + React + TS frontend
├── src/                      # Frontend (pages, components, IPC client)
└── src-tauri/
    ├── Cargo.toml            # Rust backend
    ├── tauri.conf.json
    ├── capabilities/         # Tauri permission scopes
    └── src/
        ├── main.rs
        ├── lib.rs
        ├── run.rs            # Tauri builder + command registration
        ├── commands/         # Tauri IPC commands
        ├── core/             # case_manager, evidence, hasher, audit, settings, time
        ├── parsers/          # base, registry, generic_exported, stubs (Dahua/Hikvision/...)
        ├── recovery/         # carving skeleton
        ├── timeline/         # placeholder
        ├── media/            # ffmpeg/ffprobe/thumbnail skeletons
        ├── analytics/        # motion/object/face skeletons
        └── report/           # html/json skeletons
```

## Prerequisites

- Rust 1.77+ (`rustup toolchain install stable`)
- Node 18+ and npm
- Tauri CLI (`cargo install tauri-cli --version "^2.0"`)
- (Optional) FFmpeg and FFprobe on `PATH` for extraction features.

## First run (Windows)

```powershell
cd D:\axn\trc\dvr-forensic-analyzer
npm install
npm run tauri dev
```

On first launch, Tauri builds the Rust binary in the background and then opens the desktop window.

## First-run walkthrough

1. Click **New Case** → fill in name, examiner, organization → **Create case**.
2. Open the case from the **Cases** list (it auto-opens after creation).
3. **Evidence** → click **File…** or **Folder…** → pick a `.img`/`.dd`/exported folder → **Ingest & hash**.
4. The evidence table shows MD5 + SHA-256. **Verify** re-hashes and compares.
5. Every action is written to the SQLite audit log and to `chain_of_custody.json` in the case folder.

## Architecture notes

- The Tauri shell uses HashRouter for navigation, plugin-dialog for native file pickers, plugin-fs scoped to user directories.
- All evidence-derived files (manifests, hashes, audit JSON) live under `cases/<CASE-ID>/`.
- Vendor parsers implement the `VendorParser` trait (`identify`, `parse_filesystem`, `extract_videos`, `recover_deleted`, `validate_output`) and are registered in `parsers::default_registry()`.
- Hashing is streaming with a 1 MiB chunk size and never loads the full image into memory.

## Security posture

- Original evidence is opened read-only and never written to.
- Tauri capabilities explicitly whitelist dialog/fs permissions; no shell plugin is loaded.
- CSP forbids remote scripts and external connections; only local IPC is allowed.
- No cloud upload by default. No external AI calls unless the user explicitly enables them.

## Next milestones

| Day | Goal | Status |
|---|---|---|
| 1 | Scaffold + case + ingestion + hashing | ✅ done |
| 2 | Evidence polish (E01 stub, cancelled ingestion) | pending |
| 3 | Real vendor parser + FFmpeg remux | needs sample data |
| 4 | Recovery + timeline + motion detection | pending |
| 5 | HTML/JSON report + validation suite | pending |