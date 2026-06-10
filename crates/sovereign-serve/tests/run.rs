//! Runs the actual `sovereign-serve` binary and checks the demo session
//! exhibits the cost-aware behaviour — guarding the `main()` glue (which the
//! lib tests don't reach) against regressions.

use std::process::Command;

#[test]
fn demo_shows_cache_hit_and_budget_refusal() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .output()
        .expect("run sovereign-serve");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("cache_hit=true"), "no $0 cache hit:\n{s}");
    assert!(s.contains("REFUSED"), "no budget refusal:\n{s}");
    assert!(s.contains("cache hit(s) ($0)"), "no summary:\n{s}");
}

#[test]
fn serves_operator_prompts_with_a_cache_hit_on_repeat() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args(["what is sovereignty", "what is sovereignty"])
        .output()
        .expect("run sovereign-serve PROMPT PROMPT");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    // The repeated prompt resolves as a $0 cache hit.
    assert!(
        s.contains("cache_hit=true"),
        "repeat should hit cache:\n{s}"
    );
}

#[test]
fn help_exits_zero() {
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .arg("--help")
        .output()
        .expect("run sovereign-serve --help");
    assert!(out.status.success());
    assert!(String::from_utf8_lossy(&out.stdout).contains("USAGE"));
}
