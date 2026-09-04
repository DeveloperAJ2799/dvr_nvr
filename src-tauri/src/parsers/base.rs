use std::path::PathBuf;

use async_trait::async_trait;
use serde::{Deserialize, Serialize};

use crate::core::error::CoreResult;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IdentificationResult {
    pub vendor: String,
    pub confidence: f32,
    pub matched_signals: Vec<String>,
    pub warnings: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Recording {
    pub recording_id: String,
    pub evidence_id: String,
    pub camera_id: String,
    pub camera_name: String,
    pub start_time_raw: String,
    pub start_time_utc: String,
    pub end_time_raw: String,
    pub end_time_utc: String,
    pub duration_seconds: i64,
    pub event_type: String,
    pub original_file_path: String,
    pub extracted_file_path: String,
    pub container_format: String,
    pub video_codec: String,
    pub audio_codec: String,
    pub parser_name: String,
    pub confidence: f32,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractedFile {
    pub recording_id: String,
    pub source_path: String,
    pub output_path: String,
    pub container_format: String,
    pub video_codec: String,
    pub audio_codec: String,
    pub md5: String,
    pub sha256: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetadataEntry {
    pub recording_id: String,
    pub key: String,
    pub value: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParseResult {
    pub recordings: Vec<Recording>,
    pub metadata: Vec<MetadataEntry>,
    pub warnings: Vec<String>,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ExtractionResult {
    pub extracted_files: Vec<ExtractedFile>,
    pub warnings: Vec<String>,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RecoveryResult {
    pub recovered: Vec<serde_json::Value>,
    pub warnings: Vec<String>,
    pub errors: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ValidationResult {
    pub valid: bool,
    pub issues: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ParserContext {
    pub evidence_id: String,
    pub source_path: PathBuf,
    pub case_dir: PathBuf,
    pub timezone_assumption: String,
    pub ffmpeg_path: Option<PathBuf>,
    pub ffprobe_path: Option<PathBuf>,
}

#[async_trait]
pub trait VendorParser: Send + Sync {
    fn vendor_name(&self) -> String;

    fn vendor_id(&self) -> &'static str;

    fn identify(&self, ctx: &ParserContext) -> CoreResult<IdentificationResult>;

    fn parse_filesystem(&self, ctx: &ParserContext) -> CoreResult<ParseResult>;

    async fn extract_videos(&self, ctx: &ParserContext, parse: &ParseResult) -> CoreResult<ExtractionResult>;

    fn recover_deleted(&self, ctx: &ParserContext) -> CoreResult<RecoveryResult>;

    fn validate_output(&self, _extraction: &ExtractionResult) -> CoreResult<ValidationResult> {
        Ok(ValidationResult {
            valid: true,
            issues: Vec::new(),
        })
    }

    fn priority(&self) -> u8 {
        50
    }

    fn description(&self) -> String {
        format!("Vendor parser for {}", self.vendor_name())
    }
}