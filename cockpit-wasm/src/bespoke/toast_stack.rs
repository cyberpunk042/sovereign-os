//! Bespoke wasm bridge for `sovereign-cockpit-toast-stack` (no uniform validate()).
//! Exposes the real toast state machine (bounded push+eviction, TTL expiry,
//! dismiss) so the panel runs the crate's REAL logic (F-2026-001). Mutations are
//! functional: parse state JSON, apply on a local copy, return the NEW state.
use sovereign_cockpit_toast_stack::{validate_schema_version, Toast, ToastStack};
use wasm_bindgen::prelude::*;

/// Construct a fresh bounded stack via the crate's real `ToastStack::new`
/// (enforces capacity ≥ 1). Returns JSON `{"ok":true,"value":<stack>}` or
/// `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn toast_stack_new(capacity: u32) -> String {
    match ToastStack::new(capacity as usize) {
        Ok(s) => serde_json::json!({ "ok": true, "value": serde_json::to_value(&s).unwrap() })
            .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Push a `Toast` (JSON) onto a `ToastStack` (JSON) via the crate's real
/// `push` — the severity-ordered eviction / duplicate-id rules run in Rust.
/// Returns JSON `{"ok":true,"value":<new stack>}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn toast_stack_push(stack_json: &str, toast_json: &str) -> String {
    let mut stack: ToastStack = match serde_json::from_str(stack_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let toast: Toast = match serde_json::from_str(toast_json) {
        Ok(t) => t,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    match stack.push(toast) {
        Ok(()) => serde_json::json!({ "ok": true, "value": serde_json::to_value(&stack).unwrap() })
            .to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}

/// Dismiss a toast by `id` on a `ToastStack` (JSON) via the crate's real
/// `dismiss`. Returns JSON `{"ok":true,"removed":bool,"value":<new stack>}` or
/// `{"ok":false,"error":"parse: ..."}` if the state JSON is unparseable.
#[wasm_bindgen]
pub fn toast_stack_dismiss(stack_json: &str, id: &str) -> String {
    let mut stack: ToastStack = match serde_json::from_str(stack_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let removed = stack.dismiss(id);
    serde_json::json!({ "ok": true, "removed": removed, "value": serde_json::to_value(&stack).unwrap() })
        .to_string()
}

/// Expire due toasts at `now_ms` on a `ToastStack` (JSON) via the crate's real
/// `expire` (TTL rule `created_at_ms + ttl_ms <= now_ms`). Returns JSON
/// `{"ok":true,"removed":[ids],"value":<new stack>}` or `{"ok":false,"error":"parse: ..."}`.
#[wasm_bindgen]
pub fn toast_stack_expire(stack_json: &str, now_ms: f64) -> String {
    let mut stack: ToastStack = match serde_json::from_str(stack_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    let removed = stack.expire(now_ms as u64);
    serde_json::json!({ "ok": true, "removed": removed, "value": serde_json::to_value(&stack).unwrap() })
        .to_string()
}

/// Run the crate's real `validate_schema_version`. Returns JSON
/// `{"ok":true,"error":null}` or `{"ok":false,"error":"..."}`.
#[wasm_bindgen]
pub fn toast_stack_validate_schema_version(s: &str) -> String {
    match validate_schema_version(s) {
        Ok(()) => serde_json::json!({ "ok": true, "error": serde_json::Value::Null }).to_string(),
        Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
    }
}
