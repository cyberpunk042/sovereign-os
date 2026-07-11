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
    let lengths = [
        0usize, 1, 7, 15, 16, 17, 31, 32, 33, 64, 100, 257, 1000, 4096,
    ];
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

/// Build a minimal safetensors byte buffer: `[8-byte LE header len][JSON header]
/// [tensor data]`. Each tensor is (name, dtype-string, shape, f32 values). F32 is
/// written little-endian; BF16 as the upper 16 bits of each f32; a dtype string
/// the loader doesn't decode (e.g. "I64") is written as zero-filled bytes so the
/// unsupported-dtype path can be exercised.
fn build_safetensors(tensors: &[(&str, &str, Vec<usize>, Vec<f32>)]) -> Vec<u8> {
    let mut data = Vec::new();
    let mut header = serde_json::Map::new();
    for (name, dtype, shape, vals) in tensors {
        let start = data.len();
        match *dtype {
            "F32" => {
                for &v in vals {
                    data.extend_from_slice(&v.to_le_bytes());
                }
            }
            "BF16" => {
                for &v in vals {
                    let bf16 = (v.to_bits() >> 16) as u16;
                    data.extend_from_slice(&bf16.to_le_bytes());
                }
            }
            _ => {
                // an undecodable dtype: reserve 8 bytes per element
                data.extend(std::iter::repeat_n(0u8, vals.len().max(1) * 8));
            }
        }
        let end = data.len();
        header.insert(
            (*name).to_string(),
            serde_json::json!({ "dtype": dtype, "shape": shape, "data_offsets": [start, end] }),
        );
    }
    let header_bytes = serde_json::to_vec(&header).unwrap_or_default();
    let mut out = Vec::new();
    out.extend_from_slice(&(header_bytes.len() as u64).to_le_bytes());
    out.extend_from_slice(&header_bytes);
    out.extend_from_slice(&data);
    out
}

