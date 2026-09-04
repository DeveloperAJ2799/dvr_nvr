use std::path::PathBuf;

#[derive(Debug, Clone, serde::Serialize, serde::Deserialize)]
pub struct AppSettings {
    pub case_storage_dir: PathBuf,
    pub ffmpeg_path: Option<PathBuf>,
    pub ffprobe_path: Option<PathBuf>,
    pub default_timezone: String,
    pub ai_enabled: bool,
    pub hash_algorithms: Vec<String>,
    pub theme: String,
    pub log_level: String,
    pub carving_chunk_size: usize,
    pub recovery_confidence_threshold: f32,
}

impl Default for AppSettings {
    fn default() -> Self {
        let mut default_dir = dirs_next().unwrap_or_else(|| PathBuf::from("./cases"));
        if !default_dir.ends_with("cases") {
            default_dir.push("cases");
        }
        Self {
            case_storage_dir: default_dir,
            ffmpeg_path: None,
            ffprobe_path: None,
            default_timezone: "UTC".to_string(),
            ai_enabled: false,
            hash_algorithms: vec!["md5".to_string(), "sha256".to_string()],
            theme: "dark".to_string(),
            log_level: "info".to_string(),
            carving_chunk_size: 1024 * 1024,
            recovery_confidence_threshold: 0.5,
        }
    }
}

fn dirs_next() -> Option<PathBuf> {
    if let Some(base) = std::env::var_os("APPDATA") {
        return Some(PathBuf::from(base).join("DvrForensicAnalyzer"));
    }
    if let Some(base) = std::env::var_os("HOME") {
        return Some(PathBuf::from(base).join(".dvr-forensic-analyzer"));
    }
    None
}

pub fn settings_path() -> PathBuf {
    let base = dirs_next().unwrap_or_else(|| PathBuf::from("."));
    base.join("settings.json")
}

pub fn load_settings() -> AppSettings {
    let path = settings_path();
    if path.exists() {
        if let Ok(text) = std::fs::read_to_string(&path) {
            if let Ok(parsed) = serde_json::from_str::<AppSettings>(&text) {
                return parsed;
            }
        }
    }
    AppSettings::default()
}

pub fn save_settings(settings: &AppSettings) -> std::io::Result<()> {
    let path = settings_path();
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)?;
    }
    let text = serde_json::to_string_pretty(settings)
        .map_err(|e| std::io::Error::new(std::io::ErrorKind::InvalidData, e))?;
    std::fs::write(path, text)
}