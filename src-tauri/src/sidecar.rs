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
    let json = stdout
        .lines()
        .rev()
        .find(|l| l.trim_start().starts_with('{'))
        .and_then(|l| serde_json::from_str::<serde_json::Value>(l).ok());

    Ok(SidecarResponse {
        stdout,
        stderr,
        exit_code: output.status.code().unwrap_or(-1),
        json,
    })
}

fn find_python() -> Option<String> {
    for candidate in &["python3", "python", "py"] {
        if std::process::Command::new(candidate)
            .arg("--version")
            .output()
            .is_ok()
        {
            return Some((*candidate).to_string());
        }
    }
    None
}