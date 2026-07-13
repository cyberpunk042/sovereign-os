//! Compute wrappers for `sovereign-cockpit-progress-tracker` — expose its real
//! rollup (average progress across Determinate tasks) to the panel via wasm,
//! beyond validate() (audit F-2026-001).
//!
//! Functional: parse an array of `Task`, `start()` each into a fresh
//! `ProgressTracker`, and return the crate's REAL aggregate. Never panics —
//! parse errors and the crate's own domain errors come back as
//! `{"ok":false,"error":...}`.
use sovereign_cockpit_progress_tracker::{ProgressTracker, Task};
use wasm_bindgen::prelude::*;

/// Summarize an array of `Task` (JSON) by running the crate's REAL aggregate:
/// each task is `start()`ed into a fresh `ProgressTracker`, then
/// `average_progress()` (0..=100, computed over Determinate tasks only) is read
/// off the crate — not re-implemented in drifting JS. Returns JSON
/// `{"ok":true,"average":<u8>,"tasks":[<each task>]}` on success, or
/// `{"ok":false,"error":"..."}` on a parse error or a domain error from
/// `start()` (empty id / empty label / progress > 100 / duplicate id).
#[wasm_bindgen]
pub fn progress_summary(tasks_json: &str) -> String {
    let tasks: Vec<Task> = match serde_json::from_str(tasks_json) {
        Ok(t) => t,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    // Feed each task through the crate's real constructor path (`start`), which
    // enforces shape + duplicate-id rules — this is the same aggregate the
    // daemon builds, not a JS copy.
    let mut tracker = ProgressTracker::new();
    for task in tasks {
        if let Err(e) = tracker.start(task) {
            return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
        }
    }
    let average = tracker.average_progress();
    match serde_json::to_value(&tracker.tasks) {
        Ok(v) => serde_json::json!({ "ok": true, "average": average, "tasks": v }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
