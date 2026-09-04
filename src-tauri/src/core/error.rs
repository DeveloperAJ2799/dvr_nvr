use thiserror::Error;

#[derive(Debug, Error)]
pub enum CoreError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    #[error("Database error: {0}")]
    Database(#[from] rusqlite::Error),

    #[error("JSON error: {0}")]
    Json(#[from] serde_json::Error),

    #[error("Case not found: {0}")]
    CaseNotFound(String),

    #[error("Evidence not found: {0}")]
    EvidenceNotFound(String),

    #[error("Parser error: {0}")]
    Parser(String),

    #[error("Invalid input: {0}")]
    InvalidInput(String),

    #[error("Hashing error: {0}")]
    Hash(String),

    #[error("FFmpeg error: {0}")]
    Ffmpeg(String),

    #[error("{0}")]
    Other(String),
}

pub type CoreResult<T> = Result<T, CoreError>;

impl From<anyhow::Error> for CoreError {
    fn from(err: anyhow::Error) -> Self {
        CoreError::Other(err.to_string())
    }
}

impl From<String> for CoreError {
    fn from(s: String) -> Self {
        CoreError::Other(s)
    }
}