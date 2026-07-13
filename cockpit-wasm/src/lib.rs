//! `cockpit-wasm` — the browser bridge for sovereign-os's typed cockpit crates.
//!
//! Audit finding **F-2026-001**: 413 `sovereign-cockpit-*` crates encode the
//! cockpit's UX state logic in typed, tested Rust — yet nothing runs them (the
//! webapp is hand-written HTML/JS, so every panel re-implements that logic and
//! can silently drift from the crate). This crate is the bridge: a wasm-bindgen
//! facade that compiles the real crate logic to wasm32 so a panel calls the
//! **same** Rust decision function the daemon uses, instead of a JS copy.
//!
//! First crate bridged: `sovereign-cockpit-banner-state` — `compute_severity`
//! (the top-bar severity rules), `build`, and `validate`. The pattern scales:
//! each further `sovereign-cockpit-*` crate adds a thin wrapper here.
//!
//! Boundary convention: enums cross as their serde **kebab** tokens (`execute`,
//! `throttle`, `careful`, …) and structs as JSON — the exact shapes the panels
//! already speak. Bad tokens return a readable error rather than panicking.
//!
//! This crate lives OUTSIDE the workspace (see root `Cargo.toml`
//! `[workspace].exclude`): wasm-bindgen's macro emits `unsafe` glue, and the
//! workspace keeps `sovereign-simd` as its single sanctioned unsafe crate.

use serde::de::DeserializeOwned;
use serde::Serialize;
use wasm_bindgen::prelude::*;

use sovereign_cockpit_banner_state::{compute_severity, BannerState, SCHEMA_VERSION};
use sovereign_execution_mode_registry::ExecutionMode;
use sovereign_hardware_thermal_policy::ThermalVerdict;
use sovereign_profile_bundles::BundleName;

/// Generated per-crate `<slug>_validate` bridges — one `bridge_validate!` line
/// per uniform cockpit crate, produced by `cockpit-wasm/gen-bridges.py`. Behind
/// the `bridges` feature so the default (committed demo) build stays banner-only
/// + small; the full family compiles under `--features bridges`.
#[cfg(feature = "bridges")]
mod bridges;

/// Generate a `#[wasm_bindgen] pub fn <name>(json)` that parses a cockpit
/// crate's primary type and runs its **real** `validate()`, returning
/// `{"ok":bool,"error":string|null}` (never panics). This is the uniform bridge
/// for the ~399 cockpit crates whose `validate(&self) -> Result<(), E>` is the
/// invariant the webapp must not silently re-implement in drifting JS.
#[macro_export]
macro_rules! bridge_validate {
    ($name:ident, $ty:path) => {
        #[wasm_bindgen]
        pub fn $name(json: &str) -> String {
            match ::serde_json::from_str::<$ty>(json) {
                Ok(v) => match v.validate() {
                    Ok(()) => {
                        ::serde_json::json!({ "ok": true, "error": ::serde_json::Value::Null })
                            .to_string()
                    }
                    Err(e) => {
                        ::serde_json::json!({ "ok": false, "error": e.to_string() }).to_string()
                    }
                },
                Err(e) => ::serde_json::json!({ "ok": false, "error": format!("parse: {}", e) })
                    .to_string(),
            }
        }
    };
}

/// Serialize a serde value to its bare kebab token (drops the JSON quotes).
fn kebab<T: Serialize>(v: &T) -> String {
    serde_json::to_string(v)
        .unwrap_or_default()
        .trim_matches('"')
        .to_string()
}

/// Deserialize one kebab token into an enum `T`, with a readable error.
fn de_enum<T: DeserializeOwned>(field: &str, token: &str) -> Result<T, String> {
    serde_json::from_value(serde_json::Value::String(token.to_string()))
        .map_err(|_| format!("{field}: unknown value {token:?}"))
}

// --- native-testable core (no wasm-bindgen; exercised by `cargo test`) ------

/// Real banner severity for the given live signals, as a kebab token.
fn severity_of(mode: &str, worst_thermal: &str, open_alerts: u32) -> Result<String, String> {
    let m: ExecutionMode = de_enum("mode", mode)?;
    let t: ThermalVerdict = de_enum("worst_thermal", worst_thermal)?;
    Ok(kebab(&compute_severity(m, t, open_alerts)))
}

/// Build a full `BannerState` (severity computed by the crate) as JSON.
fn state_of(
    mode: &str,
    bundle: &str,
    worst_thermal: &str,
    open_alerts: u32,
    updated_at: &str,
) -> Result<String, String> {
    let m: ExecutionMode = de_enum("mode", mode)?;
    let b: BundleName = de_enum("bundle", bundle)?;
    let t: ThermalVerdict = de_enum("worst_thermal", worst_thermal)?;
    serde_json::to_string(&BannerState::build(m, b, t, open_alerts, updated_at))
        .map_err(|e| e.to_string())
}

