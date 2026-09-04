use std::path::Path;

use chrono::{DateTime, Utc};
use md5::Md5;
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use tokio::io::AsyncReadExt;

use crate::core::error::{CoreError, CoreResult};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HashResult {
    pub md5: String,
    pub sha256: String,
    pub size_bytes: u64,
    pub computed_at_utc: DateTime<Utc>,
}

pub const CHUNK_SIZE: usize = 1024 * 1024;

pub async fn hash_file_streaming<P: AsRef<Path>>(
    path: P,
) -> CoreResult<HashResult> {
    let path_ref = path.as_ref();
    let metadata = tokio::fs::metadata(path_ref).await?;
    let size = metadata.len();

    let mut md5 = Md5::new();
    let mut sha = Sha256::new();
    let mut file = tokio::fs::File::open(path_ref).await?;
    let mut buffer = vec![0u8; CHUNK_SIZE];

    loop {
        let n = file.read(&mut buffer).await?;
        if n == 0 {
            break;
        }
        md5.update(&buffer[..n]);
        sha.update(&buffer[..n]);
    }

    Ok(HashResult {
        md5: format!("{:x}", md5.finalize()),
        sha256: format!("{:x}", sha.finalize()),
        size_bytes: size,
        computed_at_utc: Utc::now(),
    })
}

pub fn verify_hash(expected: &str, actual: &str) -> bool {
    expected.eq_ignore_ascii_case(actual)
}

pub fn validate_md5(s: &str) -> Result<(), CoreError> {
    if s.len() != 32 || !s.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(CoreError::Hash(format!("Invalid MD5 hash: {}", s)));
    }
    Ok(())
}

pub fn validate_sha256(s: &str) -> Result<(), CoreError> {
    if s.len() != 64 || !s.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(CoreError::Hash(format!("Invalid SHA-256 hash: {}", s)));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use sha2::Digest;

    #[test]
    fn streaming_hash_matches_single_shot_hash() {
        let dir = std::env::temp_dir().join(format!(
            "dvr_hasher_test_{}",
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let path = dir.join("blob.bin");
        // >1 MiB so multiple 1 MiB chunks are exercised.
        let data: Vec<u8> = (0..3 * CHUNK_SIZE + 777)
            .map(|i| (i % 251) as u8)
            .collect();
        std::fs::write(&path, &data).unwrap();

        let result = tokio::runtime::Runtime::new()
            .unwrap()
            .block_on(hash_file_streaming(&path))
            .unwrap();

        let mut md5 = Md5::new();
        md5.update(&data);
        let mut sha = Sha256::new();
        sha.update(&data);
        assert_eq!(result.md5, format!("{:x}", md5.finalize()));
        assert_eq!(result.sha256, format!("{:x}", sha.finalize()));
        assert_eq!(result.size_bytes, data.len() as u64);

        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn validators_accept_lowercase_and_uppercase() {
        let lower = "d41d8cd98f00b204e9800998ecf8427e";
        assert!(validate_md5(lower).is_ok());
        assert!(validate_md5(&lower.to_uppercase()).is_ok());
        assert!(validate_md5("tooshort").is_err());
        assert!(validate_md5("zz41d8cd98f00b204e9800998ecf8427e").is_err());

        let sha = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        assert!(validate_sha256(sha).is_ok());
        assert!(validate_sha256(&sha.to_uppercase()).is_ok());
        assert!(validate_sha256("deadbeef").is_err());
    }

    #[test]
    fn verify_hash_is_case_insensitive() {
        let h = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855";
        assert!(verify_hash(h, &h.to_uppercase()));
        assert!(!verify_hash(h, &"0".repeat(64)));
    }
}