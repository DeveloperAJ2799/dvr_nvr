# NYAYA Forensics — Standard Operating Procedure (SOP)

Court-oriented workflow for DVR/NVR HDD examinations. Follow every step in
order; each step records evidence into the case folder so the final report
and §65B/§63-BSA certificate are auto-supported.

## 0. Authorisation & hashing of the workflow itself
1. Obtain written seizure/inspection authorisation (MHA/CFSL/agency format).
2. Note case metadata: FIR no., device make/model, seizure date, examiner.
3. In NYAYA: **Case page → fill Case ID / examiner / organisation /
   timezone → Save case.json** (drives the certificate page).

## 1. Acquisition (never touch the original)
1. Connect the evidence HDD through a **hardware write-blocker**.
2. **Evidence page → List physical drives**, pick the `\\.\PhysicalDriveN`
   (read-only enumeration; sizes/models shown), or browse to an existing
   `.dd/.img/.E01` image.
3. **Acquire copy + hashes** → NYAYA streams a bit-exact copy in 4 MiB
   chunks computing MD5 + SHA-256 in one pass and opens the
   **hash-chained custody ledger** (`<copy>.custody.jsonl`).
4. Record the printed hash file (`<copy>.hashes.txt`) in the case file.

## 2. Custody discipline
- Every subsequent forensic action is appended to the ledger
  (`custody_append`) and the chain is checked before reporting
  (`custody_verify`, Report page). A single modified entry breaks the chain
  and names the sequence number — do not edit the ledger manually.

## 3. Device identification
1. **Detect Vendor** on the acquired copy (never the original).
2. The detector reports magic (DHFS/DHAV/HKVI/CPPLUS/GODREJ/MATRIX/
   UNIVIEW/TP-LINK/VIGI/HONEYWELL/HWSM/WFS/UFS), confidence, offset.
3. Record the vendor in the case notes — it selects the extraction plugin.

## 4. Extraction of existing recordings
1. **Recovery page → Decode .dav/.hik → MP4** (FFmpeg; DHAV runs are carved
   automatically if FFmpeg is unavailable).
2. Hash every extracted file before analysis (`--save-hashfile` pattern).

## 5. Deleted-footage recovery
1. **Recovery page → Carve deleted recordings** (join gap 2 MB default).
2. The engine scans H.264 (65/67/68) and H.265 (26/28/40/42/44) NAL
   signatures, extends each group to include SPS/PPS/VPS, and remuxes
   candidates to MP4.
3. Review every candidate manually — carving is probabilistic by nature;
   confidence scores are reported per clip.

## 6. Timeline normalisation & correlation
1. Collect event JSONs (AI events, timeline exports).
2. **Timeline page → Add events JSON → Correlate** (window default ±10 s).
3. Timestamps are normalised to UTC + IST; Dahua BCD values carry an
   explicit timezone assumption recorded in the JSON and report.
4. Correlated tracks (CAM-01 → CAM-02 …) evidence subject movement.

## 7. AI triage (investigative aid only)
1. Run `--mode objects` and `--mode face` on extracted clips.
2. AI output is **never** conclusive proof; an examiner must review every
   flagged frame before it enters the report.

## 8. Reporting
1. **Report page → Pre-fill from workspace → Verify custody chain →
   Generate PDF.**
2. The PDF contains 9 sections incl. hash verification and the §65B
   certificate; sign, date, and archive with the ledger and hash files.
