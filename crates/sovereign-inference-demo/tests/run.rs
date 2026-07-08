//! Runs the actual `sovereign-inference-demo` binary and checks all three demos
//! produce output — guarding the `main()` glue.

use std::process::Command;

const BIN: &str = env!("CARGO_BIN_EXE_sovereign-inference-demo");

#[test]
fn runs_the_inference_decoding_and_agentic_demos() {
    let out = Command::new(BIN).output().expect("run inference-demo");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("inference demo"), "no inference demo:\n{s}");
    assert!(s.contains("decoding strategies"), "no decoding demo:\n{s}");
    assert!(s.contains("agentic stack"), "no agentic demo:\n{s}");
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
