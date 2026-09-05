use std::path::PathBuf;
use std::process::Command;

use serde::{Deserialize, Serialize};

use crate::core::error::CoreResult;

#[derive(Debug, Serialize, Deserialize)]
pub struct SidecarRequest {
    pub subcommand: String,
    pub args: Vec<String>,
    pub cwd: Option<String>,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct SidecarResponse {
    pub stdout: String,
    pub stderr: String,
    pub exit_code: i32,
    pub json: Option<serde_json::Value>,
}

pub fn sidecar_dir() -> CoreResult<PathBuf> {
    let manifest = option_env!("CARGO_MANIFEST_DIR");
    let base = match manifest {
        Some(m) => PathBuf::from(m).parent().map(|p| p.to_path_buf()).unwrap_or_default(),
        None => std::env::current_dir().unwrap_or_default(),
    };
    Ok(base)
}

pub fn run_python_sidecar(req: SidecarRequest) -> CoreResult<SidecarResponse> {
    let dir = sidecar_dir()?;
    let python = find_python().unwrap_or_else(|| "python".to_string());

    let mut cmd = Command::new(&python);
    cmd.current_dir(&dir).arg("sidecar.py").arg(&req.subcommand);
    for a in &req.args {
        cmd.arg(a);
    }
    if let Some(cwd) = &req.cwd {
        cmd.current_dir(cwd);
    }

    let output = cmd.output()?;
    let stdout = String::from_utf8_lossy(&output.stdout).to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).to_string();
    // Prefer parsing the entire stdout as one JSON document; fall back to
    // scanning lines for a JSON object (legacy single-line sidecar output).
    let json = serde_json::from_str::<serde_json::Value>(stdout.trim())
        .ok()
        .or_else(|| {
            stdout
                .lines()
                .rev()
                .find(|l| l.trim_start().starts_with('{'))
                .and_then(|l| serde_json::from_str::<serde_json::Value>(l).ok())
        });

    Ok(SidecarResponse {
        stdout,
        stderr,
        exit_code: output.status.code().unwrap_or(-1),
        json,
    })
}

fn find_python() -> Option<String> {
    // On Windows, "python3" is often the Microsoft Store app-execution-alias
    // stub, which runs but prints "Python was not found" and exits with an
    // error — so prefer "python"/"py" there and always verify the exit status.
    let candidates: Vec<&str> = if cfg!(windows) {
        vec!["python", "py", "python3"]
    } else {
        vec!["python3", "python"]
    };
    for candidate in &candidates {
        if is_working_python(candidate) {
            return Some((*candidate).to_string());
        }
    }
    // Fall back to well-known per-user install locations on Windows.
    if cfg!(windows) {
        if let Ok(local) = std::env::var("LOCALAPPDATA") {
            let root = PathBuf::from(local).join("Programs").join("Python");
            if let Ok(entries) = std::fs::read_dir(&root) {
                let mut versions: Vec<PathBuf> = entries
                    .flatten()
                    .map(|e| e.path().join("python.exe"))
                    .filter(|p| p.is_file())
                    .collect();
                versions.sort();
                if let Some(python) = versions.pop() {
                    let python = python.to_string_lossy().to_string();
                    if is_working_python(&python) {
                        return Some(python);
                    }
                }
            }
        }
    }
    None
}

fn is_working_python(candidate: &str) -> bool {
    match std::process::Command::new(candidate)
        .arg("--version")
        .output()
    {
        Ok(output) => {
            if !output.status.success() {
                return false;
            }
            let text = format!(
                "{}{}",
                String::from_utf8_lossy(&output.stdout),
                String::from_utf8_lossy(&output.stderr)
            );
            // The Store stub reports "Python was not found"; require a real
            // Python 3 interpreter.
            text.contains("Python 3")
        }
        Err(_) => false,
    }
}