//! `chromofold` — the honest-degrade diagnostic CLI for the ChromoFold surface.
//!
//! Mirrors the upstream engine's `chromofold info` / `chromofold selftest`
//! (SDD-400): `info` prints the [`sovereign_chromofold::CapabilityDescriptor`] as
//! JSON — the machine-readable truth about which primitives this build offers —
//! and `selftest` runs the offline, no-GPU round-trip that validates the surface
//! without ever fabricating a capability the build lacks. It is the precursor to
//! the `sovereign-osctl chromofold` verb (SDD-400 §Way forward step 5).

use std::process::ExitCode;

use sovereign_chromofold::{
    Availability, CapabilityDescriptor, ChromoFoldError, availability, count, descriptor,
};

fn print_info() {
    let d = descriptor();
    match serde_json::to_string_pretty(&d) {
        Ok(json) => println!("{json}"),
        // never fabricate output — surface the failure honestly
        Err(e) => eprintln!("chromofold: could not serialize descriptor: {e}"),
    }
}

/// Offline, no-GPU self-test: the descriptor serializes + round-trips, the FM-index
/// surface honest-degrades (never fabricates), and availability is reported truthfully.
fn selftest() -> Result<(), String> {
    let d = descriptor();
    let json =
        serde_json::to_string(&d).map_err(|e| format!("descriptor serialize failed: {e}"))?;
    let back: CapabilityDescriptor =
        serde_json::from_str(&json).map_err(|e| format!("descriptor round-trip failed: {e}"))?;
    if back != d {
        return Err("descriptor did not survive a serde round-trip".to_string());
    }
    // the FM-index surface must honest-degrade, never fabricate a search result:
    // Unavailable when no engine is linked, NotImplemented when it is (the C ABI is
    // bound but the host-side device marshalling is SDD-400 step 7).
    match (availability(), count(&[1, 2, 3])) {
        (Availability::Unavailable, Err(ChromoFoldError::Unavailable)) => {}
        (Availability::Linked, Err(ChromoFoldError::NotImplemented)) => {}
        other => return Err(format!("FM-index count did not honest-degrade: {other:?}")),
    }
    Ok(())
}

fn main() -> ExitCode {
    let cmd = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "info".to_string());
    match cmd.as_str() {
        "info" => {
            print_info();
            ExitCode::SUCCESS
        }
        "selftest" => match selftest() {
            Ok(()) => {
                let note = match availability() {
                    Availability::Linked => "engine linked",
                    Availability::Unavailable => "honest-degrade (engine not linked)",
                };
                println!("chromofold selftest: PASS — {note}");
                ExitCode::SUCCESS
            }
            Err(why) => {
                eprintln!("chromofold selftest: FAIL — {why}");
                ExitCode::FAILURE
            }
        },
        other => {
            eprintln!("chromofold: unknown command {other:?} (expected `info` or `selftest`)");
            ExitCode::FAILURE
        }
    }
}
