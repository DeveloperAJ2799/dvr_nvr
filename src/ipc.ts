import { invoke } from "@tauri-apps/api/core";

export interface CommandError {
  message: string;
}

export type CaseRecord = {
  case_id: string;
  case_name: string;
  examiner: string;
  organization: string;
  timezone_assumption: string;
  notes: string;
  created_at_utc: string;
  updated_at_utc: string;
  case_dir: string;
  status: string;
};

export type NewCaseInput = {
  case_id?: string | null;
  case_name: string;
  examiner: string;
  organization: string;
  timezone_assumption: string;
  notes: string;
};

export type EvidenceRecord = {
  evidence_id: string;
  case_id: string;
  source_path: string;
  evidence_type: string;
  size_bytes: number;
  md5: string;
  sha256: string;
  ingested_at_utc: string;
  examiner: string;
  acquisition_method: string;
  status: string;
};

export type IngestEvidenceInput = {
  source_path: string;
  evidence_label: string;
  evidence_type: string;
  examiner: string;
  acquisition_method: string;
  notes: string;
};

export type ParserInfo = {
  vendor: string;
  vendor_id: string;
  priority: number;
  description: string;
};

export type AuditEvent = {
  event_id: string;
  case_id: string;
  timestamp_utc: string;
  examiner: string;
  module: string;
  action: string;
  input: string;
  output: string;
  status: string;
  details: string;
};

export type VerificationOutcome = {
  evidence_id: string;
  case_id: string;
  verified: boolean;
  source_exists: boolean;
  md5_match: boolean;
  sha256_match: boolean;
  expected_md5: string;
  actual_md5: string;
  expected_sha256: string;
  actual_sha256: string;
  size_bytes: number;
  verified_at_utc: string;
  message: string;
};

export type ChainVerification = {
  total_entries: number;
  valid: boolean;
  broken_at_seq: number | null;
  legacy_format: boolean;
  message: string;
};

export type AppSettings = {
  case_storage_dir: string;
  ffmpeg_path: string | null;
  ffprobe_path: string | null;
  default_timezone: string;
  ai_enabled: boolean;
  hash_algorithms: string[];
  theme: string;
  log_level: string;
  carving_chunk_size: number;
  recovery_confidence_threshold: number;
};

async function call<T>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  return await invoke<T>(cmd, args);
}

export type SidecarResponse = {
  stdout: string;
  stderr: string;
  exit_code: number;
  json: Record<string, any> | null;
};

export const api = {
  getSettings: () => call<AppSettings>("get_settings"),
  saveSettings: (settings: AppSettings) =>
    call<void>("save_settings_cmd", { settings }),
  createCase: (input: NewCaseInput) => call<CaseRecord>("create_case", { input }),
  listCases: () => call<CaseRecord[]>("list_cases"),
  openCase: (case_id: string) => call<CaseRecord>("open_case", { caseId: case_id }),
  closeCase: () => call<void>("close_case"),
  activeCase: () => call<CaseRecord | null>("active_case"),
  ingestEvidence: (input: IngestEvidenceInput) =>
    call<EvidenceRecord>("ingest_evidence", { input }),
  listEvidence: () => call<EvidenceRecord[]>("list_evidence"),
  verifyEvidence: (evidenceId: string) =>
    call<VerificationOutcome>("verify_evidence", { evidenceId }),
  verifyChainOfCustody: () => call<ChainVerification>("verify_chain_of_custody"),
  listParsers: () => call<ParserInfo[]>("list_parsers"),
  listAuditEvents: (caseId: string) =>
    call<AuditEvent[]>("list_audit_events", { caseId }),
  detectFfmpeg: () => call<string | null>("detect_ffmpeg"),
  detectFfprobe: () => call<string | null>("detect_ffprobe"),

  // NYAYA Forensics Python sidecar commands
  runSidecar: (subcommand: string, args: string[] = []) =>
    call<SidecarResponse>("run_sidecar", { subcommand, args }),
  detectVendor: (filePath: string) =>
    call<SidecarResponse>("detect_vendor", { filePath }),
  acquireEvidence: (imagePath: string, outDir: string) =>
    call<SidecarResponse>("acquire_evidence", { imagePath, outDir }),
  runDahuaParser: (imagePath: string, outDir: string, tool?: string) =>
    call<SidecarResponse>("run_dahua_parser", { imagePath, outDir, tool }),
  runHikvisionParser: (imagePath: string, outDir: string) =>
    call<SidecarResponse>("run_hikvision_parser", { imagePath, outDir }),
  decodeVideo: (
    inputPath: string,
    outPath: string,
    strip?: number,
    noReencode?: boolean,
  ) =>
    call<SidecarResponse>("decode_video", {
      inputPath,
      outPath,
      strip,
      noReencode,
    }),
  runRecovery: (
    imagePath: string,
    outDir: string,
    chunk?: number,
    maxCandidates?: number,
  ) =>
    call<SidecarResponse>("run_recovery", {
      imagePath,
      outDir,
      chunk,
      maxCandidates,
    }),
  runAiAnalytics: (
    videoPath: string,
    mode: "motion" | "object" | "face",
    outPath?: string,
  ) => call<SidecarResponse>("run_ai_analytics", { videoPath, mode, outPath }),
  generatePdfReport: (
    caseJson: string,
    outPdf: string,
    chainJson?: string,
  ) =>
    call<SidecarResponse>("generate_pdf_report", {
      caseJson,
      outPdf,
      chainJson,
    }),
  convertBcdToIst: (raw: string) =>
    call<SidecarResponse>("convert_bcd_to_ist", { raw }),
  convertEpochToIst: (raw: number) =>
    call<SidecarResponse>("convert_epoch_to_ist", { raw }),
};