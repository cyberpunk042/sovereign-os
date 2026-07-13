//! Compute wrappers for `sovereign-cockpit-stepper` — expose its real wizard
//! state-machine to the panel via wasm, beyond validate() (audit F-2026-001).
//!
//! Functional: parse the `Stepper` state JSON, apply the requested navigation
//! op on a LOCAL copy, and return the NEW advanced state (current index + each
//! Step's status). Never panics — parse errors, an unknown op, and the crate's
//! own domain errors all come back as `{"ok":false,"error":...}`.
use sovereign_cockpit_stepper::Stepper;
use wasm_bindgen::prelude::*;

/// Advance a `Stepper` (JSON state) by one navigation `op`, running the crate's
/// REAL state machine instead of a drifting JS re-implementation. `op` is one
/// of `"next"`, `"back"`, `"complete"`, `"fail"`, `"skip"` — mapping to
/// `Stepper::next` / `back` / `complete_current` / `fail_current` /
/// `skip_current`. Returns JSON `{"ok":true,"value":<new Stepper state>}` on
/// success (the panel sees the advanced state: `active` index + each Step's
/// `status`), or `{"ok":false,"error":"..."}` on a parse error, an unknown op,
/// or a domain error (e.g. skip not allowed, next past the end).
#[wasm_bindgen]
pub fn stepper_advance(state_json: &str, op: &str) -> String {
    let mut stepper: Stepper = match serde_json::from_str(state_json) {
        Ok(s) => s,
        Err(e) => {
            return serde_json::json!({ "ok": false, "error": format!("parse: {e}") }).to_string()
        }
    };
    // Guard: the crate's mutators index `steps[active]` directly, so a
    // parseable-but-invalid state (active out of range / no steps) would panic.
    // Run the crate's real `validate()` first and surface any breach as an
    // error object rather than letting it panic.
    if let Err(e) = stepper.validate() {
        return serde_json::json!({ "ok": false, "error": e.to_string() }).to_string();
    }
    // Apply the matching mutation on the local copy. `complete`/`fail` are
    // infallible; `next`/`back`/`skip` return the crate's domain `Result`.
    let outcome: Result<(), String> = match op {
        "next" => stepper.next().map_err(|e| e.to_string()),
        "back" => stepper.back().map_err(|e| e.to_string()),
        "complete" => {
            stepper.complete_current();
            Ok(())
        }
        "fail" => {
            stepper.fail_current();
            Ok(())
        }
        "skip" => stepper.skip_current().map_err(|e| e.to_string()),
        other => Err(format!("unknown op {other:?}")),
    };
    match outcome {
        Ok(()) => match serde_json::to_value(&stepper) {
            Ok(v) => serde_json::json!({ "ok": true, "value": v }).to_string(),
            Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }).to_string(),
        },
        Err(e) => serde_json::json!({ "ok": false, "error": e }).to_string(),
    }
}
