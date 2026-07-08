//! Runs the actual `sovereign-agent-runtime` binary and checks both demos drive
//! the agent loop — guarding the `main()` glue against regressions.

use std::process::Command;

#[test]
fn demo_runs_real_runtime_and_scripted_tool_loop() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-agent-runtime"))
        .output()
        .expect("run sovereign-agent-runtime");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    // Part 1: the real runtime drove the loop to completion.
    assert!(
        s.contains("completed=true"),
        "real runtime didn't complete:\n{s}"
    );
    // Part 2: the scripted run dispatched the tool and reached a final answer.
    assert!(
        s.contains("upper(\"sovereign\") = \"SOVEREIGN\""),
        "scripted tool loop missing:\n{s}"
    );
    assert!(s.contains("final answer"), "no final answer:\n{s}");
}

#[test]
fn runs_the_agent_on_an_operator_query() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-agent-runtime"))
        .arg("what is sovereignty")
        .output()
        .expect("run sovereign-agent-runtime QUERY");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    // The real loop ran on the operator's query to completion.
    assert!(s.contains("query="), "no query echoed:\n{s}");
    assert!(s.contains("completed=true"), "loop didn't complete:\n{s}");
}

#[test]
fn help_exits_zero() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-agent-runtime"))
        .arg("--help")
        .output()
        .expect("run sovereign-agent-runtime --help");
    assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("USAGE"));
}
