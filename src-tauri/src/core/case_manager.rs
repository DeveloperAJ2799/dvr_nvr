use std::path::{Path, PathBuf};
use std::sync::Arc;

use chrono::{DateTime, Utc};
use parking_lot::Mutex;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

use crate::core::error::{CoreError, CoreResult};
use crate::core::settings::AppSettings;
use crate::core::time::{normalize_raw, NormalizedTimestamp};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CaseRecord {
    pub case_id: String,
    pub case_name: String,
    pub examiner: String,
    pub organization: String,
    pub timezone_assumption: String,
    pub notes: String,
    pub created_at_utc: String,
    pub updated_at_utc: String,
    pub case_dir: PathBuf,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NewCaseInput {
    pub case_id: Option<String>,
    pub case_name: String,
    pub examiner: String,
    pub organization: String,
    pub timezone_assumption: String,
    pub notes: String,
}

pub struct CaseManager {
    settings: Arc<Mutex<AppSettings>>,
    active_case: Mutex<Option<(PathBuf, Arc<Mutex<Connection>>)>>,
}

impl CaseManager {
    pub fn new(settings: Arc<Mutex<AppSettings>>) -> Self {
        Self {
            settings,
            active_case: Mutex::new(None),
        }
    }

    pub fn case_root_dir() -> &'static str {
        "cases"
    }

    pub fn subdirs() -> &'static [&'static str] {
        &[
            "evidence",
            "extracted",
            "recovered",
            "reports",
            "logs",
            "thumbnails",
            "metadata",
        ]
    }

    pub fn list_cases(&self) -> CoreResult<Vec<CaseRecord>> {
        let settings = self.settings.lock().clone();
        let root = settings.case_storage_dir.clone();
        let _ = std::fs::create_dir_all(&root);

        let mut cases = Vec::new();
        if !root.exists() {
            return Ok(cases);
        }
        for entry in std::fs::read_dir(&root)? {
            let entry = entry?;
            if !entry.file_type()?.is_dir() {
                continue;
            }
            let db_path = entry.path().join("case.db");
            if !db_path.exists() {
                continue;
            }
            let conn = Connection::open(&db_path)?;
            let record = read_case_row(&conn, &entry.file_name().to_string_lossy());
            if let Ok(record) = record {
                cases.push(record);
            }
        }
        cases.sort_by(|a, b| b.updated_at_utc.cmp(&a.updated_at_utc));
        Ok(cases)
    }

    pub fn create_case(&self, input: NewCaseInput) -> CoreResult<CaseRecord> {
        let settings = self.settings.lock().clone();
        let case_id = match input.case_id {
            Some(id) if !id.trim().is_empty() => id.trim().to_string(),
            _ => format!("CASE-{}", &Uuid::new_v4().to_string()[..8].to_uppercase()),
        };

        let case_dir = settings.case_storage_dir.join(&case_id);
        if case_dir.exists() {
            return Err(CoreError::InvalidInput(format!(
                "Case already exists: {}",
                case_id
            )));
        }

        std::fs::create_dir_all(&case_dir)?;
        for sub in Self::subdirs() {
            std::fs::create_dir_all(case_dir.join(sub))?;
        }

        let db_path = case_dir.join("case.db");
        let conn = Connection::open(&db_path)?;
        init_schema(&conn)?;

        let now = Utc::now();
        let now_str = now.format("%Y-%m-%dT%H:%M:%SZ").to_string();

        conn.execute(
            "INSERT INTO cases (case_id, case_name, examiner, organization, timezone_assumption, notes, created_at_utc, updated_at_utc, status) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'active')",
            params![
                case_id,
                input.case_name,
                input.examiner,
                input.organization,
                input.timezone_assumption,
                input.notes,
                now_str,
                now_str,
            ],
        )?;

        let case_json = serde_json::json!({
            "case_id": case_id,
            "case_name": input.case_name,
            "examiner": input.examiner,
            "organization": input.organization,
            "timezone_assumption": input.timezone_assumption,
            "notes": input.notes,
            "created_at_utc": now_str,
            "updated_at_utc": now_str,
            "status": "active",
        });
        std::fs::write(
            case_dir.join("case.json"),
            serde_json::to_string_pretty(&case_json)?,
        )?;

        let record = CaseRecord {
            case_id: case_id.clone(),
            case_name: input.case_name,
            examiner: input.examiner,
            organization: input.organization,
            timezone_assumption: input.timezone_assumption,
            notes: input.notes,
            created_at_utc: now_str.clone(),
            updated_at_utc: now_str,
            case_dir: case_dir.clone(),
            status: "active".to_string(),
        };
        Ok(record)
    }

    pub fn open_case(&self, case_id: &str) -> CoreResult<CaseRecord> {
        let settings = self.settings.lock().clone();
        let case_dir = settings.case_storage_dir.join(case_id);
        if !case_dir.exists() {
            return Err(CoreError::CaseNotFound(case_id.to_string()));
        }
        let db_path = case_dir.join("case.db");
        let conn = Connection::open(&db_path)?;
        init_schema(&conn)?;

        let record = read_case_row(&conn, case_id)?;
        let conn_arc = Arc::new(Mutex::new(conn));
        *self.active_case.lock() = Some((case_dir, conn_arc));
        Ok(record)
    }

    pub fn active_case_dir(&self) -> Option<PathBuf> {
        self.active_case.lock().as_ref().map(|(d, _)| d.clone())
    }

    pub fn active_case_id(&self) -> Option<String> {
        self.active_case
            .lock()
            .as_ref()
            .and_then(|(d, _)| d.file_name().map(|n| n.to_string_lossy().to_string()))
    }

    pub fn active_connection(&self) -> Option<Arc<Mutex<Connection>>> {
        self.active_case.lock().as_ref().map(|(_, c)| c.clone())
    }

    pub fn close_case(&self) {
        *self.active_case.lock() = None;
    }

    pub fn with_connection<F, T>(&self, f: F) -> CoreResult<T>
    where
        F: FnOnce(&Connection) -> CoreResult<T>,
    {
        let guard = self.active_case.lock();
        let (_, conn_arc) = guard
            .as_ref()
            .ok_or_else(|| CoreError::InvalidInput("No active case".to_string()))?;
        let conn = conn_arc.lock();
        f(&conn)
    }
}

