// NYAYA Forensics — Tauri v2 entry point.
// The entire app is wired in `lib.rs` via the `run()` builder; this binary
// stays deliberately tiny (single-page shell).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    nyaya_forensics_lib::run()
}