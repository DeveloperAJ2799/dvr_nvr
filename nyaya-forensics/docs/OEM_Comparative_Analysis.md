# OEM Comparative Analysis — DVR/NVR Forensic Support in NYAYA

NYAYA Forensics is vendor-agnostic: the **Device ID layer** matches
proprietary magic signatures, the **plugin layer** invokes open parsers /
FFmpeg demuxers where they exist, and the **carving engine** recovers
video from any OEM image when no parser exists. No OEM software or cloud
service is required (offline evidence handling).

## Coverage matrix (8 OEMs — SIH PS list)

| OEM | On-media format / FS | Signature(s) matched | Confidence | Export container | NYAYA decode path |
|-----|----------------------|----------------------|-----------|------------------|-------------------|
| **Dahua** | DHFS volume + DHAV per-frame container | `DHFS`, `DHAV` | 0.93 | `.dav` | FFmpeg native `dhav` demuxer; carve fallback |
| **CP Plus** | Dahua DHFS OEM variant | `CPPLUS` (+DHFS/DHAV) | 0.95 | `.dav` | Same Dahua path (OEM-compatible) |
| **HIKVISION** | HIKFS + HKVI frame container | `HIKVISION`, `HKVI` | 0.97 | `.hik`/MP4 (MPEG-PS exports) | Header-strip remux; carve fallback |
| **Godrej** | Hikvision OEM variant | `GODREJ` | 0.95 | MP4 | Hikvision path |
| **Matrix** (Satya) | Hikvision OEM variant | `MATRIX` | 0.95 | MP4 | Hikvision path |
| **Uniview (UNV)** | UFS / WFS 0.4 | `UNIVIEW`, `UFS\x00`, `WFS\x00` | 0.80–0.95 | PS/H.264 | Generic H.264 carving |
| **TP-Link (VIGI)** | Standard MP4/TS + VIGI marks | `TP-LINK`, `VIGI` | 0.88–0.95 | MP4/H.264 | Direct MP4; carving |
| **Honeywell** | HUSM/PERFORMA embedded DB | `HONEYWELL`, `HWSM` | 0.90–0.96 | MP4/H.264 | Carving + FFmpeg |

Detection reports **all** hits (`all_hits`) with per-signature confidence so
the examiner can defend the identification in court; the highest-confidence
match is auto-selected. OEM rebrands that store stock Dahua/Hikvision
formats are handled by their parent's decode path.

## Engineering comparison vs. alternatives

| Capability | NYAYA Forensics | Commercial suites (FTK/EnCase) | Single-vendor tools (Dahua ConfigTool etc.) |
|---|---|---|---|
| OEM breadth | 8 OEM signatures + codec carving | Broad but licence-gated | One vendor only |
| Physical-drive imaging | Read-only Win32 handle, dual-hash streaming | Yes (write-blocker ecosystem) | Usually read-only export only |
| Custody ledger | SHA-256 hash-chained JSONL, tamper pinpointing | Proprietary audit DB | None |
| Timestamp normalisation | BCD/epoch → UTC+IST with recorded assumption | Vendor-dependent | Vendor TZ only |
| Cross-camera correlation | ±window union-find tracks | Manual | None |
| Deleted footage | H.264+H.265 GOP carving w/ param-set inclusion | Carve general, DVR-specific weak | Vendor files only |
| Cost / offline | Free, fully offline | High cost, dongles | Free but closed |

## Legal note (India)
Identification, normalisation and correlation outputs are examiner-auditable
artefacts (raw value + assumption + hash) designed to support the
certificate under **§65B Indian Evidence Act / §63 Bharatiya Sakshya Adhiniyam
2023**; the AI layer is explicitly labelled an investigative aid requiring
human verification.

## Verification hooks
- Signature set: `core/vendor_detect.py` (`SIGNATURES`, unit-testable).
- Live fixture proof: `python core/vendor_detect.py test_evidence/sample.dd`
  → Dahua/DHFS @ offset 4096 (see `docs/Validation_Report.md`).
