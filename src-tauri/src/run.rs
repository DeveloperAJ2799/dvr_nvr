use tracing_subscriber::{fmt, EnvFilter};

use crate::commands::AppState;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let filter = EnvFilter::try_from_default_env()
        .unwrap_or_else(|_| EnvFilter::new("info,dvr_forensic_analyzer_lib=debug"));
    let _ = fmt().with_env_filter(filter).try_init();

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(tauri_plugin_fs::init())
        .manage(AppState::new())
.invoke_handler(tauri::generate_handler![
            crate::commands::get_settings,
            crate::commands::save_settings_cmd,
            crate::commands::create_case,
            crate::commands::list_cases,
            crate::commands::open_case,
            crate::commands::close_case,
            crate::commands::active_case,
            crate::commands::ingest_evidence,
            crate::commands::list_evidence,
            crate::commands::verify_evidence,
            crate::commands::verify_chain_of_custody,
            crate::commands::list_parsers,
            crate::commands::list_audit_events,
            crate::commands::detect_ffmpeg,
            crate::commands::detect_ffprobe,
            crate::commands::run_sidecar,
            crate::commands::detect_vendor,
            crate::commands::acquire_evidence,
            crate::commands::run_dahua_parser,
            crate::commands::run_hikvision_parser,
            crate::commands::decode_video,
            crate::commands::run_recovery,
            crate::commands::run_ai_analytics,
            crate::commands::generate_pdf_report,
            crate::commands::convert_bcd_to_ist,
            crate::commands::convert_epoch_to_ist,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}