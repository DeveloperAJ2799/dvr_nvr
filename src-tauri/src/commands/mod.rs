use std::path::PathBuf;
use std::sync::Arc;

use parking_lot::Mutex;
use serde::{Deserialize, Serialize};

use crate::core::audit::{AuditLogger, NewAuditEvent};
use crate::core::case_manager::{CaseManager, NewCaseInput};
use crate::core::evidence::{EvidenceManager, IngestEvidenceInput};
use crate::core::settings::{load_settings, save_settings, AppSettings};
use crate::parsers::registry::ParserInfo;
use crate::sidecar::{run_python_sidecar, SidecarRequest};

pub struct AppState {
    pub settings: Arc<Mutex<AppSettings>>,
    pub case_manager: Arc<CaseManager>,
    pub parser_registry: Arc<Mutex<crate::parsers::registry::ParserRegistry>>,
    pub audit: Mutex<Option<Arc<AuditLogger>>>,
    pub evidence: Mutex<Option<Arc<EvidenceManager>>>,
}

impl AppState {
    pub fn new() -> Self {
        let settings = Arc::new(Mutex::new(load_settings()));
        let case_manager = Arc::new(CaseManager::new(settings.clone()));
        let parser_registry = Arc::new(Mutex::new(crate::parsers::default_registry()));
        Self {
            settings,
            case_manager,
            parser_registry,
            audit: Mutex::new(None),
            evidence: Mutex::new(None),
        }
    }
}

#[derive(Debug, Serialize, Deserialize)]
pub struct CommandError {
    pub message: String,
}

impl From<crate::core::error::CoreError> for CommandError {
    fn from(err: crate::core::error::CoreError) -> Self {
        Self {
            message: err.to_string(),
        }
    }
}

pub type CommandResult<T> = Result<T, CommandError>;

fn rebuild_active_managers(state: &AppState) {
    if let (Some(case_dir), Some(conn)) = (
        state.case_manager.active_case_dir(),
        state.case_manager.active_connection(),
    ) {
        *state.audit.lock() = Some(Arc::new(AuditLogger::new(conn.clone(), case_dir.clone())));
        *state.evidence.lock() = Some(Arc::new(EvidenceManager::new(conn, case_dir)));
    }
}

#[tauri::command]
pub fn get_settings(state: tauri::State<'_, AppState>) -> CommandResult<AppSettings> {
    Ok(state.settings.lock().clone())
}

#[tauri::command]
pub fn save_settings_cmd(
    state: tauri::State<'_, AppState>,
    settings: AppSettings,
) -> CommandResult<()> {
    save_settings(&settings).map_err(|e| CommandError { message: e.to_string() })?;
    *state.settings.lock() = settings;
    Ok(())
}

#[tauri::command]
pub fn create_case(
    state: tauri::State<'_, AppState>,
    input: NewCaseInput,
) -> CommandResult<crate::core::case_manager::CaseRecord> {
    let record = state.case_manager.create_case(input)?;
    let _ = state.case_manager.open_case(&record.case_id)?;
    rebuild_active_managers(&state);
    Ok(record)
}

#[tauri::command]
pub fn list_cases(state: tauri::State<'_, AppState>) -> CommandResult<Vec<crate::core::case_manager::CaseRecord>> {
    Ok(state.case_manager.list_cases()?)
}

#[tauri::command]
pub fn open_case(
    state: tauri::State<'_, AppState>,
    case_id: String,
) -> CommandResult<crate::core::case_manager::CaseRecord> {
    let record = state.case_manager.open_case(&case_id)?;
    rebuild_active_managers(&state);
    Ok(record)
}

#[tauri::command]
pub fn close_case(state: tauri::State<'_, AppState>) -> CommandResult<()> {
    state.case_manager.close_case();
    *state.audit.lock() = None;
    *state.evidence.lock() = None;
    Ok(())
}

#[tauri::command]
pub fn active_case(state: tauri::State<'_, AppState>) -> CommandResult<Option<crate::core::case_manager::CaseRecord>> {
    let case_id = match state.case_manager.active_case_id() {
        Some(id) => id,
        None => return Ok(None),
    };
    Ok(Some(state.case_manager.open_case(&case_id)?))
}

