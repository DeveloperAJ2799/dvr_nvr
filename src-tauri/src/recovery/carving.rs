use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct CarvingResult {
    pub signature: String,
    pub offsets: Vec<u64>,
    pub candidate_count: usize,
}

pub fn placeholder() -> CarvingResult {
    CarvingResult {
        signature: "h264_aud".to_string(),
        offsets: Vec::new(),
        candidate_count: 0,
    }
}