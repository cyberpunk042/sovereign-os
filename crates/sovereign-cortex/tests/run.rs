//! Runs the actual `sovereign-cortex` binary and checks each mode — guarding the
//! `main()` glue (the demo session, `--explain`, `--search`) that the lib tests
//! don't reach.

use std::process::Command;

const BIN: &str = env!("CARGO_BIN_EXE_sovereign-cortex");

#[test]
fn default_demo_session_runs_and_exits_zero() {
    let out = Command::new(BIN).output().expect("run sovereign-cortex");
    // The demo requests all commit (no refusals) and never-cloud-spill holds, so
    // the exit code is 0; stdout carries the decisions as JSON.
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("\"route\""), "no decision JSON:\n{s}");
}

#[test]
fn explain_prints_the_rationale_on_stdout() {
    let out = Command::new(BIN)
        .arg("--explain")
        .output()
        .expect("run --explain");
    assert!(out.status.success());
    assert!(
        String::from_utf8_lossy(&out.stdout).contains("Routed to"),
        "no rationale on stdout"
    );
}

#[test]
fn search_demo_converges_to_commit() {
    let out = Command::new(BIN)
        .arg("--search")
        .output()
        .expect("run --search");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("committed=true"), "search didn't converge:\n{s}");
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