/// Validate a `BannerState` JSON against the crate's own `validate()`.
/// Returns `{"ok":bool,"error":string|null}` — never panics.
fn validate_of(state_json: &str) -> String {
    let outcome = match serde_json::from_str::<BannerState>(state_json) {
        Ok(st) => match st.validate() {
            Ok(()) => serde_json::json!({ "ok": true, "error": serde_json::Value::Null }),
            Err(e) => serde_json::json!({ "ok": false, "error": e.to_string() }),
        },
        Err(e) => serde_json::json!({ "ok": false, "error": format!("parse: {e}") }),
    };
    outcome.to_string()
}

// --- wasm-bindgen exports (thin wrappers over the core above) ---------------

/// Compute the top-bar banner severity from the live signals, running the real
/// `sovereign-cockpit-banner-state::compute_severity`. Returns a kebab token
/// (`calm` / `notice` / `warn` / `critical`); throws on an unknown enum token.
#[wasm_bindgen]
pub fn banner_severity(
    mode: &str,
    worst_thermal: &str,
    open_alerts: u32,
) -> Result<String, JsError> {
    severity_of(mode, worst_thermal, open_alerts).map_err(|e| JsError::new(&e))
}

/// Build a full signed-shape `BannerState` JSON (severity computed by the crate).
/// Throws on an unknown enum token.
#[wasm_bindgen]
pub fn banner_state(
    mode: &str,
    bundle: &str,
    worst_thermal: &str,
    open_alerts: u32,
    updated_at: &str,
) -> Result<String, JsError> {
    state_of(mode, bundle, worst_thermal, open_alerts, updated_at).map_err(|e| JsError::new(&e))
}

/// Validate a `BannerState` JSON with the crate's `validate()`.
/// Returns `{"ok":bool,"error":string|null}`.
#[wasm_bindgen]
pub fn banner_validate(state_json: &str) -> String {
    validate_of(state_json)
}

/// The banner-state schema version the bridge was built against.
#[wasm_bindgen]
pub fn schema_version() -> String {
    SCHEMA_VERSION.to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn severity_matches_the_crate_rules() {
        // Mirrors sovereign-cockpit-banner-state's own tests, through the bridge.
        assert_eq!(severity_of("plan", "cool", 0).unwrap(), "calm");
        assert_eq!(severity_of("execute", "cool", 0).unwrap(), "notice");
        assert_eq!(severity_of("plan", "warm", 0).unwrap(), "notice");
        assert_eq!(severity_of("plan", "throttle", 0).unwrap(), "warn");
        assert_eq!(severity_of("plan", "cool", 1).unwrap(), "warn");
        assert_eq!(severity_of("plan", "cool", 6).unwrap(), "critical");
        assert_eq!(severity_of("plan", "shutdown", 0).unwrap(), "critical");
    }

    #[test]
    fn unknown_tokens_error_not_panic() {
        assert!(severity_of("nope", "cool", 0).is_err());
        assert!(severity_of("plan", "molten", 0).is_err());
        assert!(state_of("plan", "no-such-bundle", "cool", 0, "t").is_err());
    }

    #[test]
    fn state_builds_and_self_validates() {
        let j = state_of("execute", "fast", "warm", 2, "2026-05-19T03:00:00Z").unwrap();
        // The built state carries the crate-computed severity...
        assert!(j.contains("\"severity\":\"warn\""), "{j}");
        // ...and passes the crate's own validate() round-trip.
        let v: serde_json::Value = serde_json::from_str(&validate_of(&j)).unwrap();
        assert_eq!(v["ok"], serde_json::json!(true), "{v}");
    }

    #[test]
    fn validate_rejects_tampered_severity() {
        let good = state_of("plan", "careful", "cool", 0, "t").unwrap();
        let tampered = good.replace("\"severity\":\"calm\"", "\"severity\":\"critical\"");
        assert_ne!(good, tampered, "sanity: replacement happened");
        let v: serde_json::Value = serde_json::from_str(&validate_of(&tampered)).unwrap();
        assert_eq!(v["ok"], serde_json::json!(false), "{v}");
    }

    #[test]
    fn schema_version_is_exposed() {
        assert_eq!(schema_version(), SCHEMA_VERSION);
    }

    // A generated `<slug>_validate` bridge must reach the crate's REAL validate()
    // — not just parse — returning its real error. Runs under --features bridges.
    #[cfg(feature = "bridges")]
    #[test]
    fn generated_bridge_reaches_real_validate() {
        let ok = crate::bridges::item_pin_validate(
            r#"{"schema_version":"1.0.0","max_pins":5,"pinned":["a"]}"#,
        );
        assert!(ok.contains("\"ok\":true"), "{ok}");
        let bad = crate::bridges::item_pin_validate(
            r#"{"schema_version":"9.9","max_pins":5,"pinned":[]}"#,
        );
        assert!(
            bad.contains("\"ok\":false") && bad.contains("schema version mismatch"),
            "{bad}"
        );
        let parse = crate::bridges::item_pin_validate("garbage");
        assert!(
            parse.contains("\"ok\":false") && parse.contains("parse:"),
            "{parse}"
        );
    }
}
