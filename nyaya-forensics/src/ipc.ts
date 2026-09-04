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

/**
 * Thin typed wrapper over the 7 Python-sidecar Tauri commands + info helpers.
 * Every command rejects with `{ message }` when python exits non-zero.
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