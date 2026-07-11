//! `sovereign-feature-selftest` — per-feature LIVE self-tests for the Feature
//! Test Lab cockpit panel.
//!
//! These are NOT unit tests. Each self-test RUNS the real shipped feature and
//! reports what actually happened — the path the code took, timing, and a list
//! of pass/fail checks — as JSON on stdout, so the operator can exercise a
//! feature from the panel and watch it work. Modeled on the `sovereign-telemetry`
//! probe: pretty JSON, graceful, exit 0 (exit 1 only on a serialization fault).
//!
//! Usage:
//!   sovereign-feature-selftest list                 → the available features (JSON)
//!   sovereign-feature-selftest run <feature> [--json]  → one feature's result
//!   sovereign-feature-selftest run-all [--json]        → every feature's result
//!   sovereign-feature-selftest --self-check            → run-all, exit 0 (CI smoke)

#![forbid(unsafe_code)]

use std::time::Instant;

use serde::Serialize;

/// One pass/fail check inside a feature self-test.
#[derive(Serialize)]
struct Check {
    name: String,
    ok: bool,
    detail: String,
}

/// The result of running one feature's live self-test — the shape the panel's
/// test-card renders (result / path-taken / timing / checks).
#[derive(Serialize)]
struct FeatureResult {
    /// stable machine id (also the `run <feature>` selector)
    feature: &'static str,
    /// human label for the card
    label: &'static str,
    /// overall pass/fail (all checks passed)
    ok: bool,
    /// which real code path executed (e.g. "avx512f" vs "scalar")
    path_taken: String,
    /// wall-clock duration of the exercise, microseconds
    duration_us: u128,
    /// one-line human summary
    detail: String,
    /// the individual checks that make up the verdict
    checks: Vec<Check>,
}

/// A deterministic pseudo-random f32 in [-3, 3) from an index — so the exercise
/// is reproducible run-to-run with no `rand` dependency and no unsafe.
fn det_val(i: usize) -> f32 {
    // a cheap integer hash → [0,1) → [-3,3)
    let h = (i as u64)
        .wrapping_mul(0x9E37_79B9_7F4A_7C15)
        .wrapping_add(0x1234_5678);
    let unit = ((h >> 40) as f32) / ((1u64 << 24) as f32); // 24 bits → [0,1)
    unit * 6.0 - 3.0
}

/// SIMD-vs-scalar equality tolerance (matches the crate's own `close`).
fn close(a: f32, b: f32) -> bool {
    (a - b).abs() <= 1e-4 * (a.abs() + b.abs() + 1.0)
}