/// Live self-test of the safetensors loader (`sovereign-safetensors-loader`):
/// exercises the real parser + dequantizer + config reader + error taxonomy on
/// a hand-built buffer — no model file, no network. (A full model-forward decode
/// self-test using the loader's GQA fixture is a Phase-0c follow-up.)
fn selftest_safetensors_loader() -> FeatureResult {
    use sovereign_safetensors_loader::{Config, LoaderError, SafeTensors};

    let started = Instant::now();
    let mut checks = Vec::new();
    let mut all_ok = true;

    // 1. parse a valid buffer + dequantize F32 exactly and BF16 within tolerance.
    let buf = build_safetensors(&[
        ("w", "F32", vec![4], vec![1.0, 2.0, 3.0, 4.0]),
        ("wb", "BF16", vec![2], vec![1.5, -2.0]), // exact in bf16
    ]);
    let parse_ok = match SafeTensors::parse(&buf) {
        Ok(st) => {
            let mut names = st.names();
            names.sort_unstable();
            let names_ok = names == ["w", "wb"];
            let f32_ok = st
                .tensor_f32("w")
                .map(|v| v == [1.0, 2.0, 3.0, 4.0])
                .unwrap_or(false);
            let bf16_ok = st
                .tensor_f32("wb")
                .map(|v| v.len() == 2 && (v[0] - 1.5).abs() < 1e-2 && (v[1] + 2.0).abs() < 1e-2)
                .unwrap_or(false);
            checks.push(Check {
                name: "parse_and_names".into(),
                ok: names_ok,
                detail: format!("names = {names:?}"),
            });
            checks.push(Check {
                name: "dequant_f32_exact".into(),
                ok: f32_ok,
                detail: "tensor_f32(\"w\") == [1,2,3,4]".into(),
            });
            checks.push(Check {
                name: "dequant_bf16".into(),
                ok: bf16_ok,
                detail: "tensor_f32(\"wb\") ≈ [1.5, -2.0]".into(),
            });
            names_ok && f32_ok && bf16_ok
        }
        Err(e) => {
            checks.push(Check {
                name: "parse_valid_buffer".into(),
                ok: false,
                detail: format!("parse failed: {e}"),
            });
            false
        }
    };
    all_ok &= parse_ok;

    // 2. Config::from_json — HF field names + derived GQA kv-heads / head_dim.
    let cfg_json = br#"{"hidden_size":8,"num_hidden_layers":2,"num_attention_heads":4,
        "num_key_value_heads":2,"vocab_size":32,"intermediate_size":16,"tie_word_embeddings":true}"#;
    let cfg_ok = match Config::from_json(cfg_json) {
        Ok(c) => {
            let ok = c.model_dim == 8
                && c.n_heads == 4
                && c.kv_heads() == 2
                && c.head_dim() == 2
                && c.tied;
            checks.push(Check {
                name: "config_from_json".into(),
                ok,
                detail: format!(
                    "model_dim={} n_heads={} kv_heads={} head_dim={} tied={}",
                    c.model_dim,
                    c.n_heads,
                    c.kv_heads(),
                    c.head_dim(),
                    c.tied
                ),
            });
            ok
        }
        Err(e) => {
            checks.push(Check {
                name: "config_from_json".into(),
                ok: false,
                detail: format!("config parse failed: {e}"),
            });
            false
        }
    };
    all_ok &= cfg_ok;

    // 3. error taxonomy — a missing tensor, an unsupported dtype, a truncated
    //    buffer each raise the RIGHT LoaderError (negative-path live testing).
    let missing_ok = matches!(
        SafeTensors::parse(&buf).and_then(|st| st.tensor_f32("nope")),
        Err(LoaderError::MissingTensor(_))
    );
    checks.push(Check {
        name: "error_missing_tensor".into(),
        ok: missing_ok,
        detail: "tensor_f32(unknown) → MissingTensor".into(),
    });

    let ubuf = build_safetensors(&[("x", "I64", vec![1], vec![0.0])]);
    let dtype_ok = matches!(
        SafeTensors::parse(&ubuf).and_then(|st| st.tensor_f32("x")),
        Err(LoaderError::UnsupportedDtype { .. })
    );
    checks.push(Check {
        name: "error_unsupported_dtype".into(),
        ok: dtype_ok,
        detail: "dtype I64 → UnsupportedDtype".into(),
    });

    let truncated = &buf[..6.min(buf.len())]; // shorter than the 8-byte header-len prefix
    let trunc_ok = matches!(
        SafeTensors::parse(truncated),
        Err(LoaderError::Truncated(_)) | Err(LoaderError::Json(_))
    );
    checks.push(Check {
        name: "error_truncated".into(),
        ok: trunc_ok,
        detail: "6-byte buffer → Truncated/Json".into(),
    });

    all_ok &= missing_ok && dtype_ok && trunc_ok;

    FeatureResult {
        feature: "safetensors-loader",
        label: "safetensors loader",
        ok: all_ok,
        path_taken: "parse + dequant + config + errors".into(),
        duration_us: started.elapsed().as_micros(),
        detail: if all_ok {
            "loader parses, dequantizes F32/BF16, reads config, and raises the right errors".into()
        } else {
            "loader self-test failed — see checks".into()
        },
        checks,
    }
}

/// The registry of features the lab can self-test. Grows as cards are added
/// (Phase 0c: cockpit surfaces + a full model-forward decode).
fn run(feature: &str) -> Option<FeatureResult> {
    match feature {
        "simd-sum-of-squares" => Some(selftest_simd_sum_of_squares()),
        "safetensors-loader" => Some(selftest_safetensors_loader()),
        _ => None,
    }
}

const FEATURES: &[(&str, &str)] = &[
    ("simd-sum-of-squares", "AVX-512 · sum_of_squares"),
    ("safetensors-loader", "safetensors loader"),
];

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