pub fn init_schema(conn: &Connection) -> CoreResult<()> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS cases (
            case_id TEXT PRIMARY KEY,
            case_name TEXT,
            examiner TEXT,
            organization TEXT,
            timezone_assumption TEXT,
            notes TEXT,
            created_at_utc TEXT,
            updated_at_utc TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS evidence (
            evidence_id TEXT PRIMARY KEY,
            case_id TEXT,
            source_path TEXT,
            evidence_type TEXT,
            size_bytes INTEGER,
            md5 TEXT,
            sha256 TEXT,
            ingested_at_utc TEXT,
            examiner TEXT,
            acquisition_method TEXT,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS recordings (
            recording_id TEXT PRIMARY KEY,
            case_id TEXT,
            evidence_id TEXT,
            camera_id TEXT,
            camera_name TEXT,
            start_time_raw TEXT,
            start_time_utc TEXT,
            end_time_raw TEXT,
            end_time_utc TEXT,
            duration_seconds INTEGER,
            event_type TEXT,
            original_file_path TEXT,
            extracted_file_path TEXT,
            container_format TEXT,
            video_codec TEXT,
            audio_codec TEXT,
            parser_name TEXT,
            confidence REAL,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS recovered_items (
            recovered_id TEXT PRIMARY KEY,
            case_id TEXT,
            evidence_id TEXT,
            method TEXT,
            offset_bytes INTEGER,
            size_bytes INTEGER,
            file_path TEXT,
            md5 TEXT,
            sha256 TEXT,
            possible_camera_id TEXT,
            possible_start_utc TEXT,
            possible_end_utc TEXT,
            confidence REAL,
            status TEXT
        );

        CREATE TABLE IF NOT EXISTS analytics_events (
            event_id TEXT PRIMARY KEY,
            case_id TEXT,
            recording_id TEXT,
            event_type TEXT,
            timestamp_utc TEXT,
            label TEXT,
            confidence REAL,
            model_name TEXT,
            reviewed INTEGER DEFAULT 0,
            reviewer_notes TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            case_id TEXT,
            timestamp_utc TEXT,
            examiner TEXT,
            module TEXT,
            action TEXT,
            input TEXT,
            output TEXT,
            status TEXT,
            details TEXT
        );

        CREATE TABLE IF NOT EXISTS hashes (
            hash_id TEXT PRIMARY KEY,
            case_id TEXT,
            artifact_type TEXT,
            artifact_path TEXT,
            md5 TEXT,
            sha256 TEXT,
            calculated_at_utc TEXT,
            verified_at_utc TEXT,
            verification_status TEXT
        );
        "#,
    )?;
    Ok(())
}

pub fn read_case_row(conn: &Connection, case_id: &str) -> CoreResult<CaseRecord> {
    let mut stmt = conn.prepare(
        "SELECT case_id, case_name, examiner, organization, timezone_assumption, notes, created_at_utc, updated_at_utc, status FROM cases WHERE case_id = ?1",
    )?;
    let mut rows = stmt.query(params![case_id])?;
    let row = rows.next()?.ok_or_else(|| CoreError::CaseNotFound(case_id.to_string()))?;
    Ok(CaseRecord {
        case_id: row.get(0)?,
        case_name: row.get(1)?,
        examiner: row.get(2)?,
        organization: row.get(3)?,
        timezone_assumption: row.get(4)?,
        notes: row.get(5)?,
        created_at_utc: row.get(6)?,
        updated_at_utc: row.get(7)?,
        case_dir: PathBuf::from("cases").join(case_id),
        status: row.get(8)?,
    })
}

pub fn case_dir<P: AsRef<Path>>(storage_root: P, case_id: &str) -> PathBuf {
    storage_root.as_ref().join(case_id)
}

pub fn normalize_timestamp_input(
    raw: &str,
    tz: &str,
) -> Result<NormalizedTimestamp, String> {
    normalize_raw(raw, tz)
}

pub fn case_utc_now(case_id: &str) -> String {
    let _ = case_id;
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

pub fn case_dir_exists<P: AsRef<Path>>(storage_root: P, case_id: &str) -> bool {
    storage_root.as_ref().join(case_id).exists()
}

pub fn _unused_marker(_: DateTime<Utc>) {}