//! Compute wrappers for `sovereign-cockpit-alert-group` — expose its real by-tag
//! rollup (observe → total / groups_by_severity) to the panel via wasm, beyond
//! validate() (audit F-2026-001).
//!
//! Functional: build a local `AlertGroup`, replay the raw events through the
//! crate's real `observe`, then read `total()` + `groups_by_severity()`. Holds no
//! state across calls; never panics (parse/domain errors return `{"ok":false}`).
use sovereign_cockpit_alert_group::{AlertGroup, Severity};
use wasm_bindgen::prelude::*;

/// Roll up a batch of raw alert events by tag using the crate's REAL grouping.
///
/// Input: a JSON array `[{ "tag": string, "severity": "<kebab>", "ts_ms": number }, ...]`
/// (severity kebab tokens: `info` / `warning` / `error` / `critical`). Returns JSON
/// `{"ok":true,"total":<u64>,"groups":[<Group>, ...]}` — groups ordered max-severity
/// desc then latest-ts desc (the crate's `groups_by_severity` order) — or
/// `{"ok":false,"error":"..."}` on any parse/domain error.
#[wasm_bindgen]
pub fn alert_group_rollup(events_json: &str) -> String {
    let events: Vec<serde_json::Value> = match serde_json::from_str(events_json) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };

    let mut group = AlertGroup::new();
    for (i, ev) in events.iter().enumerate() {
        let tag = match ev.get("tag").and_then(|v| v.as_str()) {
            Some(t) => t,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("event {i}: missing string \"tag\""),
                })
                .to_string()
            }
        };
        let tok = match ev.get("severity").and_then(|v| v.as_str()) {
            Some(s) => s,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("event {i}: missing string \"severity\""),
                })
                .to_string()
            }
        };
        // Severity crosses as its serde kebab token — parse it via from_value.
        let severity: Severity =
            match serde_json::from_value(serde_json::Value::String(tok.to_string())) {
                Ok(s) => s,
                Err(_) => {
                    return serde_json::json!({
                        "ok": false,
                        "error": format!("event {i}: unknown severity {tok:?}"),
                    })
                    .to_string()
                }
            };
        let ts_ms: u64 = match ev
            .get("ts_ms")
            .and_then(|v| v.as_u64().or_else(|| v.as_f64().map(|f| f as u64)))
        {
            Some(t) => t,
            None => {
                return serde_json::json!({
                    "ok": false,
                    "error": format!("event {i}: missing/invalid number \"ts_ms\""),
                })
                .to_string()
            }
        };

        if let Err(e) = group.observe(tag, severity, ts_ms) {
            return serde_json::json!({ "ok": false, "error": format!("event {i}: {e}") })
                .to_string();
        }
    }

    // `Group` derives Serialize, so the borrowed slice serializes directly.
    let groups = match serde_json::to_value(group.groups_by_severity()) {
        Ok(v) => v,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("serialize: {e}") })
                .to_string()
        }
    };

    serde_json::json!({ "ok": true, "total": group.total(), "groups": groups }).to_string()
}
