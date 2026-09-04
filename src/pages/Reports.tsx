import { useState } from "react";
import { save } from "@tauri-apps/plugin-dialog";
import { api, type ChainVerification } from "../ipc";
import { useActiveCase } from "../hooks/useActiveCase";

export default function ReportsPage() {
  const { active } = useActiveCase();
  const [checking, setChecking] = useState(false);
  const [chainResult, setChainResult] = useState<ChainVerification | null>(null);
  const [generating, setGenerating] = useState(false);
  const [generatedPdf, setGeneratedPdf] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const verifyChain = async () => {
    setChecking(true);
    setError(null);
    try {
      setChainResult(await api.verifyChainOfCustody());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setChecking(false);
    }
  };

  const generateReport = async () => {
    if (!active) return;
    setGenerating(true);
    setError(null);
    setGeneratedPdf(null);

    try {
      const defaultOut = `${active.case_dir}/forensic_report.pdf`;
      const outPdf = (await save({
        title: "Save Forensic Report (PDF)",
        defaultPath: defaultOut,
        filters: [{ name: "PDF Document", extensions: ["pdf"] }],
      })) || defaultOut;

      const caseJson = `${active.case_dir}/case.json`;
      const chainJson = `${active.case_dir}/chain_of_custody.json`;

      const resp = await api.generatePdfReport(caseJson, outPdf, chainJson);
      if (resp.json && resp.json.error) {
        setError(resp.json.error);
      } else {
        setGeneratedPdf(outPdf);
      }
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink-100">Forensic Reporting &amp; Legal Admissibility</h1>
        <p className="text-sm text-ink-400 mt-1">
          Court-ready certificate generation compliant with Section 65B Indian Evidence Act / Section 63 BSA 2023.
        </p>
      </div>

      {!active ? (
        <div className="card border-amber-700/40 text-amber-300">
          Open a case to generate reports and verify chain-of-custody integrity.
        </div>
      ) : (
        <div className="space-y-6">
          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">Active Case Overview</h2>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <span className="text-ink-400 text-xs">Case Identifier</span>
                <div className="font-semibold text-ink-100">{active.case_id}</div>
              </div>
              <div>
                <span className="text-ink-400 text-xs">Case Name</span>
                <div className="text-ink-200">{active.case_name}</div>
              </div>
              <div>
                <span className="text-ink-400 text-xs">Lead Forensic Examiner</span>
                <div className="text-ink-200">{active.examiner}</div>
              </div>
              <div>
                <span className="text-ink-400 text-xs">Law Enforcement Agency</span>
                <div className="text-ink-200">{active.organization}</div>
              </div>
            </div>
          </div>

          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">Chain of Custody Verification</h2>
            <p className="text-sm text-ink-300">
              Each forensic action (ingestion, verification, carving, decoding) is cryptographically linked in an append-only JSONL ledger via SHA-256 hash chaining:
            </p>
            <div>
              <button
                className="btn"
                onClick={verifyChain}
                disabled={checking}
              >
                {checking ? "Checking Ledger Hashes..." : "Verify Custody Chain Integrity"}
              </button>
            </div>

            {chainResult && (
              <div
                className={`p-3 rounded border text-sm ${
                  chainResult.valid
                    ? "bg-emerald-950/40 border-emerald-700/50 text-emerald-300"
                    : "bg-red-950/40 border-red-700/50 text-red-300"
                }`}
              >
                <div className="font-semibold">
                  {chainResult.valid
                    ? `✓ Chain Intact: All ${chainResult.total_entries} custody ledger entries verified.`
                    : `✗ TAMPERING DETECTED at sequence #${chainResult.broken_at_seq}!`}
                </div>
                <div className="text-xs text-ink-300 mt-1">{chainResult.message}</div>
              </div>
            )}
          </div>

          <div className="card space-y-4">
            <h2 className="text-lg font-semibold text-ink-100">Generate Court-Ready Forensic Report</h2>
            <p className="text-sm text-ink-300">
              Compiles an official PDF report including Case Metadata, Dual Cryptographic Hashes (MD5 &amp; SHA-256), Extracted Video Listings, Carved Footage Candidates, and a formal statutory Section 65B / Section 63 BSA certificate.
            </p>

            <div className="pt-2">
              <button
                className="btn btn-primary"
                onClick={generateReport}
                disabled={generating}
              >
                {generating ? "Compiling PDF Report..." : "Generate Official Forensic Report (PDF)"}
              </button>
            </div>

            {generatedPdf && (
              <div className="p-3 bg-emerald-950/40 border border-emerald-700/50 rounded text-emerald-300 text-sm flex items-center justify-between">
                <div>
                  <div className="font-semibold">✓ Forensic PDF Report Generated Successfully!</div>
                  <div className="text-xs text-ink-300 font-mono mt-1">{generatedPdf}</div>
                </div>
              </div>
            )}
          </div>

          {error && (
            <div className="p-3 bg-red-950/40 border border-red-700/50 rounded text-red-300 text-sm">
              {error}
            </div>
          )}
        </div>
      )}
    </div>
  );
}