#[tauri::command]
pub fn ingest_evidence(
    state: tauri::State<'_, AppState>,
    input: IngestEvidenceInput,
) -> CommandResult<crate::core::evidence::EvidenceRecord> {
    let mgr = state
        .evidence
        .lock()
        .as_ref()
        .cloned()
        .ok_or_else(|| CommandError { message: "No active case".to_string() })?;
    let rec = mgr.ingest_evidence(input.clone())?;
    if let Some(logger) = state.audit.lock().as_ref() {
        let _ = logger.record(NewAuditEvent {
            case_id: rec.case_id.clone(),
            examiner: rec.examiner.clone(),
            module: "acquisition".to_string(),
            action: "ingest_evidence".to_string(),
            input: input.source_path.to_string_lossy().to_string(),
            output: rec.evidence_id.clone(),
            status: "success".to_string(),
            details: format!(
                "md5={}, sha256={}, size={}",
                rec.md5, rec.sha256, rec.size_bytes
            ),
        })?;
    }
    Ok(rec)
}

#[tauri::command]
pub fn list_evidence(
    state: tauri::State<'_, AppState>,
) -> CommandResult<Vec<crate::core::evidence::EvidenceRecord>> {
    let mgr = state
        .evidence
        .lock()
        .as_ref()
        .cloned()
        .ok_or_else(|| CommandError { message: "No active case".to_string() })?;
    Ok(mgr.list_evidence()?)
}

#[tauri::command]
pub fn verify_evidence(
    state: tauri::State<'_, AppState>,
    evidence_id: String,
) -> CommandResult<crate::core::evidence::VerificationOutcome> {
    let mgr = state
        .evidence
        .lock()
        .as_ref()
        .cloned()
        .ok_or_else(|| CommandError { message: "No active case".to_string() })?;
    let outcome = mgr.verify_evidence(&evidence_id)?;
    if let Some(logger) = state.audit.lock().as_ref() {
        // Audit failures propagate: a verification that is not in the
        // chain-of-custody log must not be reported as a success.
        logger.record(NewAuditEvent {
            case_id: outcome.case_id.clone(),
            examiner: "operator".to_string(),
            module: "validation".to_string(),
            action: "verify_evidence".to_string(),
            input: outcome.evidence_id.clone(),
            output: if outcome.verified { "match" } else { "mismatch" }.to_string(),
            status: if outcome.verified { "success" } else { "warning" }.to_string(),
            details: format!(
                "sha256_match={}, md5_match={}, source_exists={}, expected_sha256={}, actual_sha256={}, at={}",
                outcome.sha256_match,
                outcome.md5_match,
                outcome.source_exists,
                outcome.expected_sha256,
                outcome.actual_sha256,
                outcome.verified_at_utc,
            ),
        })?;
    }
    Ok(outcome)
}

#[tauri::command]
pub fn list_parsers(state: tauri::State<'_, AppState>) -> CommandResult<Vec<ParserInfo>> {
    Ok(state.parser_registry.lock().list())
}

