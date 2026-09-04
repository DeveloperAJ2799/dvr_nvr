use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::Utc;
use parking_lot::Mutex;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::core::case_manager::init_schema;
use crate::core::error::{CoreError, CoreResult};
use crate::core::hasher::{hash_file_streaming, HashResult};
use crate::core::time::now_utc_string;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceRecord {
    pub evidence_id: String,
    pub case_id: String,
    pub source_path: String,
    pub evidence_type: String,
    pub size_bytes: u64,
    pub md5: String,
    pub sha256: String,
    pub ingested_at_utc: String,
    pub examiner: String,
    pub acquisition_method: String,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IngestEvidenceInput {
    pub source_path: PathBuf,
    pub evidence_label: String,
    pub evidence_type: String,
    pub examiner: String,
    pub acquisition_method: String,
    pub notes: String,
}

/// Detailed result of an evidence hash verification, persisted to the
/// `hashes` and `evidence` tables and written to the audit log.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VerificationOutcome {
    pub evidence_id: String,
    pub case_id: String,
    pub verified: bool,
    pub source_exists: bool,
    pub md5_match: bool,
    pub sha256_match: bool,
    pub expected_md5: String,
    pub actual_md5: String,
    pub expected_sha256: String,
    pub actual_sha256: String,
    pub size_bytes: u64,
    pub verified_at_utc: String,
    pub message: String,
}

pub struct EvidenceManager {
    pub active_connection: Arc<Mutex<Connection>>,
    pub case_dir: PathBuf,
}

impl EvidenceManager {
    pub fn new(active_connection: Arc<Mutex<Connection>>, case_dir: PathBuf) -> Self {
        Self {
            active_connection,
            case_dir,
        }
    }

