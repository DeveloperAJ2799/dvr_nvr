use chrono::{DateTime, NaiveDateTime, TimeZone, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NormalizedTimestamp {
    pub raw: String,
    pub utc: DateTime<Utc>,
    pub timezone_assumed: String,
}

pub fn now_utc_string() -> String {
    Utc::now().format("%Y-%m-%dT%H:%M:%SZ").to_string()
}

pub fn now_utc() -> DateTime<Utc> {
    Utc::now()
}

pub fn normalize_raw(
    raw: &str,
    timezone_assumption: &str,
) -> Result<NormalizedTimestamp, String> {
    if let Ok(dt) = DateTime::parse_from_rfc3339(raw) {
        return Ok(NormalizedTimestamp {
            raw: raw.to_string(),
            utc: dt.with_timezone(&Utc),
            timezone_assumed: "rfc3339".to_string(),
        });
    }

    let formats = [
        "%Y%m%d%H%M%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%d-%m-%Y %H:%M:%S",
    ];

    for fmt in formats {
        if let Ok(naive) = NaiveDateTime::parse_from_str(raw, fmt) {
            let utc = match timezone_assumption {
                "UTC" => Utc.from_utc_datetime(&naive),
                "local" => {
                    let local = chrono::Local.from_local_datetime(&naive).single();
                    match local {
                        Some(l) => l.with_timezone(&Utc),
                        None => Utc.from_utc_datetime(&naive),
                    }
                }
                _ => Utc.from_utc_datetime(&naive),
            };
            return Ok(NormalizedTimestamp {
                raw: raw.to_string(),
                utc,
                timezone_assumed: timezone_assumption.to_string(),
            });
        }
    }

    Err(format!("Could not parse timestamp: {}", raw))
}

pub fn duration_seconds(start: &NormalizedTimestamp, end: &NormalizedTimestamp) -> i64 {
    (end.utc - start.utc).num_seconds().max(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_rfc3339_with_offset() {
        let n = normalize_raw("2026-01-02T03:04:05+02:00", "UTC").unwrap();
        assert_eq!(n.utc.to_rfc3339(), "2026-01-02T01:04:05+00:00");
        assert_eq!(n.timezone_assumed, "rfc3339");
    }

    #[test]
    fn parses_space_format_as_utc_when_utc_assumed() {
        let n = normalize_raw("2024-06-01 12:30:00", "UTC").unwrap();
        assert_eq!(n.utc.format("%Y-%m-%dT%H:%M:%SZ").to_string(), "2024-06-01T12:30:00Z");
    }

    #[test]
    fn parses_compact_dvr_format() {
        let n = normalize_raw("20240601123000", "UTC").unwrap();
        assert_eq!(n.utc.format("%Y-%m-%d %H:%M:%S").to_string(), "2024-06-01 12:30:00");
    }

    #[test]
    fn parses_day_first_format() {
        let n = normalize_raw("05-01-2024 08:00:00", "UTC").unwrap();
        // Day-first: 5 January, not 1 May.
        assert_eq!(n.utc.format("%d/%m/%Y").to_string(), "05/01/2024");
    }

    #[test]
    fn unknown_format_is_an_error() {
        assert!(normalize_raw("not a timestamp", "UTC").is_err());
    }
}