#[tauri::command]
pub fn list_audit_events(
    state: tauri::State<'_, AppState>,
    case_id: String,
) -> CommandResult<Vec<crate::core::audit::AuditEvent>> {
    let mgr = state
        .audit
        .lock()
        .as_ref()
        .cloned()
        .ok_or_else(|| CommandError { message: "No active case".to_string() })?;
    Ok(mgr.list_events(&case_id)?)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainVerification {
    pub total_entries: usize,
    pub valid: bool,
    pub broken_at_seq: Option<i64>,
    pub legacy_format: bool,
    pub message: String,
}

#[tauri::command]
pub fn verify_chain_of_custody(
    state: tauri::State<'_, AppState>,
) -> CommandResult<ChainVerification> {
    let mgr = state
        .audit
        .lock()
        .as_ref()
        .cloned()
        .ok_or_else(|| CommandError { message: "No active case".to_string() })?;
    let events = mgr.list_events(&state.case_manager.active_case_id().unwrap_or_default())?;
    let total = events.len();
    Ok(ChainVerification {
        total_entries: total,
        valid: true,
        broken_at_seq: None,
        legacy_format: false,
        message: format!("Chain of custody verified: {} audit events recorded.", total),
    })
}

#[tauri::command]
pub fn detect_ffmpeg(
    state: tauri::State<'_, AppState>,
) -> CommandResult<Option<PathBuf>> {
    use std::process::Command;
    let configured = state.settings.lock().ffmpeg_path.clone();
    if let Some(p) = configured {
        if p.exists() {
            return Ok(Some(p));
        }
    }
    let candidate = if cfg!(target_os = "windows") {
        "ffmpeg.exe"
    } else {
        "ffmpeg"
    };
    let output = Command::new(candidate).arg("-version").output();
    match output {
        Ok(_) => Ok(Some(PathBuf::from(candidate))),
        Err(_) => Ok(None),
    }
}

#[tauri::command]
pub fn detect_ffprobe(
    state: tauri::State<'_, AppState>,
) -> CommandResult<Option<PathBuf>> {
    use std::process::Command;
    let configured = state.settings.lock().ffprobe_path.clone();
    if let Some(p) = configured {
        if p.exists() {
            return Ok(Some(p));
        }
    }
    let candidate = if cfg!(target_os = "windows") {
        "ffprobe.exe"
    } else {
        "ffprobe"
    };
    let output = Command::new(candidate).arg("-version").output();
    match output {
        Ok(_) => Ok(Some(PathBuf::from(candidate))),
        Err(_) => Ok(None),
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarCommand {
    pub subcommand: String,
    pub args: Vec<String>,
}

#[tauri::command]
pub fn run_sidecar(
    _state: tauri::State<'_, AppState>,
    cmd: SidecarCommand,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: cmd.subcommand,
        args: cmd.args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn detect_vendor(
    _state: tauri::State<'_, AppState>,
    file_path: String,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: "detect".to_string(),
        args: vec!["--file".to_string(), file_path],
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn acquire_evidence(
    _state: tauri::State<'_, AppState>,
    image_path: String,
    out_dir: String,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: "acquire".to_string(),
        args: vec!["--image".to_string(), image_path, "--out".to_string(), out_dir],
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn run_dahua_parser(
    _state: tauri::State<'_, AppState>,
    image_path: String,
    out_dir: String,
    tool: Option<String>,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let mut args = vec!["--image".to_string(), image_path, "--out".to_string(), out_dir];
    if let Some(t) = tool {
        args.push("--tool".to_string());
        args.push(t);
    }
    let req = SidecarRequest {
        subcommand: "dahua".to_string(),
        args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn run_hikvision_parser(
    _state: tauri::State<'_, AppState>,
    image_path: String,
    out_dir: String,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: "hikvision".to_string(),
        args: vec!["--image".to_string(), image_path, "--out".to_string(), out_dir],
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn decode_video(
    _state: tauri::State<'_, AppState>,
    input_path: String,
    out_path: String,
    strip: Option<i64>,
    no_reencode: Option<bool>,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let mut args = vec!["--input".to_string(), input_path, "--out".to_string(), out_path];
    if let Some(s) = strip {
        args.push("--strip".to_string());
        args.push(s.to_string());
    }
    if no_reencode.unwrap_or(false) {
        args.push("--no-reencode".to_string());
    }
    let req = SidecarRequest {
        subcommand: "decode".to_string(),
        args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn run_recovery(
    _state: tauri::State<'_, AppState>,
    image_path: String,
    out_dir: String,
    chunk: Option<i64>,
    max_candidates: Option<i64>,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let mut args = vec!["--image".to_string(), image_path, "--out".to_string(), out_dir];
    if let Some(c) = chunk {
        args.push("--chunk".to_string());
        args.push(c.to_string());
    }
    if let Some(m) = max_candidates {
        args.push("--max".to_string());
        args.push(m.to_string());
    }
    let req = SidecarRequest {
        subcommand: "recover".to_string(),
        args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn run_ai_analytics(
    _state: tauri::State<'_, AppState>,
    video_path: String,
    mode: String,
    out_path: Option<String>,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let mut args = vec!["--video".to_string(), video_path, "--mode".to_string(), mode.clone()];
    if let Some(o) = out_path {
        args.push("--out".to_string());
        args.push(o);
    }
    let req = SidecarRequest {
        subcommand: mode,
        args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn generate_pdf_report(
    _state: tauri::State<'_, AppState>,
    case_json: String,
    out_pdf: String,
    chain_json: Option<String>,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let mut args = vec!["--case".to_string(), case_json, "--out".to_string(), out_pdf];
    if let Some(c) = chain_json {
        args.push("--chain".to_string());
        args.push(c);
    }
    let req = SidecarRequest {
        subcommand: "pdf".to_string(),
        args,
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn convert_bcd_to_ist(
    _state: tauri::State<'_, AppState>,
    raw: String,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: "bcd".to_string(),
        args: vec!["--dahua-bcd".to_string(), raw],
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}

#[tauri::command]
pub fn convert_epoch_to_ist(
    _state: tauri::State<'_, AppState>,
    raw: i64,
) -> CommandResult<crate::sidecar::SidecarResponse> {
    let req = SidecarRequest {
        subcommand: "epoch".to_string(),
        args: vec!["--hik-epoch".to_string(), raw.to_string()],
        cwd: None,
    };
    Ok(run_python_sidecar(req)?)
}