    pub fn list_evidence(&self) -> CoreResult<Vec<EvidenceRecord>> {
        let conn = self.active_connection.lock();
        let mut stmt = conn.prepare(
            "SELECT evidence_id, case_id, source_path, evidence_type, size_bytes, md5, sha256, ingested_at_utc, examiner, acquisition_method, status FROM evidence ORDER BY ingested_at_utc DESC",
        )?;
        let rows = stmt
            .query_map([], |row| {
                Ok(EvidenceRecord {
                    evidence_id: row.get(0)?,
                    case_id: row.get(1)?,
                    source_path: row.get(2)?,
                    evidence_type: row.get(3)?,
                    size_bytes: row.get::<_, i64>(4)? as u64,
                    md5: row.get(5)?,
                    sha256: row.get(6)?,
                    ingested_at_utc: row.get(7)?,
                    examiner: row.get(8)?,
                    acquisition_method: row.get(9)?,
                    status: row.get(10)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    pub fn ingest_evidence(&self, input: IngestEvidenceInput) -> CoreResult<EvidenceRecord> {
        let source_path = input.source_path.clone();
        if !source_path.exists() {
            return Err(CoreError::InvalidInput(format!(
                "Source path does not exist: {:?}",
                source_path
            )));
        }

        let metadata = std::fs::metadata(&source_path)?;
        let evidence_type = input.evidence_type.clone();
        let evidence_type_final = if !evidence_type.is_empty() {
            evidence_type
        } else if metadata.is_dir() {
            "exported_folder".to_string()
        } else {
            "disk_image".to_string()
        };

        let case_id = self
            .case_dir
            .file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();

        let evidence_id = format!("EVID-{}", &Uuid::new_v4().to_string()[..8].to_uppercase());

        let conn_arc = self.active_connection.clone();
        let init_conn = Connection::open(self.case_dir.join("case.db"))?;
        init_schema(&init_conn)?;

        let now = Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string();

        let hashes = if metadata.is_dir() {
            HashResult {
                md5: String::new(),
                sha256: String::new(),
                size_bytes: 0,
                computed_at_utc: Utc::now(),
            }
        } else {
            hash_file_streaming_sync(&source_path)?
        };

        let conn = conn_arc.lock();
        conn.execute(
            "INSERT INTO evidence (evidence_id, case_id, source_path, evidence_type, size_bytes, md5, sha256, ingested_at_utc, examiner, acquisition_method, status) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, 'ingested')",
            params![
                evidence_id,
                case_id,
                source_path.to_string_lossy().to_string(),
                evidence_type_final,
                hashes.size_bytes as i64,
                hashes.md5,
                hashes.sha256,
                now,
                input.examiner,
                input.acquisition_method,
            ],
        )?;

        let hash_id = format!("HASH-{}", &Uuid::new_v4().to_string()[..8].to_uppercase());
        conn.execute(
            "INSERT INTO hashes (hash_id, case_id, artifact_type, artifact_path, md5, sha256, calculated_at_utc, verified_at_utc, verification_status) VALUES (?1, ?2, 'evidence_source', ?3, ?4, ?5, ?6, NULL, 'pending')",
            params![
                hash_id,
                case_id,
                source_path.to_string_lossy().to_string(),
                hashes.md5,
                hashes.sha256,
                now,
            ],
        )?;

        let manifest = serde_json::json!({
            "evidence_id": evidence_id,
            "case_id": case_id,
            "source_path": source_path.to_string_lossy().to_string(),
            "evidence_type": evidence_type_final,
            "size_bytes": hashes.size_bytes,
            "md5": hashes.md5,
            "sha256": hashes.sha256,
            "ingested_at_utc": now,
            "examiner": input.examiner,
            "acquisition_method": input.acquisition_method,
            "notes": input.notes,
            "status": "ingested",
            "evidence_label": input.evidence_label,
        });

        let manifest_dir = self.case_dir.join("evidence");
        std::fs::create_dir_all(&manifest_dir)?;
        std::fs::write(
            manifest_dir.join(format!("{}.json", evidence_id)),
            serde_json::to_string_pretty(&manifest)?,
        )?;

        Ok(EvidenceRecord {
            evidence_id,
            case_id,
            source_path: source_path.to_string_lossy().to_string(),
            evidence_type: evidence_type_final,
            size_bytes: hashes.size_bytes,
            md5: hashes.md5,
            sha256: hashes.sha256,
            ingested_at_utc: now,
            examiner: input.examiner,
            acquisition_method: input.acquisition_method,
            status: "ingested".to_string(),
        })
    }

    /// Re-hashes the evidence source and verifies **both** SHA-256 (primary)
    /// and MD5 against the values recorded at ingest. The outcome is persisted
    /// to the `evidence.status` and `hashes.verified_at_utc` /
    /// `hashes.verification_status` columns so verifications are provable
    /// after the fact, not just shown transiently in the UI.
    pub fn verify_evidence(&self, evidence_id: &str) -> CoreResult<VerificationOutcome> {
        let verified_at = now_utc_string();

        // Fetch the baseline under a short lock; hashing happens unlocked.
        let (case_id, source_path, expected_md5, expected_sha256, expected_size) = {
            let conn = self.active_connection.lock();
            let mut stmt = conn.prepare(
                "SELECT case_id, source_path, md5, sha256, size_bytes FROM evidence WHERE evidence_id = ?1",
            )?;
            let mut rows = stmt.query(params![evidence_id])?;
            let row = rows
                .next()?
                .ok_or_else(|| CoreError::EvidenceNotFound(evidence_id.to_string()))?;
            (
                row.get::<_, String>(0)?,
                row.get::<_, String>(1)?,
                row.get::<_, String>(2)?,
                row.get::<_, String>(3)?,
                row.get::<_, i64>(4)? as u64,
            )
        };

        let path = PathBuf::from(&source_path);
        if !path.exists() {
            let outcome = VerificationOutcome {
                evidence_id: evidence_id.to_string(),
                case_id,
                verified: false,
                source_exists: false,
                md5_match: false,
                sha256_match: false,
                expected_md5,
                actual_md5: String::new(),
                expected_sha256,
                actual_sha256: String::new(),
                size_bytes: expected_size,
                verified_at_utc: verified_at.clone(),
                message: "Source file no longer exists at the recorded path.".to_string(),
            };
            self.persist_verification(
                evidence_id,
                &source_path,
                &outcome.expected_md5,
                &outcome.expected_sha256,
                "source_missing",
                "source_missing",
                &verified_at,
            )?;
            return Ok(outcome);
        }

        let actual = hash_file_streaming_sync(&path)?;

        let md5_recorded = !expected_md5.is_empty();
        let sha256_recorded = !expected_sha256.is_empty();
        let md5_match = md5_recorded && actual.md5.eq_ignore_ascii_case(&expected_md5);
        let sha256_match = sha256_recorded && actual.sha256.eq_ignore_ascii_case(&expected_sha256);

        let (verified, message) = if !md5_recorded && !sha256_recorded {
            (
                true,
                "No baseline hash was recorded at ingest (folder evidence); nothing to compare."
                    .to_string(),
            )
        } else if md5_match && sha256_match {
            (
                true,
                "SHA-256 and MD5 match the values recorded at ingest.".to_string(),
            )
        } else {
            (
                false,
                "Hash mismatch: the evidence may have been altered since ingest.".to_string(),
            )
        };

        let outcome = VerificationOutcome {
            evidence_id: evidence_id.to_string(),
            case_id,
            verified,
            source_exists: true,
            md5_match,
            sha256_match,
            expected_md5,
            actual_md5: actual.md5,
            expected_sha256,
            actual_sha256: actual.sha256,
            size_bytes: actual.size_bytes,
            verified_at_utc: verified_at.clone(),
            message,
        };

        let status = if verified { "verified" } else { "hash_mismatch" };
        self.persist_verification(
            evidence_id,
            &source_path,
            &outcome.expected_md5,
            &outcome.expected_sha256,
            status,
            if verified { "verified" } else { "mismatch" },
            &verified_at,
        )?;

        Ok(outcome)
    }

    /// Persists a verification result: updates the evidence `status` and the
    /// matching `hashes` row (`verified_at_utc`, `verification_status`).
    /// If no `hashes` row exists for the source (e.g. legacy records), one is
    /// created so the verification is still recorded.
    #[allow(clippy::too_many_arguments)]
    fn persist_verification(
        &self,
        evidence_id: &str,
        source_path: &str,
        expected_md5: &str,
        expected_sha256: &str,
        evidence_status: &str,
        hash_status: &str,
        verified_at: &str,
    ) -> CoreResult<()> {
        let conn = self.active_connection.lock();
        conn.execute(
            "UPDATE evidence SET status = ?2 WHERE evidence_id = ?1",
            params![evidence_id, evidence_status],
        )?;

        let updated = conn.execute(
            "UPDATE hashes SET verified_at_utc = ?1, verification_status = ?2 WHERE artifact_type = 'evidence_source' AND artifact_path = ?3",
            params![verified_at, hash_status, source_path],
        )?;
        if updated == 0 {
            let case_id: String = conn.query_row(
                "SELECT case_id FROM evidence WHERE evidence_id = ?1",
                params![evidence_id],
                |r| r.get(0),
            )?;
            let hash_id = format!("HASH-{}", &Uuid::new_v4().to_string()[..8].to_uppercase());
            conn.execute(
                "INSERT INTO hashes (hash_id, case_id, artifact_type, artifact_path, md5, sha256, calculated_at_utc, verified_at_utc, verification_status) VALUES (?1, ?2, 'evidence_source', ?3, ?4, ?5, ?6, ?6, ?7)",
                params![
                    hash_id,
                    case_id,
                    source_path,
                    expected_md5,
                    expected_sha256,
                    verified_at,
                    hash_status,
                ],
            )?;
        }
        Ok(())
    }
}

pub fn hash_file_streaming_sync<P: AsRef<Path>>(path: P) -> CoreResult<HashResult> {
    let runtime = tokio::runtime::Handle::try_current();
    match runtime {
        Ok(handle) => tokio::task::block_in_place(|| {
            handle.block_on(async move { hash_file_streaming(path).await })
        }),
        Err(_) => {
            let rt = tokio::runtime::Runtime::new()?;
            rt.block_on(hash_file_streaming(path))
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::case_manager::init_schema;

    fn setup_case(tag: &str) -> (PathBuf, EvidenceManager) {
        let dir = std::env::temp_dir().join(format!(
            "dvr_evidence_test_{}_{}",
            tag,
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let conn = Connection::open(dir.join("case.db")).unwrap();
        init_schema(&conn).unwrap();
        let mgr = EvidenceManager::new(
            Arc::new(Mutex::new(conn)),
            dir.clone(),
        );
        (dir, mgr)
    }

    #[test]
    fn ingest_then_verify_roundtrip_and_tamper_detection() {
        let (case_dir, mgr) = setup_case("roundtrip");

        // Source evidence file.
        let src_dir = std::env::temp_dir().join(format!(
            "dvr_evidence_src_{}",
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&src_dir).unwrap();
        let src = src_dir.join("image.dd");
        std::fs::write(&src, b"Forensic evidence content v1").unwrap();

        let rec = mgr
            .ingest_evidence(IngestEvidenceInput {
                source_path: src.clone(),
                evidence_label: "test image".to_string(),
                evidence_type: "disk_image".to_string(),
                examiner: "tester".to_string(),
                acquisition_method: "write-blocked image".to_string(),
                notes: String::new(),
            })
            .unwrap();

        // First verification: must pass on both algorithms.
        let ok = mgr.verify_evidence(&rec.evidence_id).unwrap();
        assert!(ok.verified, "untouched evidence must verify: {}", ok.message);
        assert!(ok.sha256_match);
        assert!(ok.md5_match);

        // The verification must be persisted.
        let conn = mgr.active_connection.lock();
        let (ev_status, h_status, verified_at): (String, String, String) = conn
            .query_row(
                "SELECT e.status, h.verification_status, h.verified_at_utc FROM evidence e JOIN hashes h ON h.artifact_path = e.source_path WHERE e.evidence_id = ?1",
                params![rec.evidence_id],
                |r| Ok((r.get(0)?, r.get(1)?, r.get(2)?)),
            )
            .unwrap();
        drop(conn);
        assert_eq!(ev_status, "verified");
        assert_eq!(h_status, "verified");
        assert!(!verified_at.is_empty());

        // Tamper with the source, then verify again: must fail.
        std::fs::write(&src, b"Forensic evidence content v2-TAMPERED").unwrap();
        let bad = mgr.verify_evidence(&rec.evidence_id).unwrap();
        assert!(!bad.verified, "tampered evidence must fail verification");
        assert!(!bad.sha256_match, "SHA-256 must be checked, not just MD5");

        let conn = mgr.active_connection.lock();
        let (ev_status, h_status): (String, String) = conn
            .query_row(
                "SELECT e.status, h.verification_status FROM evidence e JOIN hashes h ON h.artifact_path = e.source_path WHERE e.evidence_id = ?1",
                params![rec.evidence_id],
                |r| Ok((r.get(0)?, r.get(1)?)),
            )
            .unwrap();
        drop(conn);
        assert_eq!(ev_status, "hash_mismatch");
        assert_eq!(h_status, "mismatch");

        drop(mgr); // close the SQLite handle before cleanup (Windows)
        std::fs::remove_dir_all(&case_dir).unwrap();
        std::fs::remove_dir_all(&src_dir).unwrap();
    }

    #[test]
    fn missing_source_is_reported_and_persisted() {
        let (case_dir, mgr) = setup_case("missing");
        let src_dir = std::env::temp_dir().join(format!(
            "dvr_evidence_gone_{}",
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&src_dir).unwrap();
        let src = src_dir.join("image.dd");
        std::fs::write(&src, b"temporary evidence").unwrap();

        let rec = mgr
            .ingest_evidence(IngestEvidenceInput {
                source_path: src.clone(),
                evidence_label: "gone".to_string(),
                evidence_type: "disk_image".to_string(),
                examiner: "tester".to_string(),
                acquisition_method: "write-blocked image".to_string(),
                notes: String::new(),
            })
            .unwrap();

        std::fs::remove_dir_all(&src_dir).unwrap();
        let out = mgr.verify_evidence(&rec.evidence_id).unwrap();
        assert!(!out.verified);
        assert!(!out.source_exists);

        let conn = mgr.active_connection.lock();
        let ev_status: String = conn
            .query_row(
                "SELECT status FROM evidence WHERE evidence_id = ?1",
                params![rec.evidence_id],
                |r| r.get(0),
            )
            .unwrap();
        drop(conn);
        assert_eq!(ev_status, "source_missing");

        drop(mgr);
        std::fs::remove_dir_all(&case_dir).unwrap();
    }
}