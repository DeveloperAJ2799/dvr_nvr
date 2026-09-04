import { invoke } from "@tauri-apps/api/core";

export type JsonValue = Record<string, any>;

export type CaseInfo = {
  case_id: string;
  case_name: string;
  examiner: string;
  organization: string;
  timezone: string;
  notes: string;
};

export const emptyCase = (): CaseInfo => ({
  case_id: "",
  case_name: "",
  examiner: "",
  organization: "",
  timezone: "Asia/Kolkata (IST, +05:30)",
  notes: "",
});

export type TimelineEvent = {
  utc?: string;
  camera?: string;
  event?: string;
  confidence?: string | number;
};

export type ConvertedTimestamp = {
  ok: boolean;
  raw: string | number;
  raw_kind: string;
  utc: string;
  ist: string;
  epoch_utc: number;
  tz_assumption: string;
  offset_hours: number;
};

export type CorrelatedTrack = {
  cameras: string[];
  event_count: number;
  span_seconds: number;
  events: Array<{
    camera?: string;
    event?: string;
    utc?: string;
    ist?: string;
    confidence?: string | number;
  }>;
};

export type CorrelationResult = {
  ok: boolean;
  window_seconds: number;
  event_count: number;
  parse_errors: Array<Record<string, unknown>>;
  events: Array<Record<string, unknown>>;
  correlated_pairs: Array<{
    delta_seconds: number;
    a: { camera?: string; event?: string; utc?: string };
    b: { camera?: string; event?: string; utc?: string };
  }>;
  correlation_count: number;
  tracks: CorrelatedTrack[];
  out?: string;
};

export type CustodyEntry = {
  seq: number;
  ts_utc: string;
  examiner: string;
  action: string;
  details: Record<string, unknown>;
  prev_hash: string;
  entry_hash: string;
};

export type CustodyVerifyResult = {
  ok: boolean;
  valid: boolean;
  total_entries: number;
  broken_at_seq: number | null;
  head_hash?: string;
  message: string;
};

export type DriveInfo = {
  device: string;
  index: number;
  size_bytes: number | null;
  size_human: string;
  model?: string;
};

export type DriveListResult = {
  ok: boolean;
  physical_drives: DriveInfo[];
  volumes: Array<Record<string, unknown>>;
  note?: string;
};

/**
 * Thin typed wrapper over the Tauri commands. Every forensic command shells
 * out to Python and rejects with `{ message }` when it exits non-zero.
 */
export const nyaya = {
  detectVendor: (image_path: string) =>
    invoke<JsonValue>("detect_vendor", { imagePath: image_path }),

  acquireImage: (input: string, output: string, verify = true) =>
    invoke<JsonValue>("acquire_image", { input, output, verify }),

  extractDahua: (image: string, outdir: string) =>
    invoke<JsonValue>("extract_dahua", { image, outdir }),

  decodeVideo: (input: string, output?: string, headerBytes?: number) =>
    invoke<JsonValue>("decode_video", { input, output, headerBytes }),

  carveDeleted: (image: string, workdir: string, joinGapMb?: number) =>
    invoke<JsonValue>("carve_deleted", {
      image,
      workdir,
      joinGapMb: joinGapMb ?? 2,
    }),

  runAI: (video: string, eventsPath?: string) =>
    invoke<JsonValue>("run_ai", { video, eventsPath }),

  runAIMode: (video: string, mode: "objects" | "face", eventsPath?: string) =>
    invoke<JsonValue>("run_ai_mode", { video, mode, eventsPath }),

  // ---- SIH PS additions: drives, timestamps, correlation, custody ----
  listDrives: () => invoke<DriveListResult>("list_drives"),

  convertDahuaBcd: (bcd: string, assumeUtc = false) =>
    invoke<ConvertedTimestamp>("timestamp_convert", {
      dahuaBcd: bcd,
      assumeUtc,
    }),

  convertHikEpoch: (epoch: number) =>
    invoke<ConvertedTimestamp>("timestamp_convert", { hikEpoch: epoch }),

  correlateTimeline: (inputs: string[], windowSeconds = 10, out?: string) =>
    invoke<CorrelationResult>("timeline_correlate", {
      inputs,
      window: windowSeconds,
      out,
    }),

  custodyAppend: (
    ledger: string,
    examiner: string,
    action: string,
    details?: Record<string, unknown>,
  ) =>
    invoke<CustodyEntry>("custody_append", {
      ledger,
      examiner,
      action,
      details: details ? JSON.stringify(details) : undefined,
    }),

  custodyVerify: (ledger: string) =>
    invoke<CustodyVerifyResult>("custody_verify", { ledger }),

  generateReport: (args: {
    case: string;
    hashes: string;
    timeline: string;
    custody: string;
    recovery?: string;
    ai?: string;
    out: string;
  }) =>
    invoke<JsonValue>("generate_report", {
      ...args,
      case: args.case,
    } as Record<string, unknown>),

  pythonInfo: () => invoke<JsonValue>("get_python_info"),
  appInfo: () => invoke<JsonValue>("get_app_info"),
};

export function errMsg(e: unknown): string {
  if (typeof e === "string") return e;
  if (e && typeof e === "object" && "message" in e) {
    return String((e as { message: unknown }).message);
  }
  return String(e);
}