//! NYAYA Forensics — Tauri v2 application entry (Rust side).
//!
//! The Rust side is intentionally thin: it exposes a small set of Tauri
//! commands that shell out to the Python forensic core (`core/*.py`,
//! `plugins/*.py`, `ai/*.py`, `reporting/*.py`) via `std::process::Command`.
//! All heavy forensics live in Python so plugins can be swapped without
//! rebuilding the Tauri binary.
mod commands;

use commands::{AppState, CommandError, CommandResult};

#[tauri::command]
fn detect_vendor(image_path: String) -> commands::CommandResult<serde_json::Value> {
    let args = vec!["core/vendor_detect.py".to_string(), image_path];
    commands::run_python(&args, "vendor detection failed")
}

#[tauri::command]
fn acquire_image(
    input: String,
    output: String,
    verify: Option<bool>,
) -> commands::CommandResult<serde_json::Value> {
    let mut args = vec!["core/acquisition.py".to_string(), input];
    args.push("--output".into());
    args.push(output);
    if verify.unwrap_or(true) {
        args.push("--verify".into());
    }
    commands::run_python(&args, "acquisition failed")
}

#[tauri::command]
fn extract_dahua(image: String, outdir: String) -> commands::CommandResult<serde_json::Value> {
    let args = vec![
        "plugins/dahua_wrapper.py".to_string(),
        image,
        "--outdir".to_string(),
        outdir,
    ];
    commands::run_python(&args, "dahua extraction failed")
}

#[tauri::command]
fn decode_video(
    input: String,
    output: Option<String>,
    header_bytes: Option<u32>,
) -> commands::CommandResult<serde_json::Value> {
    let mut args = vec!["core/decoder.py".to_string(), input];
    if let Some(o) = output {
        args.push("--output".into());
        args.push(o);
    }
    if let Some(h) = header_bytes {
        args.push("--header-bytes".into());
        args.push(h.to_string());
    }
    commands::run_python(&args, "video decode failed")
}

#[tauri::command]
fn carve_deleted(
    image: String,
    workdir: String,
    join_gap_mb: Option<u32>,
) -> commands::CommandResult<serde_json::Value> {
    let mut args = vec!["core/recovery.py".to_string(), image];
    args.push("--workdir".into());
    args.push(workdir);
    if let Some(g) = join_gap_mb {
        args.push("--join-gap-mb".into());
        args.push(g.to_string());
    }
    commands::run_python(&args, "deleted recovery failed")
}

#[tauri::command]
fn run_ai(
    video: String,
    events_path: Option<String>,
) -> commands::CommandResult<serde_json::Value> {
    let mut args = vec!["ai/detector.py".to_string(), video];
    if let Some(p) = events_path {
        args.push("--events".into());
        args.push(p);
    }
    commands::run_python(&args, "AI analytics failed")
}

#[tauri::command]
fn generate_report(
    case: String,
    hashes: String,
    timeline: String,
    custody: String,
    recovery: Option<String>,
    ai: Option<String>,
    out: String,
) -> commands::CommandResult<serde_json::Value> {
    let mut args = vec![
        "reporting/pdf_gen.py".to_string(),
        "--case".into(), case,
        "--hash".into(), hashes,
        "--timeline".into(), timeline,
        "--custody".into(), custody,
        "--out".into(), out,
    ];
    if let Some(r) = recovery {
        args.push("--recovery".into());
        args.push(r);
    }
    if let Some(a) = ai {
        args.push("--ai".into());
        args.push(a);
    }
    commands::run_python(&args, "report generation failed")
}

/// Generic JSON-python runner: script path (repo-relative) + raw CLI args.
/// Every new forensic capability is exposed to the UI through this one fn.
fn run_py(script_args: &[String], context: &str) -> CommandResult<serde_json::Value> {
    commands::run_python(script_args, context)
}

#[tauri::command]
fn list_drives() -> CommandResult<serde_json::Value> {
    run_py(
        &["core/acquisition.py".to_string(), "--list-drives".to_string()],
        "drive enumeration failed",
    )
}

#[tauri::command]
fn timestamp_convert(
    dahua_bcd: Option<String>,
    hik_epoch: Option<f64>,
    assume_utc: Option<bool>,
) -> CommandResult<serde_json::Value> {
    let mut a = vec!["core/timestamps.py".to_string()];
    if let Some(bcd) = dahua_bcd {
        a.push("--dahua-bcd".into());
        a.push(bcd);
    } else if let Some(ep) = hik_epoch {
        a.push("--hik-epoch".into());
        a.push(format!("{}", ep as i64));
    } else {
        return Err(CommandError {
            message: "timestamp_convert: provide dahua_bcd or hik_epoch".into(),
        });
    }
    if assume_utc.unwrap_or(false) {
        a.push("--assume-utc".into());
    }
    run_py(&a, "timestamp conversion failed")
}

#[tauri::command]
fn timeline_correlate(
    inputs: Vec<String>,
    window: Option<f64>,
    out: Option<String>,
) -> CommandResult<serde_json::Value> {
    let mut a = vec!["core/timeline.py".to_string(), "--inputs".into()];
    a.extend(inputs);
    a.push("--window".into());
    a.push(window.unwrap_or(10.0).to_string());
    if let Some(o) = out {
        a.push("--out".into());
        a.push(o);
    }
    run_py(&a, "timeline correlation failed")
}

#[tauri::command]
fn custody_append(
    ledger: String,
    examiner: String,
    action: String,
    details: Option<String>,
) -> CommandResult<serde_json::Value> {
    let mut a = vec![
        "core/custody.py".to_string(),
        "append".into(),
        "--ledger".into(),
        ledger,
        "--examiner".into(),
        examiner,
        "--action".into(),
        action,
    ];
    if let Some(d) = details {
        a.push("--details".into());
        a.push(d);
    }
    run_py(&a, "custody append failed")
}

#[tauri::command]
fn custody_verify(ledger: String) -> CommandResult<serde_json::Value> {
    run_py(
        &[
            "core/custody.py".to_string(),
            "verify".into(),
            "--ledger".into(),
            ledger,
        ],
        "custody verification failed",
    )
}

#[tauri::command]
fn run_ai_mode(
    video: String,
    mode: Option<String>,
    events_path: Option<String>,
) -> CommandResult<serde_json::Value> {
    let mut a = vec![
        "ai/detector.py".to_string(),
        video,
        "--mode".into(),
        mode.unwrap_or_else(|| "objects".into()),
    ];
    if let Some(p) = events_path {
        a.push("--events".into());
        a.push(p);
    }
    run_py(&a, "AI analytics failed")
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .plugin(tauri_plugin_shell::init())
        .manage(AppState::default())
        .invoke_handler(tauri::generate_handler![
            detect_vendor,
            acquire_image,
            extract_dahua,
            decode_video,
            carve_deleted,
            run_ai,
            generate_report,
            list_drives,
            timestamp_convert,
            timeline_correlate,
            custody_append,
            custody_verify,
            run_ai_mode,
            commands::get_python_info,
            commands::get_app_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running NYAYA Forensics");
}