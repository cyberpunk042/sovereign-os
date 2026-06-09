//! Runs the actual `sovereign-chat` binary and checks the session keeps history
//! bounded — guarding the `main()` glue against regressions.

use std::process::Command;

#[test]
fn demo_keeps_history_bounded() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-chat"))
        .output()
        .expect("run sovereign-chat");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    // The cap is reported, the system message is retained, and the body never
    // exceeds the cap (every reported turn shows "≤ 4").
    assert!(
        s.contains("non-system, ≤ 4"),
        "no bounded-history report:\n{s}"
    );
    assert!(
        s.contains("system always retained"),
        "system message not retained:\n{s}"
    );
    // At least two turns must report the body still at the cap (steady state),
    // proving older turns were dropped rather than the history growing.
    let at_cap = s.matches("4 non-system, ≤ 4").count();
    assert!(
        at_cap >= 2,
        "history did not stay bounded (saw {at_cap}):\n{s}"
    );
}

#[test]
fn runs_operator_messages_keeping_history_bounded() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-chat"))
        .args(["one", "two", "three", "four", "five"])
        .output()
        .expect("run sovereign-chat MESSAGE…");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    // The operator's turns run, and the history stays bounded (≤ 4).
    assert!(
        s.contains("non-system, ≤ 4"),
        "no bounded-history report:\n{s}"
    );
    assert!(
        s.matches("4 non-system, ≤ 4").count() >= 2,
        "history did not stay bounded:\n{s}"
    );
}

#[test]
fn help_exits_zero() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-chat"))
        .arg("--help")
        .output()
        .expect("run sovereign-chat --help");
    assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("USAGE"));
}