/// Live self-test of the AVX-512 `sum_of_squares` kernel (`sovereign-simd`):
/// exercises the real dispatcher across lengths straddling the 16-lane
/// boundary, proves the SIMD path equals the scalar reference, reports which
/// path the host actually took, and times both paths for a speedup.
fn selftest_simd_sum_of_squares() -> FeatureResult {
    use sovereign_simd::{has_avx512f, sum_of_squares, sum_of_squares_scalar};

    let started = Instant::now();
    let mut checks = Vec::new();
    let mut all_ok = true;

    let path = if has_avx512f() { "avx512f" } else { "scalar" };

    // 1. equality across lengths that straddle the 16-lane chunk + remainder.
    let lengths = [0usize, 1, 7, 15, 16, 17, 31, 32, 33, 64, 100, 257, 1000, 4096];
    let mut worst_delta = 0.0f32;
    let mut eq_ok = true;
    for &n in &lengths {
        let x: Vec<f32> = (0..n).map(det_val).collect();
        let simd = sum_of_squares(&x);
        let scalar = sum_of_squares_scalar(&x);
        worst_delta = worst_delta.max((simd - scalar).abs());
        if !close(simd, scalar) {
            eq_ok = false;
        }
    }
    all_ok &= eq_ok;
    checks.push(Check {
        name: "simd_equals_scalar_across_lengths".into(),
        ok: eq_ok,
        detail: format!(
            "{} lengths (0..=4096); worst |Δ| = {:.3e} (tol scales with magnitude)",
            lengths.len(),
            worst_delta
        ),
    });

    // 2. empty + tiny edge cases.
    let edge_ok = sum_of_squares(&[]) == 0.0
        && close(sum_of_squares(&[3.0]), 9.0)
        && close(sum_of_squares(&[1.0, 2.0, 3.0]), 14.0);
    all_ok &= edge_ok;
    checks.push(Check {
        name: "edge_cases_empty_and_tiny".into(),
        ok: edge_ok,
        detail: "Σ[]=0 · Σ[3]²=9 · Σ[1,2,3]²=14".into(),
    });

    // 3. timing + accuracy at scale: a big vector through both paths. Correctness
    //    is judged against an f64 reference — NOT simd-vs-scalar directly, because
    //    at 1e6 terms the two f32 reductions legitimately diverge by their
    //    summation order (the scalar sequential sum accumulates MORE f32 error
    //    than the SIMD 16-lane tree-reduce). So the gate is "the SIMD sum is
    //    accurate vs f64", and the scalar's larger drift is reported as evidence
    //    the SIMD path is, if anything, more accurate.
    let big: Vec<f32> = (0..1_000_000).map(det_val).collect();
    let f64_ref: f64 = big.iter().map(|&v| f64::from(v) * f64::from(v)).sum();
    let t0 = Instant::now();
    let simd_sum = sum_of_squares(&big);
    let simd_us = t0.elapsed().as_micros();
    let t1 = Instant::now();
    let scalar_sum = sum_of_squares_scalar(&big);
    let scalar_us = t1.elapsed().as_micros();
    let denom = f64_ref.abs().max(1.0);
    let simd_rel_err = (f64::from(simd_sum) - f64_ref).abs() / denom;
    let scalar_rel_err = (f64::from(scalar_sum) - f64_ref).abs() / denom;
    let timing_ok = simd_rel_err <= 1e-3; // SIMD sum accurate at 1e6 scale
    all_ok &= timing_ok;
    let speedup = if simd_us > 0 {
        scalar_us as f64 / simd_us as f64
    } else {
        f64::INFINITY
    };
    checks.push(Check {
        name: "timing_and_accuracy_1M_elements".into(),
        ok: timing_ok,
        detail: format!(
            "path={path}: simd {simd_us}µs vs scalar {scalar_us}µs (≈{speedup:.2}× on 1e6 f32); \
             simd rel-err {simd_rel_err:.2e} vs f64 ref (scalar {scalar_rel_err:.2e})"
        ),
    });

    FeatureResult {
        feature: "simd-sum-of-squares",
        label: "AVX-512 · sum_of_squares",
        ok: all_ok,
        path_taken: path.into(),
        duration_us: started.elapsed().as_micros(),
        detail: if all_ok {
            format!("SIMD kernel verified equal to scalar; host path = {path}")
        } else {
            "SIMD/scalar divergence — see checks".into()
        },
        checks,
    }
}

/// The registry of features the lab can self-test. Grows as cards are added
/// (D21-lab Phase 0b: safetensors loader; Phase 0c: cockpit surfaces).
fn run(feature: &str) -> Option<FeatureResult> {
    match feature {
        "simd-sum-of-squares" => Some(selftest_simd_sum_of_squares()),
        _ => None,
    }
}

const FEATURES: &[(&str, &str)] = &[("simd-sum-of-squares", "AVX-512 · sum_of_squares")];

fn print_json(v: &impl Serialize) {
    match serde_json::to_string_pretty(v) {
        Ok(s) => println!("{s}"),
        Err(e) => {
            eprintln!("sovereign-feature-selftest: serialization failed: {e}");
            std::process::exit(1);
        }
    }
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let cmd = args.first().map(String::as_str).unwrap_or("list");

    match cmd {
        "list" => {
            let list: Vec<_> = FEATURES
                .iter()
                .map(|(id, label)| serde_json::json!({ "feature": id, "label": label }))
                .collect();
            print_json(&serde_json::json!({
                "schema": "sovereign-feature-selftest/1",
                "features": list,
            }));
        }
        "run" => {
            let Some(feat) = args.get(1) else {
                eprintln!("usage: sovereign-feature-selftest run <feature> [--json]");
                std::process::exit(2);
            };
            match run(feat) {
                Some(r) => print_json(&r),
                None => {
                    print_json(&serde_json::json!({
                        "error": format!("unknown feature: {feat}"),
                        "known": FEATURES.iter().map(|(id, _)| *id).collect::<Vec<_>>(),
                    }));
                }
            }
        }
        "run-all" | "--self-check" => {
            let results: Vec<FeatureResult> =
                FEATURES.iter().filter_map(|(id, _)| run(id)).collect();
            let all_ok = results.iter().all(|r| r.ok);
            print_json(&serde_json::json!({
                "schema": "sovereign-feature-selftest/1",
                "all_ok": all_ok,
                "results": results,
            }));
        }
        "--help" | "-h" => {
            println!(
                "sovereign-feature-selftest — per-feature live self-tests\n\n\
                 USAGE:\n\
                 \x20   list                      list available features (JSON)\n\
                 \x20   run <feature> [--json]    run one feature's self-test\n\
                 \x20   run-all [--json]          run every feature\n\
                 \x20   --self-check              run-all, exit 0 (CI smoke)"
            );
        }
        other => {
            eprintln!("unknown command: {other} (try: list | run <feature> | run-all)");
            std::process::exit(2);
        }
    }
}
