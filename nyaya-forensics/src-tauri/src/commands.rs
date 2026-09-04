//! NYAYA Forensics — Tauri command layer + Python sidecar runner.
//!
//! Every heavy operation shells out to the Python forensic core. Python
//! writes JSON to stdout; we surface it verbatim to the React frontend.
use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};
use std::sync::Mutex as StdMutex;

#[derive(Debug, Serialize, Deserialize)]
pub struct CommandError {
    pub message: String,
}

pub type CommandResult<T> = Result<T, CommandError>;

/// Resolve the repo root (a few folders up from `src-tauri/src/`).
pub fn repo_root() -> PathBuf {
    let exe = std::env::current_exe().unwrap_or_default();
    // Debug/Release: <root>/src-tauri/target/{debug,release}/nyaya-forensics.exe
    // exe(0) -> debug|release(1) -> target(2) -> src-tauri(3) -> <root>(4)
    exe.ancestors()
        .nth(4)
        .map(|p| p.to_path_buf())
        .unwrap_or_else(|| PathBuf::from("."))
}

/// Runs `python <script> <args...>` in the repo root and parses stdout JSON.
pub fn run_python(args: &[String], context: &str) -> CommandResult<serde_json::Value> {
    let root = repo_root();
    let script = root.join(&args[0]);
    if !script.exists() {
        return Err(CommandError {
            message: format!(
                "{}: script not found: {} (root={})",
                context,
                script.display(),
                root.display()
            ),
        });
    }
    let mut cmd = Command::new(python_bin());
    cmd.current_dir(&root);
    cmd.arg(script);
    for a in &args[1..] {
        cmd.arg(a);
    }
    match cmd.output() {
        Err(e) => Err(CommandError {
            message: format!("{}: cannot start python: {}", context, e),
        }),
        Ok(out) => {
            if !out.status.success() {
                let stderr = String::from_utf8_lossy(&out.stderr);
                return Err(CommandError {
                    message: format!("{}: python exited {}\n{}",
                                     context, out.status, stderr.chars().take(2000).collect::<String>()),
                });
            }
            let stdout = String::from_utf8_lossy(&out.stdout);
            serde_json::from_str(stdout.trim()).map_err(|e| CommandError {
                message: format!("{}: invalid JSON from python: {}", context, e),
            })
        }
    }
}

#[allow(dead_code)]
fn python_bin() -> String {
    std::env::var("NYAYA_PYTHON")
        .unwrap_or_else(|_| if cfg!(windows) { "python".into() } else { "python3".into() })
}

#[allow(dead_code)]
fn python_env() -> String {
    python_bin()
}

#[allow(dead_code)] // request_counter is reserved for future request tracing
pub struct AppState {
    pub request_counter: StdMutex<u64>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            request_counter: StdMutex::new(0),
        }
    }
}

#[tauri::command]
pub fn get_python_info() -> CommandResult<serde_json::Value> {
    let bin = python_bin();
    let mut cmd = Command::new(&bin);
    cmd.arg("--version");
    match cmd.output() {
        Ok(out) if out.status.success() => Ok(serde_json::json!({
            "ok": true,
            "python": bin,
            "version": String::from_utf8_lossy(&out.stdout).trim_end(),
        })),
        Ok(out) => Ok(serde_json::json!({
            "ok": false,
            "python": bin,
            "stderr": String::from_utf8_lossy(&out.stderr).trim_end(),
        })),
        Err(e) => Ok(serde_json::json!({
            "ok": false,
            "python": bin,
            "error": e.to_string(),
        })),
    }
}

#[tauri::command]
pub fn get_app_info() -> CommandResult<serde_json::Value> {
    Ok(serde_json::json!({
        "name": "NYAYA Forensics",
        "version": env!("CARGO_PKG_VERSION"),
        "vendor_targets": ["Dahua", "CP Plus", "Honeywell", "TP-Link",
                           "Godrej", "Uniview", "HIKVISION", "Matrix"],
        "layers": 7,
        "offline": true,
        "custody_ledger": "SHA-256 hash-chained JSONL",
        "correlation_window_seconds": 10,
    }))
}