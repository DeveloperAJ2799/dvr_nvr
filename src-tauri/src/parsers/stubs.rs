use std::path::Path;

use async_trait::async_trait;

use crate::core::error::CoreResult;
use crate::parsers::base::{
    ExtractionResult, IdentificationResult, ParseResult, ParserContext, RecoveryResult,
    ValidationResult, VendorParser,
};

macro_rules! stub_parser {
    ($name:ident, $vendor:literal, $vendor_id:literal, $priority:expr, $desc:literal, $signals:expr) => {
        pub struct $name;

        #[async_trait]
        impl VendorParser for $name {
            fn vendor_name(&self) -> String {
                $vendor.to_string()
            }

            fn vendor_id(&self) -> &'static str {
                $vendor_id
            }

            fn priority(&self) -> u8 {
                $priority
            }

            fn description(&self) -> String {
                $desc.to_string()
            }

            fn identify(&self, ctx: &ParserContext) -> CoreResult<IdentificationResult> {
                let mut confidence: f32 = 0.0;
                let mut matched_signals = Vec::new();

                if ctx.source_path.is_dir() {
                    let root_name = Path::new(&ctx.source_path)
                        .file_name()
                        .map(|n| n.to_string_lossy().to_lowercase())
                        .unwrap_or_default();
                    for sig in $signals.iter() {
                        if root_name.contains(sig) {
                            confidence = confidence.max(0.6);
                            matched_signals.push(format!("folder name contains '{}'", sig));
                        }
                    }
                    for entry in walkdir::WalkDir::new(&ctx.source_path)
                        .max_depth(3)
                        .into_iter()
                        .flatten()
                    {
                        if !entry.file_type().is_file() {
                            continue;
                        }
                        let name_lower = entry
                            .file_name()
                            .to_string_lossy()
                            .to_lowercase();
                        for sig in $signals.iter() {
                            if name_lower.contains(sig) {
                                confidence = confidence.max(0.55);
                                matched_signals
                                    .push(format!("file '{}' matched signal '{}'", name_lower, sig));
                                break;
                            }
                        }
                    }
                }

                Ok(IdentificationResult {
                    vendor: self.vendor_name(),
                    confidence,
                    matched_signals,
                    warnings: vec![format!(
                        "{} parser is a stub; full parsing not available yet.",
                        self.vendor_name()
                    )],
                })
            }

            fn parse_filesystem(&self, _ctx: &ParserContext) -> CoreResult<ParseResult> {
                Ok(ParseResult {
                    recordings: Vec::new(),
                    metadata: Vec::new(),
                    warnings: vec![format!(
                        "{} parser is a stub; no recordings parsed.",
                        self.vendor_name()
                    )],
                    errors: Vec::new(),
                })
            }

            async fn extract_videos(
                &self,
                _ctx: &ParserContext,
                _parse: &ParseResult,
            ) -> CoreResult<ExtractionResult> {
                Ok(ExtractionResult {
                    extracted_files: Vec::new(),
                    warnings: vec![format!(
                        "{} parser is a stub; no extraction performed.",
                        self.vendor_name()
                    )],
                    errors: Vec::new(),
                })
            }

            fn recover_deleted(&self, _ctx: &ParserContext) -> CoreResult<RecoveryResult> {
                Ok(RecoveryResult {
                    recovered: Vec::new(),
                    warnings: vec![format!(
                        "{} parser is a stub; no recovery performed.",
                        self.vendor_name()
                    )],
                    errors: Vec::new(),
                })
            }

            fn validate_output(&self, _extraction: &ExtractionResult) -> CoreResult<ValidationResult> {
                Ok(ValidationResult {
                    valid: true,
                    issues: Vec::new(),
                })
            }
        }
    };
}

stub_parser!(
    DahuaParser,
    "Dahua",
    "dahua",
    90,
    "Dahua DVR/NVR parser (MVP stub). Detection signals: dh, dahua.",
    ["dh", "dahua"]
);

stub_parser!(
    HikvisionParser,
    "Hikvision",
    "hikvision",
    90,
    "Hikvision DVR/NVR parser (MVP stub). Detection signals: hik, hikvision.",
    ["hik", "hikvision"]
);

stub_parser!(
    UniviewParser,
    "Uniview",
    "uniview",
    60,
    "Uniview DVR/NVR parser (MVP stub). Detection signals: unv, uniview.",
    ["unv", "uniview"]
);

stub_parser!(
    CpPlusParser,
    "CP Plus",
    "cpplus",
    50,
    "CP Plus DVR/NVR parser (MVP stub). Detection signals: cpplus, cp_plus, cplus.",
    ["cpplus", "cp_plus", "cplus"]
);

stub_parser!(
    HoneywellParser,
    "Honeywell",
    "honeywell",
    30,
    "Honeywell DVR/NVR parser (plugin stub). Detection signals: honeywell, hwl.",
    ["honeywell", "hwl"]
);

stub_parser!(
    TpLinkParser,
    "TP-Link",
    "tplink",
    20,
    "TP-Link NVR parser (plugin stub). Detection signals: tplink, tp-link.",
    ["tplink", "tp-link"]
);

stub_parser!(
    GodrejParser,
    "Godrej",
    "godrej",
    20,
    "Godrej DVR parser (plugin stub). Detection signals: godrej.",
    ["godrej"]
);

stub_parser!(
    MatrixParser,
    "Matrix",
    "matrix",
    20,
    "Matrix DVR parser (plugin stub). Detection signals: matrix, mtx.",
    ["matrix", "mtx"]
);