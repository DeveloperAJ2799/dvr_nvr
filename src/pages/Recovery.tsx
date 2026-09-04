import { useEffect, useState } from "react";
import { open } from "@tauri-apps/plugin-dialog";
import { useActiveCase } from "../hooks/useActiveCase";
import { api, type EvidenceRecord } from "../ipc";

export default function RecoveryPage() {
  const { active } = useActiveCase();
  const [evidenceList, setEvidenceList] = useState<EvidenceRecord[]>([]);
  const [selectedImage, setSelectedImage] = useState<string>("");
  const [maxCandidates, setMaxCandidates] = useState<number>(25);
  const [carving, setCarving] = useState<boolean>(false);
  const [carvingResult, setCarvingResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (active) {
      api.listEvidence().then((ev) => {
        setEvidenceList(ev);
        if (ev.length > 0 && !selectedImage) {
          setSelectedImage(ev[0].source_path);
        }
      }).catch(console.error);
    }
  }, [active]);

  const browseImage = async () => {
    const sel = await open({
      multiple: false,
      title: "Select disk image (.dd/.img/.raw) for deleted carving",
      filters: [{ name: "Raw Disk Images", extensions: ["dd", "img", "raw", "bin", "001"] }],
    });
    if (typeof sel === "string") {
      setSelectedImage(sel);
    }
  };

  const startCarving = async () => {
    if (!selectedImage || !active) return;
    setCarving(true);
    setError(null);
    setCarvingResult(null);

    try {
      const outDir = `${active.case_dir}/recovered`;
      const resp = await api.runRecovery(selectedImage, outDir, 2 * 1024 * 1024, maxCandidates);
      if (resp.json) {
        if (resp.json.error) {
          setError(resp.json.error);
        } else {
          setCarvingResult(resp.json);
        }
      } else {
        setError(resp.stderr || "Carving returned unexpected result");
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setCarving(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Deleted Footage Recovery Engine</h1>
        <p className="text-sm text-ink-400 mt-1">
          Deep unallocated space carving for H.264 &amp; H.265 GOP sequences with automated SPS/PPS parameter prepending.
        </p>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Please create or open a case first to perform video carving.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">Carving Configuration</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="md:col-span-2 space-y-1">
                <label className="text-xs text-ink-400 font-medium">Source Evidence Image</label>
                <div className="flex gap-2">
                  <input
                    className="input flex-1"
                    placeholder="Path to raw disk image (.dd/.img/.raw)"
                    value={selectedImage}
                    onChange={(e) => setSelectedImage(e.target.value)}
                  />
                  <button className="btn" onClick={browseImage}>
                    Browse
                  </button>
                  {evidenceList.length > 0 && (
                    <select
                      className="input max-w-xs"
                      value={selectedImage}
                      onChange={(e) => setSelectedImage(e.target.value)}
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
              </div>
              <div className="space-y-1">
                <label className="text-xs text-ink-400 font-medium">Max Candidate Fragments</label>
                <input
                  type="number"
                  className="input w-full"
                  min={5}
                  max={200}
                  value={maxCandidates}
                  onChange={(e) => setMaxCandidates(Number(e.target.value))}
                />
              </div>
            </div>

            <div className="flex items-center gap-3 pt-2">
              <button
                className="btn btn-primary"
                onClick={startCarving}
                disabled={carving || !selectedImage}
              >
                {carving ? "Scanning & Carving GOPs..." : "Start Deep Carving"}
              </button>
              <span className="text-xs text-ink-400">
                Opened strictly read-only. Original bit-stream is never modified.
              </span>
            </div>
          </div>

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-700/50 rounded text-red-300 text-sm">
              {error}
            </div>
          )}

          {carvingResult && (
            <div className="space-y-4">
              <div className="card border-emerald-700/40 bg-ink-900/60 flex flex-wrap justify-between items-center">
                <div>
                  <div className="text-sm font-semibold text-emerald-300">
                    Carving Scan Complete
                  </div>
                  <div className="text-xs text-ink-400 mt-1">
                    Image size: {Math.round((carvingResult.image_size_bytes || 0) / (1024 * 1024))} MB · Scanned with SPS/PPS GOP reconstruction
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-2xl font-bold text-emerald-400">
                    {carvingResult.candidates_written || 0}
                  </div>
                  <div className="text-xs text-ink-400">Recovered Candidates</div>
                </div>
              </div>

              {carvingResult.candidates && carvingResult.candidates.length > 0 && (
                <div className="card space-y-3">
                  <h3 className="text-lg font-semibold text-ink-100">
                    Recovered Video Candidates ({carvingResult.candidates.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead>
                        <tr className="border-b border-ink-700 text-ink-400">
                          <th className="py-2">Candidate File</th>
                          <th className="py-2">Byte Offset</th>
                          <th className="py-2">NAL Type</th>
                          <th className="py-2">Confidence</th>
                          <th className="py-2">Size</th>
                          <th className="py-2">SHA-256 Hash</th>
                        </tr>
                      </thead>
                      <tbody>
                        {carvingResult.candidates.map((c: any, i: number) => (
                          <tr key={i} className="border-b border-ink-800 hover:bg-ink-800/40">
                            <td className="py-2 font-mono text-xs text-blue-300 truncate max-w-xs">
                              {(c.mp4_file || c.file || "").split(/[\\/]/).pop()}
                            </td>
                            <td className="py-2 font-mono text-xs text-ink-300">
                              {c.offset_hex || hex(c.offset_bytes)}
                            </td>
                            <td className="py-2">
                              <span className="badge badge-info text-xs">{c.nal_type}</span>
                            </td>
                            <td className="py-2 font-semibold text-emerald-400">
                              {Math.round((c.confidence || 0.7) * 100)}%
                            </td>
                            <td className="py-2 text-ink-300">
                              {c.size_bytes ? `${Math.round(c.size_bytes / 1024)} KB` : "—"}
                            </td>
                            <td className="py-2 font-mono text-xs text-ink-400">
                              {c.sha256 ? `${c.sha256.slice(0, 16)}...` : "—"}
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
      )}
    </div>
  );
}

function hex(n: number) {
  return "0x" + (n || 0).toString(16).toUpperCase();
}