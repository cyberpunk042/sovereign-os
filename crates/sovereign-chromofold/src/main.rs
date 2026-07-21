//! `chromofold` — the honest-degrade diagnostic CLI for the ChromoFold surface.
//!
//! Mirrors the upstream engine's `chromofold info` / `chromofold selftest`
//! (SDD-400): `info` prints the [`sovereign_chromofold::CapabilityDescriptor`] as
//! JSON — the machine-readable truth about which primitives this build offers —
//! and `selftest` runs the offline, no-GPU round-trip that validates the surface
//! without ever fabricating a capability the build lacks. It is the precursor to
//! the `sovereign-osctl chromofold` verb (SDD-400 §Way forward step 5).

use std::process::ExitCode;

use sovereign_chromofold::{Availability, CapabilityDescriptor, FmIndex, availability, descriptor};

fn print_info() {
    let d = descriptor();
    match serde_json::to_string_pretty(&d) {
        Ok(json) => println!("{json}"),
        // never fabricate output — surface the failure honestly
        Err(e) => eprintln!("chromofold: could not serialize descriptor: {e}"),
    }
}

/// Offline, no-GPU self-test: the descriptor round-trips, and the CPU-native
/// FM-index (provenance-B) returns the correct count/locate for a known stream —
/// a real functional check, no GPU, no fabrication.
fn selftest() -> Result<(), String> {
    let d = descriptor();
    let json =
        serde_json::to_string(&d).map_err(|e| format!("descriptor serialize failed: {e}"))?;
    let back: CapabilityDescriptor =
        serde_json::from_str(&json).map_err(|e| format!("descriptor round-trip failed: {e}"))?;
    if back != d {
        return Err("descriptor did not survive a serde round-trip".to_string());
    }
    // provenance-B functional check against a known answer ("abracadabra").
    let text: Vec<u32> = "abracadabra".bytes().map(u32::from).collect();
    let idx = FmIndex::build(&text);
    let a = b'a' as u32;
    if idx.count(&[a]) != 5 {
        return Err(format!(
            "FM-index count('a') = {}, expected 5",
            idx.count(&[a])
        ));
    }
    let abra: Vec<u32> = "abra".bytes().map(u32::from).collect();
    if idx.locate(&abra) != vec![0, 7] {
        return Err(format!(
            "FM-index locate('abra') = {:?}, expected [0, 7]",
            idx.locate(&abra)
        ));
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
