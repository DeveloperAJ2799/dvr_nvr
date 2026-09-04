use std::path::PathBuf;
use std::sync::Arc;

use parking_lot::Mutex;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::fs::OpenOptions;
use std::io::Write;
use uuid::Uuid;

use crate::core::error::{CoreError, CoreResult};
use crate::core::time::now_utc_string;

/// Hash of the virtual entry preceding the first real entry.
const GENESIS_HASH: &str = "0000000000000000000000000000000000000000000000000000000000000000";

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditEvent {
    pub event_id: String,
    pub case_id: String,
    pub timestamp_utc: String,
    pub examiner: String,
    pub module: String,
    pub action: String,
    pub input: String,
    pub output: String,
    pub status: String,
    pub details: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewAuditEvent {
    pub case_id: String,
    pub examiner: String,
    pub module: String,
    pub action: String,
    pub input: String,
    pub output: String,
    pub status: String,
    pub details: String,
}

/// One custody entry in the append-only hash-chained JSONL file.
/// `entry_hash = SHA-256(seq | prev_hash | canonical_event_json)` so any
/// retro-active modification of an entry (or deletion/reordering) is detectable.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainedCustodyEntry {
    pub seq: u64,
    pub prev_hash: String,
    pub entry_hash: String,
    pub event: AuditEvent,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChainVerification {
    pub total_entries: u64,
    pub valid: bool,
    pub broken_at_seq: Option<u64>,
    pub legacy_format: bool,
    pub message: String,
}

fn custody_entry_hash(
    seq: u64,
    prev_hash: &str,
    event_json: &serde_json::Value,
) -> CoreResult<String> {
    let canonical = serde_json::to_string(event_json)?;
    let mut hasher = Sha256::new();
    hasher.update(seq.to_string().as_bytes());
    hasher.update(b"|");
    hasher.update(prev_hash.as_bytes());
    hasher.update(b"|");
    hasher.update(canonical.as_bytes());
    Ok(format!("{:x}", hasher.finalize()))
}

pub struct AuditLogger {
    active_connection: Arc<Mutex<Connection>>,
    chain_of_custody_path: PathBuf,
}

impl AuditLogger {
    pub fn new(active_connection: Arc<Mutex<Connection>>, case_dir: PathBuf) -> Self {
        Self {
            active_connection,
            chain_of_custody_path: case_dir.join("chain_of_custody.json"),
        }
    }

    pub fn record(&self, event: NewAuditEvent) -> CoreResult<AuditEvent> {
        let event_id = format!("EVT-{}", &Uuid::new_v4().to_string()[..8].to_uppercase());
        let ts = now_utc_string();

        let conn = self.active_connection.lock();
        conn.execute(
            "INSERT INTO audit_events (event_id, case_id, timestamp_utc, examiner, module, action, input, output, status, details) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10)",
            params![
                event_id,
                event.case_id,
                ts,
                event.examiner,
                event.module,
                event.action,
                event.input,
                event.output,
                event.status,
                event.details,
            ],
        )?;
        drop(conn);

        let full = AuditEvent {
            event_id: event_id.clone(),
            case_id: event.case_id,
            timestamp_utc: ts,
            examiner: event.examiner,
            module: event.module,
            action: event.action,
            input: event.input,
            output: event.output,
            status: event.status,
            details: event.details,
        };

        self.append_to_chain_of_custody(&full)?;
        Ok(full)
    }

    pub fn list_events(&self, case_id: &str) -> CoreResult<Vec<AuditEvent>> {
        let conn = self.active_connection.lock();
        let mut stmt = conn.prepare(
            "SELECT event_id, case_id, timestamp_utc, examiner, module, action, input, output, status, details FROM audit_events WHERE case_id = ?1 ORDER BY timestamp_utc DESC",
        )?;
        let rows = stmt
            .query_map(params![case_id], |row| {
                Ok(AuditEvent {
                    event_id: row.get(0)?,
                    case_id: row.get(1)?,
                    timestamp_utc: row.get(2)?,
                    examiner: row.get(3)?,
                    module: row.get(4)?,
                    action: row.get(5)?,
                    input: row.get(6)?,
                    output: row.get(7)?,
                    status: row.get(8)?,
                    details: row.get(9)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    fn append_to_chain_of_custody(&self, event: &AuditEvent) -> CoreResult<()> {
        let (seq, prev_hash) = self.load_chain_tip()?;

        let event_json = serde_json::to_value(event)?;
        let entry_hash = custody_entry_hash(seq + 1, &prev_hash, &event_json)?;
        let entry = ChainedCustodyEntry {
            seq: seq + 1,
            prev_hash,
            entry_hash,
            event: event.clone(),
        };

        // Append-only: existing entries are never rewritten.
        let mut file = OpenOptions::new()
            .create(true)
            .append(true)
            .open(&self.chain_of_custody_path)?;
        writeln!(file, "{}", serde_json::to_string(&entry)?)?;
        Ok(())
    }

    /// Returns `(last_seq, last_entry_hash)`, migrating a legacy plain-array
    /// custody file to the hashed JSONL format in place if needed.
    ///
    /// A corrupt file is a hard error — it must never be silently replaced.
    fn load_chain_tip(&self) -> CoreResult<(u64, String)> {
        if !self.chain_of_custody_path.exists() {
            return Ok((0, GENESIS_HASH.to_string()));
        }
        let text = std::fs::read_to_string(&self.chain_of_custody_path)?;
        if text.trim().is_empty() {
            return Ok((0, GENESIS_HASH.to_string()));
        }

        if text.trim_start().starts_with('[') {
            // Legacy format written by earlier versions: a plain JSON array.
            // Migrate every entry into the hashed chain, preserving order.
            let legacy: Vec<AuditEvent> = serde_json::from_str(&text).map_err(|e| {
                CoreError::Other(format!(
                    "chain_of_custody.json is corrupt and cannot be migrated: {}",
                    e
                ))
            })?;
            let mut out = String::new();
            let mut seq: u64 = 0;
            let mut prev = GENESIS_HASH.to_string();
            for event in &legacy {
                seq += 1;
                let event_json = serde_json::to_value(event)?;
                let entry_hash = custody_entry_hash(seq, &prev, &event_json)?;
                let entry = ChainedCustodyEntry {
                    seq,
                    prev_hash: prev.clone(),
                    entry_hash: entry_hash.clone(),
                    event: event.clone(),
                };
                out.push_str(&serde_json::to_string(&entry)?);
                out.push('\n');
                prev = entry_hash;
            }
            std::fs::write(&self.chain_of_custody_path, out)?;
            return Ok((seq, prev));
        }

        let mut seq: u64 = 0;
        let mut prev = GENESIS_HASH.to_string();
        for (idx, line) in text.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let entry: ChainedCustodyEntry = serde_json::from_str(line).map_err(|e| {
                CoreError::Other(format!(
                    "chain_of_custody.json entry {} is corrupt: {}",
                    idx + 1,
                    e
                ))
            })?;
            seq = entry.seq;
            prev = entry.entry_hash;
        }
        Ok((seq, prev))
    }

    /// Recomputes the whole hash chain and reports whether the custody log is
    /// intact. Read-only: it never mutates the file.
    pub fn verify_chain(&self) -> CoreResult<ChainVerification> {
        if !self.chain_of_custody_path.exists() {
            return Ok(ChainVerification {
                total_entries: 0,
                valid: true,
                broken_at_seq: None,
                legacy_format: false,
                message: "No chain-of-custody file recorded yet.".to_string(),
            });
        }
        let text = std::fs::read_to_string(&self.chain_of_custody_path)?;
        if text.trim().is_empty() {
            return Ok(ChainVerification {
                total_entries: 0,
                valid: true,
                broken_at_seq: None,
                legacy_format: false,
                message: "Chain-of-custody file is empty.".to_string(),
            });
        }
        if text.trim_start().starts_with('[') {
            return Ok(ChainVerification {
                total_entries: 0,
                valid: true,
                broken_at_seq: None,
                legacy_format: true,
                message: "Legacy format (no per-entry hashes). It will be migrated automatically the next time an event is recorded.".to_string(),
            });
        }

        let mut expected_seq: u64 = 0;
        let mut prev = GENESIS_HASH.to_string();
        for (idx, line) in text.lines().enumerate() {
            if line.trim().is_empty() {
                continue;
            }
            let entry: ChainedCustodyEntry = serde_json::from_str(line).map_err(|e| {
                CoreError::Other(format!(
                    "chain_of_custody.json entry {} is corrupt: {}",
                    idx + 1,
                    e
                ))
            })?;
            expected_seq += 1;
            if entry.seq != expected_seq || entry.prev_hash != prev {
                return Ok(ChainVerification {
                    total_entries: expected_seq - 1,
                    valid: false,
                    broken_at_seq: Some(entry.seq),
                    legacy_format: false,
                    message: format!(
                        "Chain broken at entry {} (sequence or link mismatch — entries may have been deleted or reordered).",
                        entry.seq
                    ),
                });
            }
            let event_json = serde_json::to_value(&entry.event)?;
            let recomputed = custody_entry_hash(entry.seq, &entry.prev_hash, &event_json)?;
            if recomputed != entry.entry_hash {
                return Ok(ChainVerification {
                    total_entries: entry.seq,
                    valid: false,
                    broken_at_seq: Some(entry.seq),
                    legacy_format: false,
                    message: format!(
                        "Entry {} hash mismatch — the record was modified after being written.",
                        entry.seq
                    ),
                });
            }
            prev = entry.entry_hash;
        }

        Ok(ChainVerification {
            total_entries: expected_seq,
            valid: true,
            broken_at_seq: None,
            legacy_format: false,
            message: format!("All {} entries verified; hash chain intact.", expected_seq),
        })
    }
}

pub fn ensure_case_active(case_id: &str) -> CoreResult<()> {
    if case_id.trim().is_empty() {
        return Err(CoreError::InvalidInput(
            "No active case".to_string(),
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::core::case_manager::init_schema;

    fn temp_case_dir(tag: &str) -> PathBuf {
        let dir = std::env::temp_dir().join(format!(
            "dvr_audit_test_{}_{}",
            tag,
            uuid::Uuid::new_v4()
        ));
        std::fs::create_dir_all(&dir).unwrap();
        let conn = Connection::open(dir.join("case.db")).unwrap();
        init_schema(&conn).unwrap();
        dir
    }

    fn sample_event(case_id: &str, action: &str) -> NewAuditEvent {
        NewAuditEvent {
            case_id: case_id.to_string(),
            examiner: "tester".to_string(),
            module: "test".to_string(),
            action: action.to_string(),
            input: "in".to_string(),
            output: "out".to_string(),
            status: "success".to_string(),
            details: String::new(),
        }
    }

    fn new_logger(dir: &std::path::Path) -> AuditLogger {
        let conn = Arc::new(Mutex::new(Connection::open(dir.join("case.db")).unwrap()));
        AuditLogger::new(conn, dir.to_path_buf())
    }

    #[test]
    fn chain_roundtrip_and_verify() {
        let dir = temp_case_dir("roundtrip");
        let logger = new_logger(&dir);
        for i in 0..3 {
            logger
                .record(sample_event("CASE-X", &format!("action-{}", i)))
                .unwrap();
        }
        let v = logger.verify_chain().unwrap();
        assert!(v.valid, "chain should verify: {}", v.message);
        assert_eq!(v.total_entries, 3);
        assert!(!v.legacy_format);
        assert!(v.broken_at_seq.is_none());
        drop(logger); // close the SQLite handle before cleanup (Windows)
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn tampered_entry_is_detected() {
        let dir = temp_case_dir("tamper");
        let logger = new_logger(&dir);
        for i in 0..2 {
            logger
                .record(sample_event("CASE-X", &format!("action-{}", i)))
                .unwrap();
        }

        // Modify the first entry in place, as a tamperer would.
        let path = dir.join("chain_of_custody.json");
        let text = std::fs::read_to_string(&path).unwrap();
        let tampered = text.replacen("action-0", "action-TAMPERED", 1);
        assert_ne!(text, tampered);
        std::fs::write(&path, tampered).unwrap();

        let v = logger.verify_chain().unwrap();
        assert!(!v.valid, "tampering must be detected");
        assert_eq!(v.broken_at_seq, Some(1));
        drop(logger);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn deleted_entry_is_detected() {
        let dir = temp_case_dir("delete");
        let logger = new_logger(&dir);
        for i in 0..3 {
            logger
                .record(sample_event("CASE-X", &format!("action-{}", i)))
                .unwrap();
        }
        let path = dir.join("chain_of_custody.json");
        let text = std::fs::read_to_string(&path).unwrap();
        // Drop the second line: sequence numbers then break the chain.
        let tampered: String = text
            .lines()
            .enumerate()
            .filter(|(i, _)| *i != 1)
            .map(|(_, l)| format!("{}\n", l))
            .collect();
        std::fs::write(&path, tampered).unwrap();

        let v = logger.verify_chain().unwrap();
        assert!(!v.valid, "deletion must be detected");
        // After deleting entry 2, the next surviving entry (seq 3) is where
        // the sequence check fails.
        assert_eq!(v.broken_at_seq, Some(3));
        drop(logger);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn legacy_array_is_migrated_and_extended() {
        let dir = temp_case_dir("legacy");
        // Seed a legacy plain-array file with two entries.
        let legacy_events = vec![
            AuditEvent {
                event_id: "EVT-00000001".to_string(),
                case_id: "CASE-X".to_string(),
                timestamp_utc: "2026-01-01T00:00:00Z".to_string(),
                examiner: "tester".to_string(),
                module: "test".to_string(),
                action: "legacy-a".to_string(),
                input: String::new(),
                output: String::new(),
                status: "success".to_string(),
                details: String::new(),
            },
            AuditEvent {
                event_id: "EVT-00000002".to_string(),
                case_id: "CASE-X".to_string(),
                timestamp_utc: "2026-01-01T00:00:01Z".to_string(),
                examiner: "tester".to_string(),
                module: "test".to_string(),
                action: "legacy-b".to_string(),
                input: String::new(),
                output: String::new(),
                status: "success".to_string(),
                details: String::new(),
            },
        ];
        std::fs::write(
            dir.join("chain_of_custody.json"),
            serde_json::to_string_pretty(&legacy_events).unwrap(),
        )
        .unwrap();

        let logger = new_logger(&dir);
        // Recording a new event must migrate the legacy entries, not wipe them.
        logger
            .record(sample_event("CASE-X", "new-event"))
            .unwrap();

        let v = logger.verify_chain().unwrap();
        assert!(v.valid, "migrated chain should verify: {}", v.message);
        assert_eq!(v.total_entries, 3, "legacy entries must be preserved");
        assert!(!v.legacy_format);
        drop(logger);
        std::fs::remove_dir_all(&dir).unwrap();
    }

    #[test]
    fn corrupt_file_is_an_error_not_silently_wiped() {
        let dir = temp_case_dir("corrupt");
        std::fs::write(
            dir.join("chain_of_custody.json"),
            "{{{ not json at all",
        )
        .unwrap();
        let logger = new_logger(&dir);
        let result = logger.record(sample_event("CASE-X", "boom"));
        assert!(result.is_err(), "corrupt custody file must fail loudly");
        // The corrupt file must be left untouched.
        assert_eq!(
            std::fs::read_to_string(dir.join("chain_of_custody.json")).unwrap(),
            "{{{ not json at all"
        );
        drop(logger);
        std::fs::remove_dir_all(&dir).unwrap();
    }
}