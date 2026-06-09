//! Runs the actual `sovereign-telemetry` binary and checks it emits a telemetry
//! sample — guarding the `main()` glue. Host-independent: every probe degrades
//! to `null` when a source is absent, so the document structure is always there.

use std::process::Command;

const BIN: &str = env!("CARGO_BIN_EXE_sovereign-telemetry");

#[test]
fn emits_a_json_telemetry_sample() {
    let out = Command::new(BIN).output().expect("run sovereign-telemetry");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    // The structured document is present regardless of host hardware.
    assert!(
        s.contains("captured_at_unix"),
        "no telemetry document:\n{s}"
    );
    assert!(s.contains("thermal_verdicts"), "no derived signals:\n{s}");
}

#[test]
fn prometheus_mode_emits_exposition() {
    let out = Command::new(BIN)
        .arg("--prometheus")
        .output()
        .expect("run --prometheus");
    assert!(out.status.success());
    assert!(
        String::from_utf8_lossy(&out.stdout).contains("# TYPE sovereign_"),
        "no Prometheus exposition"
    );
}

#[test]
fn help_exits_zero() {
    let out = Command::new(BIN)
        .arg("--help")
        .output()
        .expect("run --help");
    assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("USAGE"));
}
