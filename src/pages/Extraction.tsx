import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useActiveCase } from "../hooks/useActiveCase";
import { api, type EvidenceRecord } from "../ipc";

export default function ExtractionPage() {
  const { active } = useActiveCase();
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([]);
  const [selectedEvidence, setSelectedEvidence] = useState<string>("");
  const [vendorInfo, setVendorInfo] = useState<any>(null);
  const [detecting, setDetecting] = useState<boolean>(false);
  const [extracting, setExtracting] = useState<boolean>(false);
  const [extractedFiles, setExtractedFiles] = useState<any[]>([]);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (active) {
      api.listEvidence().then((ev) => {
        setEvidenceList(ev);
        if (ev.length > 0 && !selectedEvidence) {
          setSelectedEvidence(ev[0].source_path);
        }
      }).catch(console.error);
    }
  }, [active]);

  const browseFile = async () => {
    const sel = await open({
      multiple: false,
      title: "Select disk image or video file to extract",
      filters: [{ name: "Forensic Evidence", extensions: ["dd", "img", "raw", "dav", "hik", "mp4", "264", "asf"] }],
    });
    if (typeof sel === "string") {
      setSelectedEvidence(sel);
    }
  };

  const handleDetectVendor = async () => {
    if (!selectedEvidence) return;
    setDetecting(true);
    setError(null);
    setVendorInfo(null);
    try {
      const resp = await api.detectVendor(selectedEvidence);
      if (resp.json) {
        setVendorInfo(resp.json);
      } else {
        setError(resp.stderr || "Vendor detection returned unexpected output");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDetecting(false);
    }
  };

  const handleExtract = async (parserType?: string) => {
    if (!selectedEvidence || !active) return;
    setExtracting(true);
    setError(null);
    setStatusMessage("Extracting and remuxing video streams...");
    try {
      const outDir = `${active.case_dir}/extracted`;
      let resp;

      const vendor = parserType || vendorInfo?.vendor_id || "dahua";
      if (vendor === "hikvision" || vendor === "matrix" || vendor === "godrej") {
        resp = await api.runHikvisionParser(selectedEvidence, outDir);
      } else {
        resp = await api.runDahuaParser(selectedEvidence, outDir);
      }

      if (resp.json && resp.json.details) {
        setExtractedFiles(resp.json.details);
        setStatusMessage(`Successfully extracted ${resp.json.extracted_count} recordings.`);
      } else if (resp.json && resp.json.extracted_files) {
        setExtractedFiles(resp.json.extracted_files.map((f: string) => ({ output: f })));
        setStatusMessage(`Extracted ${resp.json.extracted_files.length} streams.`);
      } else if (resp.json && resp.json.error) {
        setError(resp.json.error);
      } else {
        setStatusMessage("Extraction finished.");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setExtracting(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Video Stream Extraction</h1>
        <p className="text-sm text-ink-400 mt-1">
          Automated multi-vendor demuxing and decoding of proprietary CCTV streams (DHAV, HKVI, WFS, MPEG-PS).
        </p>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Please create or open a case first to access extraction tools.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">1. Target Evidence Source</h2>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                className="input flex-1"
                placeholder="Path to disk image (.dd/.img) or exported video file"
                value={selectedEvidence}
                onChange={(e) => setSelectedEvidence(e.target.value)}
              />
              <button className="btn" onClick={browseFile}>
                Browse File
              </button>
              {evidenceList.length > 0 && (
                <select
                  className="input sm:w-64"
                  value={selectedEvidence}
                  onChange={(e) => setSelectedEvidence(e.target.value)}
                >
                  <option value="">Select Ingested Evidence...</option>
                  {evidenceList.map((ev) => (
                    <option key={ev.evidence_id} value={ev.source_path}>
                      {ev.evidence_id} - {ev.source_path.split(/[\\/]/).pop()}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                className="btn btn-primary"
                onClick={handleDetectVendor}
                disabled={detecting || !selectedEvidence}
              >
                {detecting ? "Analyzing Signatures..." : "Auto-Detect Vendor"}
              </button>
              <button
                className="btn"
                onClick={() => handleExtract("dahua")}
                disabled={extracting || !selectedEvidence}
              >
                {extracting ? "Extracting..." : "Dahua / CP Plus Extract"}
              </button>
              <button
                className="btn"
                onClick={() => handleExtract("hikvision")}
                disabled={extracting || !selectedEvidence}
              >
                {extracting ? "Extracting..." : "Hikvision / Matrix Extract"}
              </button>
            </div>
          </div>

          {vendorInfo && (
            <div className="card border-blue-600/40 bg-ink-900/60">
              <h3 className="text-md font-semibold text-blue-300">Device Identification Result</h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-3 text-sm">
                <div>
                  <span className="text-ink-400">Identified Vendor:</span>
                  <div className="font-semibold text-ink-100">{vendorInfo.vendor}</div>
                </div>
                <div>
                  <span className="text-ink-400">Confidence:</span>
                  <div className="font-semibold text-emerald-400">
                    {Math.round((vendorInfo.confidence || 0) * 100)}%
                  </div>
                </div>
                <div>
                  <span className="text-ink-400">Magic Signature:</span>
                  <div className="font-mono text-ink-200">{vendorInfo.hex_head || "N/A"}</div>
                </div>
                <div>
                  <span className="text-ink-400">Parser Architecture:</span>
                  <div className="text-ink-200">{vendorInfo.note || "Embedded demuxer ready"}</div>
                </div>
              </div>
            </div>
          )}

          {statusMessage && (
            <div className="p-3 bg-emerald-950/40 border border-emerald-700/50 rounded text-emerald-300 text-sm">
              {statusMessage}
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-700/50 rounded text-red-300 text-sm">
              {error}
            </div>
          )}

          {extractedFiles.length > 0 && (
            <div className="card space-y-3">
              <h3 className="text-lg font-semibold text-ink-100">
                Extracted Recordings ({extractedFiles.length})
              </h3>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-ink-700 text-ink-400">
                      <th className="py-2">File</th>
                      <th className="py-2">Format</th>
                      <th className="py-2">Size</th>
                      <th className="py-2">SHA-256</th>
                    </tr>
                  </thead>
                  <tbody>
                    {extractedFiles.map((f, i) => (
                      <tr key={i} className="border-b border-ink-800 hover:bg-ink-800/40">
                        <td className="py-2 font-mono text-xs text-blue-300 truncate max-w-xs">
                          {(f.output || f.source || "").split(/[\\/]/).pop()}
                        </td>
                        <td className="py-2 text-ink-300">{f.format || "mp4"}</td>
                        <td className="py-2 text-ink-300">
                          {f.size_bytes ? `${Math.round(f.size_bytes / 1024)} KB` : "—"}
                        </td>
                        <td className="py-2 font-mono text-xs text-ink-400">
                          {f.sha256 ? `${f.sha256.slice(0, 16)}...` : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}