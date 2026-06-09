//! End-to-end smoke test for the `sovereign-telemetry` binary.
//!
//! Runs the real binary against the live host and asserts the emitted JSON
//! honours the telemetry contract: a validated 6-axis pressure snapshot and a
//! 5-target load snapshot that validates against the canonical registry. This
//! gates the runnable probe in CI so the assembly can't silently regress.

use std::process::Command;

use serde_json::Value;

#[test]
fn emits_contract_honouring_telemetry_json() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-telemetry"))
        .output()
        .expect("binary runs");
    assert!(out.status.success(), "exit status: {:?}", out.status);

    let doc: Value = serde_json::from_slice(&out.stdout).expect("stdout is JSON");

    assert_eq!(doc["schema"], "sovereign-telemetry/1");
    assert!(doc["captured_at_unix"].is_string());

    // Pressure: exactly the 6 canonical axes, every value normalised 0..=1.
    let axes = doc["pressure"]["readings"]
        .as_array()
        .expect("readings array");
    assert_eq!(axes.len(), 6, "six pressure axes");
    for r in axes {
        let v = r["value"].as_f64().expect("axis value is a number");
        assert!((0.0..=1.0).contains(&v), "axis {r} out of range");
    }

    // Load: exactly the 5 canonical targets, and the snapshot validated
    // against the registry (cpu-pulse carries a real /proc/stat sample).
    let loads = doc["load"]["loads"].as_array().expect("loads array");
    assert_eq!(loads.len(), 5, "five load targets");
    assert_eq!(doc["load_valid"], true, "load validates against registry");

    let cpu = loads
        .iter()
        .find(|l| l["target"] == "cpu-pulse")
        .expect("cpu-pulse target present");
    let util = cpu["util_pct"].as_u64().expect("util_pct is a number");
    assert!(util <= 100, "cpu util in range");

    // Observability: exactly the 9 canonical sources, and the fabric validated.
    let sources = doc["observability"]["sources"]
        .as_array()
        .expect("sources array");
    assert_eq!(sources.len(), 9, "nine observability sources");
    assert_eq!(doc["observability_valid"], true, "fabric validates");

    // Derived: a thermal verdict per target + a shutdown flag (the telemetry
    // → scheduling-decision chain running end-to-end).
    let verdicts = doc["derived"]["thermal_verdicts"]
        .as_array()
        .expect("thermal_verdicts array");
    assert_eq!(verdicts.len(), 5, "one thermal verdict per target");
    for v in verdicts {
        assert!(v["target"].is_string() && v["verdict"].is_string());
    }
    assert!(doc["derived"]["thermal_any_shutdown"].is_boolean());

    // E0431 adaptive reactions: an array; each entry carries a trigger and a
    // non-empty verbatim action list.
    let reactions = doc["derived"]["adaptive_reactions"]
        .as_array()
        .expect("adaptive_reactions array");
    for r in reactions {
        assert!(r["trigger"].is_string());
        assert!(
            !r["actions"].as_array().expect("actions array").is_empty(),
            "every fired reaction prescribes at least one action"
        );
    }
}
