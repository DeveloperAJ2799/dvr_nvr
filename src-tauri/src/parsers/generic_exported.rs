use std::path::Path;

use async_trait::async_trait;

use crate::core::error::{CoreError, CoreResult};
use crate::parsers::base::{
    ExtractionResult, IdentificationResult, ParseResult, ParserContext, RecoveryResult,
    ValidationResult, VendorParser,
};

pub struct GenericExportedParser;

#[async_trait]
impl VendorParser for GenericExportedParser {
    fn vendor_name(&self) -> String {
        "Generic Exported MP4/MKV".to_string()
    }

    fn vendor_id(&self) -> &'static str {
        "generic_exported"
    }

    fn priority(&self) -> u8 {
        10
    }

    fn description(&self) -> String {
        "Detects standard exported video files (.mp4/.mkv/.avi/.mov) and treats them as recordings.".to_string()
    }

    fn identify(&self, ctx: &ParserContext) -> CoreResult<IdentificationResult> {
        let mut confidence = 0.0_f32;
        let mut signals = Vec::new();
        if ctx.source_path.is_dir() {
            for entry in walkdir::WalkDir::new(&ctx.source_path)
                .max_depth(4)
                .into_iter()
                .flatten()
            {
                if entry.file_type().is_file() {
                    if let Some(ext) = entry.path().extension() {
                        let ext_lower = ext.to_string_lossy().to_lowercase();
                        if matches!(
                            ext_lower.as_str(),
                            "mp4" | "mkv" | "avi" | "mov" | "mpg" | "mpeg" | "ts" | "m4v"
                        ) {
                            confidence = confidence.max(0.9);
                            signals.push(format!("video file: {:?}", entry.path()));
                            break;
                        }
                    }
                }
            }
        } else if let Some(ext) = Path::new(&ctx.source_path).extension() {
            let ext_lower = ext.to_string_lossy().to_lowercase();
            if matches!(
                ext_lower.as_str(),
                "mp4" | "mkv" | "avi" | "mov" | "mpg" | "mpeg" | "ts" | "m4v"
            ) {
                confidence = 0.95;
                signals.push("single video file".to_string());
            }
        }

        Ok(IdentificationResult {
            vendor: self.vendor_name(),
            confidence,
            matched_signals: signals,
            warnings: Vec::new(),
        })
    }

    fn parse_filesystem(&self, ctx: &ParserContext) -> CoreResult<ParseResult> {
        let mut recordings = Vec::new();
        let metadata = Vec::new();
        let mut warnings = Vec::new();

        if ctx.source_path.is_file() {
            let rec = build_recording_from_path(&ctx.source_path, &ctx.evidence_id, self.vendor_id(), &self.vendor_name())?;
            recordings.push(rec);
        } else if ctx.source_path.is_dir() {
            for entry in walkdir::WalkDir::new(&ctx.source_path)
                .max_depth(5)
                .into_iter()
                .flatten()
            {
                if !entry.file_type().is_file() {
                    continue;
                }
                let path = entry.path();
                if let Some(ext) = path.extension() {
                    let ext_lower = ext.to_string_lossy().to_lowercase();
                    if matches!(
                        ext_lower.as_str(),
                        "mp4" | "mkv" | "avi" | "mov" | "mpg" | "mpeg" | "ts" | "m4v"
                    ) {
                        match build_recording_from_path(path, &ctx.evidence_id, self.vendor_id(), &self.vendor_name()) {
                            Ok(rec) => recordings.push(rec),
                            Err(e) => warnings.push(format!("Skipped {:?}: {}", path, e)),
                        }
                    }
                }
            }
        } else {
            return Err(CoreError::InvalidInput(format!(
                "Source path is neither file nor directory: {:?}",
                ctx.source_path
            )));
        }

        Ok(ParseResult {
            recordings,
            metadata,
            warnings,
            errors: Vec::new(),
        })
    }

    async fn extract_videos(
        &self,
        _ctx: &ParserContext,
        parse: &ParseResult,
    ) -> CoreResult<ExtractionResult> {
        let mut extracted = Vec::new();
        let warnings = Vec::new();

        for rec in &parse.recordings {
            let src = rec.original_file_path.clone();
            extracted.push(crate::parsers::base::ExtractedFile {
                recording_id: rec.recording_id.clone(),
                source_path: src.clone(),
                output_path: src.clone(),
                container_format: rec.container_format.clone(),
                video_codec: rec.video_codec.clone(),
                audio_codec: rec.audio_codec.clone(),
                md5: String::new(),
                sha256: String::new(),
            });
        }

        Ok(ExtractionResult {
            extracted_files: extracted,
            warnings,
            errors: Vec::new(),
        })
    }

    fn recover_deleted(&self, _ctx: &ParserContext) -> CoreResult<RecoveryResult> {
        Ok(RecoveryResult {
            recovered: Vec::new(),
            warnings: vec!["Generic parser does not perform recovery".to_string()],
            errors: Vec::new(),
        })
    }

    fn validate_output(&self, extraction: &ExtractionResult) -> CoreResult<ValidationResult> {
        Ok(ValidationResult {
            valid: !extraction.extracted_files.is_empty(),
            issues: if extraction.extracted_files.is_empty() {
                vec!["No extracted files produced".to_string()]
            } else {
                Vec::new()
            },
        })
    }
}

fn build_recording_from_path(
    path: &Path,
    evidence_id: &str,
    parser_id: &str,
    parser_name: &str,
) -> CoreResult<crate::parsers::base::Recording> {
    use crate::core::time::now_utc_string;
    use uuid::Uuid;

    let recording_id = format!("REC-{}", &Uuid::new_v4().to_string()[..8].to_uppercase());
    let camera_id = path
        .file_stem()
        .map(|s| s.to_string_lossy().to_string())
        .unwrap_or_else(|| "CAM-UNKNOWN".to_string());
    let now = now_utc_string();

    Ok(crate::parsers::base::Recording {
        recording_id,
        evidence_id: evidence_id.to_string(),
        camera_id,
        camera_name: String::new(),
        start_time_raw: now.clone(),
        start_time_utc: now.clone(),
        end_time_raw: now.clone(),
        end_time_utc: now,
        duration_seconds: 0,
        event_type: "continuous".to_string(),
        original_file_path: path.to_string_lossy().to_string(),
        extracted_file_path: path.to_string_lossy().to_string(),
        container_format: path
            .extension()
            .map(|e| e.to_string_lossy().to_lowercase())
            .unwrap_or_else(|| "unknown".to_string()),
        video_codec: "unknown".to_string(),
        audio_codec: "unknown".to_string(),
        parser_name: format!("{} ({})", parser_name, parser_id),
        confidence: 0.7,
        status: "discovered".to_string(),
    })
}