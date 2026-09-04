//! NYAYA Forensics — Tauri v2 application entry (Rust side).
//!
//! The Rust side is intentionally thin: it exposes a small set of Tauri
//! commands that shell out to the Python forensic core (`core/*.py`,
//! `plugins/*.py`, `ai/*.py`, `reporting/*.py`) via `std::process::Command`.
//! All heavy forensics live in Python so plugins can be swapped without
//! rebuilding the Tauri binary.
mod commands;

use commands::AppState;

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
            commands::get_python_info,
            commands::get_app_info,
        ])
        .run(tauri::generate_context!())
        .expect("error while running NYAYA Forensics");
}