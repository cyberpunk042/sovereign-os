//! Runs the actual `sovereign-resource-control` binary and checks it emits the
//! systemd resource-control drop-ins — guarding the `main()` glue.

use std::process::Command;

const BIN: &str = env!("CARGO_BIN_EXE_sovereign-resource-control");

#[test]
fn emits_systemd_resource_control_drop_ins() {
    let out = Command::new(BIN).output().expect("run resource-control");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("[Service]"), "no unit section:\n{s}");
    assert!(s.contains("CPUWeight="), "no CPUWeight directive:\n{s}");
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
