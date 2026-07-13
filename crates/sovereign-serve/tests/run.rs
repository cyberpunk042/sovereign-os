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
    assert!(s.contains("hit=exact"), "no $0 cache hit:\n{s}");
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
    assert!(s.contains("hit=exact"), "repeat should hit cache:\n{s}");
}

#[test]
fn semantic_flag_serves_a_paraphrase_for_free() {
    // With `--semantic`, a paraphrase of an earlier prompt is a $0 semantic hit
    // even though the byte-exact key differs.
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args([
            "--semantic",
            "how do I reset my password",
            "how can I reset the password",
        ])
        .output()
        .expect("run sovereign-serve --semantic");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("hit=semantic"), "no semantic hit:\n{s}");
    assert!(s.contains("1 semantic"), "summary missing semantic:\n{s}");
}

#[test]
fn redact_flag_runs_the_egress_gate() {
    // The model emits gibberish (no real secrets), so this checks the egress
    // path runs end-to-end and still serves; the scrub logic itself is unit-
    // tested in sovereign-llm.
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args(["--redact", "tell me a secret", "tell me a secret"])
        .output()
        .expect("run sovereign-serve --redact");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("hit=exact"), "repeat should still cache:\n{s}");
}

#[test]
fn screen_flag_runs_without_blocking_clean_output() {
    // The demo model emits gibberish (not toxic), so the screen gate passes the
    // completion through; this checks the egress-screen path runs end-to-end.
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args(["--screen", "hello there", "hello there"])
        .output()
        .expect("run sovereign-serve --screen");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("hit=exact"), "repeat should still cache:\n{s}");
}

#[test]
fn regex_flag_constrains_completions_to_digits() {
    // --regex [0-9]+ forces every served completion to be digits-only.
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args(["--regex", "[0-9]+", "give me a number"])
        .output()
        .expect("run sovereign-serve --regex");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    // the served text (printed after `-> `) is all ASCII digits
    let served = s
        .lines()
        .find(|l| l.contains("serve  ok"))
        .and_then(|l| l.rsplit("-> ").next())
        .unwrap_or("");
    let digits: String = served.chars().filter(|c| c.is_ascii_digit()).collect();
    assert!(!digits.is_empty(), "expected digits in served output:\n{s}");
    // no letters leaked into the constrained completion
    assert!(
        !served.chars().any(|c| c.is_ascii_alphabetic()),
        "non-digit leaked:\n{s}"
    );
}

#[test]
fn max_context_flag_runs_with_a_trimmed_prompt() {
    // A long prompt with --max-context 4 still serves (the prompt is trimmed
    // before generation); a repeat still cache-hits on the original prompt.
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args([
            "--max-context",
            "4",
            "the quick brown fox jumps over the lazy dog",
            "the quick brown fox jumps over the lazy dog",
        ])
        .output()
        .expect("run sovereign-serve --max-context");
    assert!(out.status.success());
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("hit=exact"), "repeat should cache:\n{s}");
}

#[test]
fn xtc_and_dry_flags_run_the_alternate_decoders() {
    for flag in ["--xtc", "--dry"] {
        let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
            .args([flag, "say something", "say something"])
            .output()
            .unwrap_or_else(|_| panic!("run sovereign-serve {flag}"));
        assert!(out.status.success(), "{flag} failed");
        let s = String::from_utf8_lossy(&out.stdout);
        assert!(s.contains("hit=exact"), "{flag}: repeat should cache:\n{s}");
    }
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

#[test]
fn rag_grounds_the_prompt_and_a_repeat_is_free() {
    // `--rag` grounds each query in the knowledge store, then serves the grounded
    // prompt through the cache — the repeat of a deterministic grounded prompt is
    // a $0 exact cache hit (retrieval + the cost-aware cache combined).
    let out = Command::new(env!("CARGO_BIN_EXE_sovereign-serve"))
        .args(["--rag", "what is sovereignty"])
        .output()
        .expect("run sovereign-serve --rag");
    assert!(out.status.success(), "exit: {:?}", out.status);
    let s = String::from_utf8_lossy(&out.stdout);
    assert!(s.contains("grounded=true"), "query was not grounded:\n{s}");
    assert!(
        s.contains("Context:"),
        "the served prompt was not augmented with retrieval:\n{s}"
    );
    assert!(
        s.contains("hit=exact"),
        "the repeated grounded query was not a $0 cache hit:\n{s}"
    );
    assert!(
        s.contains("cache hit(s) ($0)"),
        "no $0 cache-hit summary:\n{s}"
    );
}
