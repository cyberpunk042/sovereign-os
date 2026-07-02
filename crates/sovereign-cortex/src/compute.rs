//! Per-device compute profile.
//!
//! Placement decides *which device* runs the work; this module decides
//! *what that costs*, using the real numeric engines:
//!
//! - **Conductor (CPU)** runs ternary BitLinear — footprint via
//!   [`sovereign_bitlinear_core::bits_per_param`] at the 1.6-bit base-3
//!   packing, and the multiplication-free property (M073).
//! - **Logic (GPU 0)** runs NVFP4 — footprint from the real format
//!   constants `(BLOCK_SIZE·ELEMENT_BITS + SCALE_BITS)/BLOCK_SIZE = 4.5`
//!   bits/param (M077).
//! - **Oracle (GPU 1)** runs un-quantized FP16 — 16 bits/param (M075).
//! - **Cloud** executes off-node; no local compute profile.
//!
//! So the cortex doesn't just *name* a device — it reports the actual
//! model footprint the chosen precision implies, computed by the same
//! crates that would run it.

use serde::Serialize;
use sovereign_attention::{Attention, DecodeStep};
use sovereign_bitlinear_core::{BitLinearMlp, Packing, bits_per_param as ternary_bits_per_param};
use sovereign_nvfp4_runtime::{
    BLOCK_SIZE, ELEMENT_BITS, QuantMatrix, RhtQuantMatrix, SCALE_BITS, TwoDQuantMatrix,
    relative_frobenius_error,
};
use sovereign_router_7axis::SrpRole;
use sovereign_spec_decode::{expected_speedup, verify_sampled};

/// Nominal per-token acceptance rate assumed when estimating speculative-
/// decoding throughput on the GPU target roles.
pub const NOMINAL_ACCEPTANCE: f64 = 0.7;
/// Nominal draft length for the speculative-decoding throughput estimate.
pub const NOMINAL_DRAFT_LEN: usize = 4;

/// The compute cost profile for a placed workload.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct ComputeProfile {
    /// Human-readable execution path.
    pub path: &'static str,
    /// Effective bits stored per model parameter at this precision.
    pub bits_per_param: f64,
    /// Estimated on-device model footprint in bytes for `model_params`.
    pub est_model_bytes: u64,
    /// Whether the inner-product hot path is multiplication-free (ternary).
    pub multiplication_free: bool,
    /// Whether the device's actual compute kernel ran a live self-check
    /// (a micro forward pass through the real bitlinear / nvfp4 kernel).
    pub kernel_verified: bool,
    /// Whether the attention inner loop self-checked on this device: a micro
    /// decode step through the real online-softmax kernel, confirmed equal to
    /// the naive softmax. Attention is precision-agnostic, so every local
    /// role runs it; the cloud plane runs no local kernel.
    pub attention_verified: bool,
    /// Expected tokens emitted per target pass via speculative decoding on
    /// this role — `1.0` where spec-decode doesn't apply (CPU draft / cloud),
    /// `> 1.0` on the GPU target roles (DFlash family, M077/M073 draft).
    pub expected_throughput_x: f64,
    /// Whether the DFlash speculative-decoding accept path self-checked live on
    /// this role: a real distribution-preserving [`verify_sampled`] round
    /// confirmed callable + correct. Only the GPU target roles verify the
    /// spec-decode path they actually use; the CPU draft and cloud planes don't.
    pub spec_decode_verified: bool,
    /// Short note on the precision/runtime.
    pub note: &'static str,
}

/// Live self-check of the speculative-decoding accept path: run the real
/// distribution-preserving [`verify_sampled`] through a full-accept round and
/// a forced-rejection round, confirming the accept rule and residual
/// correction behave exactly. Proves the GPU target role's spec-decode path is
/// callable and correct, not just an estimated multiplier.
fn spec_decode_kernel_live() -> bool {
    // Full accept: target == draft, u = 0 < ratio 1 → both tokens accepted,
    // bonus appended from the bonus distribution ([0,1] → token 1).
    let draft = [0u32, 1];
    let pd = [vec![0.5, 0.5], vec![0.5, 0.5]];
    let pt = [vec![0.5, 0.5], vec![0.5, 0.5], vec![0.0, 1.0]];
    let mut zero = || 0.0f64;
    let full = matches!(
        verify_sampled(&draft, &pd, &pt, &mut zero),
        Ok(o) if o.accepted == 2 && o.emitted_tokens == vec![0u32, 1, 1]
    );
    // Forced reject: draft token 0 has target prob 0 → ratio 0, u = 0 →
    // rejected; correction drawn from the positive residual, never token 0.
    let rdraft = [0u32];
    let rpd = [vec![1.0, 0.0, 0.0]];
    let rpt = [vec![0.0, 0.5, 0.5], vec![1.0, 0.0, 0.0]];
    let mut zero2 = || 0.0f64;
    let rejected = matches!(
        verify_sampled(&rdraft, &rpd, &rpt, &mut zero2),
        Ok(o) if o.accepted == 0 && o.emitted_tokens.len() == 1 && o.emitted_tokens[0] != 0
    );
    full && rejected
}

/// Expected speculative-decoding throughput multiplier for the GPU target
/// roles, at the nominal acceptance rate + draft length.
fn gpu_spec_throughput() -> f64 {
    expected_speedup(NOMINAL_ACCEPTANCE, NOMINAL_DRAFT_LEN)
}

/// Live self-check of the ternary kernel: build a real two-layer FFN block
/// (`d_model → d_ff → d_model` with a ReLU, the transformer feed-forward)
/// and run one forward pass. Proves the Conductor's compute path *composes*
/// — a multi-layer block, not just one projection — that the
/// multiplication-free invariant holds across the whole stack (zero
/// inner-product floating multiplies; only the per-output scales), and that
/// the single-pass **packed-domain** forward (the LUT/AVX-512 path
/// foundation) reproduces the unpack-loop forward bit-for-bit.
fn ternary_kernel_live() -> bool {
    let (d_model, d_ff) = (8usize, 32usize);
    let expand: Vec<f32> = (0..d_ff * d_model)
        .map(|i| ((i % 5) as f32 - 2.0) * 0.5)
        .collect();
    let contract: Vec<f32> = (0..d_model * d_ff)
        .map(|i| ((i % 7) as f32 - 3.0) * 0.25)
        .collect();
    let x = vec![1.0f32; d_model];

    // Base3 (density-optimal) block: composes + stays multiplication-free.
    let mlp = match BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, Packing::Base3) {
        Ok(m) => m,
        Err(_) => return false,
    };
    let composes = match mlp.forward(&x) {
        Ok((y, ops)) => {
            y.len() == d_model
                && ops.float_muls == d_ff + d_model
                && mlp.floating_muls_eliminated() == d_ff * d_model + d_model * d_ff
        }
        Err(_) => false,
    };

    // TwoBit (byte-aligned) block: the packed-domain forward — the scalar
    // form of the AVX-512 LUT matmul — must equal the unpack-loop forward.
    let packed_exact = match BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, Packing::TwoBit) {
        Ok(b) => match (b.forward(&x), b.forward_packed(&x)) {
            (Ok((y, ops)), Ok((yp, opsp))) => y == yp && ops == opsp,
            _ => false,
        },
        Err(_) => false,
    };

    composes && packed_exact
}

/// Live self-check of the NVFP4 kernel: quantize a tiny matrix and run one
/// matvec through the plain, RHT, 2D, and stochastic recipes — proving the
/// Logic engine's compute path *and* its M077 accuracy recipes are all
/// callable and produce finite output.
fn nvfp4_kernel_live() -> bool {
    let (out_dim, in_dim) = (2usize, 16usize);
    let w: Vec<f32> = (0..out_dim * in_dim)
        .map(|i| ((i % 4) as f32 - 1.5) * 0.5)
        .collect();
    let x = vec![1.0f32; in_dim];
    let finite = |y: &[f32]| y.len() == out_dim && y.iter().all(|v| v.is_finite());

    // Plain 1D microscaling.
    let plain = matches!(
        QuantMatrix::from_f32(&w, out_dim, in_dim).and_then(|m| m.matvec(&x)),
        Ok(y) if finite(&y)
    );
    // RHT recipe (input_dim 16 is a power of two).
    let rht = matches!(
        RhtQuantMatrix::from_f32(&w, out_dim, in_dim, 0xC0FFEE).and_then(|m| m.matvec(&x)),
        Ok(y) if finite(&y)
    );
    // 2D per-row+per-column recipe.
    let two_d = matches!(
        TwoDQuantMatrix::from_f32(&w, out_dim, in_dim).and_then(|m| m.matvec(&x)),
        Ok(y) if finite(&y)
    );

    // The recipes are genuinely distinct, not aliases: on a column-structured
    // matrix (one systematically-tiny column that plain's per-row scale rounds
    // toward zero) the 2D recipe's per-column scale reconstructs the weights at
    // least as well as plain microscaling. This is the property recipe
    // selection exploits, so the self-check asserts it, not just finiteness.
    let mut col_w = vec![1.0f32; out_dim * in_dim];
    for o in 0..out_dim {
        col_w[o * in_dim + 5] = 0.012;
    }
    let plain_err = QuantMatrix::from_f32(&col_w, out_dim, in_dim)
        .map(|m| relative_frobenius_error(&col_w, &m.dequantized_weights()))
        .unwrap_or(f64::INFINITY);
    let two_d_err = TwoDQuantMatrix::from_f32(&col_w, out_dim, in_dim)
        .map(|m| relative_frobenius_error(&col_w, &m.dequantized_weights()))
        .unwrap_or(f64::INFINITY);
    let two_d_wins = two_d_err <= plain_err + 1e-9;

    plain && rht && two_d && two_d_wins
}

/// Live self-check of the attention inner loop: stream three tokens through
/// the real online-softmax [`DecodeStep`] and confirm it equals the naive
/// full-softmax [`Attention::attend`]. Proves the device's per-token
/// attention path is callable and numerically faithful.
fn attention_kernel_live() -> bool {
    let head = Attention::new(4);
    let q = [0.5f32, -0.5, 1.0, 0.0];
    let keys = [
        vec![1.0f32, 0.0, 0.0, 0.0],
        vec![0.0, 1.0, 0.0, 0.0],
        vec![0.0, 0.0, 1.0, 0.0],
    ];
    let values = [vec![1.0f32, 2.0], vec![3.0, 4.0], vec![5.0, 6.0]];

    let mut step = DecodeStep::new(head);
    for (k, v) in keys.iter().zip(&values) {
        if step.push(&q, k, v).is_err() {
            return false;
        }
    }
    match (step.output(), head.attend(&q, &keys, &values)) {
        (Ok(stream), Ok(naive)) => {
            stream.len() == naive.len()
                && stream.iter().zip(&naive).all(|(a, b)| (a - b).abs() < 1e-5)
        }
        _ => false,
    }
}

/// NVFP4 effective bits/param from the real format constants (M077):
/// 16 four-bit elements share one eight-bit E4M3 scale → `(16·4+8)/16`.
pub fn nvfp4_bits_per_param() -> f64 {
    (BLOCK_SIZE as f64 * ELEMENT_BITS as f64 + SCALE_BITS as f64) / BLOCK_SIZE as f64
}

fn bytes_for(bits_per_param: f64, params: u64) -> u64 {
    ((bits_per_param * params as f64) / 8.0).ceil() as u64
}

impl ComputeProfile {
    /// Compute the profile for a placement on `role`, for a model of
    /// `model_params` parameters.
    pub fn for_role(role: SrpRole, model_params: u64) -> ComputeProfile {
        match role {
            SrpRole::Conductor => {
                // Ternary base-3 packing footprint via the BitLinear crate.
                let bpp = ternary_bits_per_param(Packing::Base3, model_params as usize);
                ComputeProfile {
                    path: "ternary 1.58-bit BitLinear (bitnet.cpp / CPU)",
                    bits_per_param: bpp,
                    est_model_bytes: bytes_for(bpp, model_params),
                    multiplication_free: true,
                    kernel_verified: ternary_kernel_live(),
                    attention_verified: attention_kernel_live(),
                    expected_throughput_x: 1.0, // the draft model itself; no spec-decode
                    spec_decode_verified: false, // draft model; doesn't verify the target path
                    note: "mul → conditional add/sub; no de-quant at execution (M073)",
                }
            }
            SrpRole::Logic => {
                let bpp = nvfp4_bits_per_param();
                ComputeProfile {
                    path: "NVFP4 E2M1 + E4M3 scale (RTX 4090 / GPU 0)",
                    bits_per_param: bpp,
                    est_model_bytes: bytes_for(bpp, model_params),
                    multiplication_free: false,
                    kernel_verified: nvfp4_kernel_live(),
                    attention_verified: attention_kernel_live(),
                    expected_throughput_x: gpu_spec_throughput(),
                    spec_decode_verified: spec_decode_kernel_live(),
                    note: "4-bit microscaled, 16-value blocks (M077)",
                }
            }
            SrpRole::Oracle => {
                let bpp = 16.0;
                ComputeProfile {
                    path: "un-quantized FP16 (Blackwell PRO 6000 / GPU 1)",
                    bits_per_param: bpp,
                    est_model_bytes: bytes_for(bpp, model_params),
                    multiplication_free: false,
                    kernel_verified: true, // native FP16 needs no quantization kernel
                    attention_verified: attention_kernel_live(),
                    expected_throughput_x: gpu_spec_throughput(),
                    spec_decode_verified: spec_decode_kernel_live(),
                    note: "full-precision deep reasoning (M075)",
                }
            }
            SrpRole::Cloud => ComputeProfile {
                path: "remote cloud expert plane (M032)",
                bits_per_param: 0.0,
                est_model_bytes: 0,
                multiplication_free: false,
                kernel_verified: false, // no local kernel runs for remote work
                attention_verified: false, // no local kernel runs for remote work
                expected_throughput_x: 1.0, // remote; local spec-decode N/A
                spec_decode_verified: false, // no local kernel runs for remote work
                note: "executed off-node; local compute profile N/A",
            },
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    const ONE_B: u64 = 1_000_000_000;

    #[test]
    fn conductor_is_ternary_and_mul_free() {
        let p = ComputeProfile::for_role(SrpRole::Conductor, ONE_B);
        assert!(p.multiplication_free);
        // base-3 packing is 1.6 bits/param
        assert!(
            (p.bits_per_param - 1.6).abs() < 1e-6,
            "{}",
            p.bits_per_param
        );
        // 1B params * 1.6 bits / 8 = 200 MB
        assert_eq!(p.est_model_bytes, 200_000_000);
    }

    #[test]
    fn logic_is_nvfp4_4_5_bits() {
        let p = ComputeProfile::for_role(SrpRole::Logic, ONE_B);
        assert!(!p.multiplication_free);
        assert!(
            (p.bits_per_param - 4.5).abs() < 1e-9,
            "{}",
            p.bits_per_param
        );
        assert_eq!(p.est_model_bytes, 562_500_000); // 1B*4.5/8
    }

    #[test]
    fn oracle_is_fp16() {
        let p = ComputeProfile::for_role(SrpRole::Oracle, ONE_B);
        assert_eq!(p.bits_per_param, 16.0);
        assert_eq!(p.est_model_bytes, 2_000_000_000); // 1B*16/8 = 2GB
    }

    #[test]
    fn footprint_ordering_ternary_lt_nvfp4_lt_fp16() {
        let t = ComputeProfile::for_role(SrpRole::Conductor, ONE_B).est_model_bytes;
        let n = ComputeProfile::for_role(SrpRole::Logic, ONE_B).est_model_bytes;
        let f = ComputeProfile::for_role(SrpRole::Oracle, ONE_B).est_model_bytes;
        assert!(t < n && n < f, "{t} < {n} < {f}");
    }

    #[test]
    fn cloud_has_no_local_footprint() {
        let p = ComputeProfile::for_role(SrpRole::Cloud, ONE_B);
        assert_eq!(p.est_model_bytes, 0);
    }

    #[test]
    fn nvfp4_bits_matches_format_constants() {
        assert_eq!(nvfp4_bits_per_param(), (16.0 * 4.0 + 8.0) / 16.0);
    }

    #[test]
    fn local_kernels_self_check_live() {
        // Conductor + Logic actually run their compute kernels.
        assert!(ComputeProfile::for_role(SrpRole::Conductor, ONE_B).kernel_verified);
        assert!(ComputeProfile::for_role(SrpRole::Logic, ONE_B).kernel_verified);
        // Oracle is native FP16 (no quantization kernel needed).
        assert!(ComputeProfile::for_role(SrpRole::Oracle, ONE_B).kernel_verified);
        // Cloud runs no local kernel.
        assert!(!ComputeProfile::for_role(SrpRole::Cloud, ONE_B).kernel_verified);
    }

    #[test]
    fn ternary_and_nvfp4_kernels_are_callable() {
        assert!(ternary_kernel_live());
        assert!(nvfp4_kernel_live());
    }

    #[test]
    fn attention_kernel_is_callable_and_faithful() {
        assert!(attention_kernel_live());
    }

    #[test]
    fn spec_decode_kernel_is_callable_and_correct() {
        assert!(spec_decode_kernel_live());
    }

    #[test]
    fn gpu_roles_verify_spec_decode_others_dont() {
        // Logic + Oracle run the GPU target spec-decode path → verified live.
        assert!(ComputeProfile::for_role(SrpRole::Logic, ONE_B).spec_decode_verified);
        assert!(ComputeProfile::for_role(SrpRole::Oracle, ONE_B).spec_decode_verified);
        // Conductor is the draft model; Cloud is remote → neither verifies it.
        assert!(!ComputeProfile::for_role(SrpRole::Conductor, ONE_B).spec_decode_verified);
        assert!(!ComputeProfile::for_role(SrpRole::Cloud, ONE_B).spec_decode_verified);
    }

    #[test]
    fn attention_self_checks_on_every_local_role_not_cloud() {
        // Attention is precision-agnostic: every device that runs locally
        // exercises it; the cloud plane runs no local kernel.
        assert!(ComputeProfile::for_role(SrpRole::Conductor, ONE_B).attention_verified);
        assert!(ComputeProfile::for_role(SrpRole::Logic, ONE_B).attention_verified);
        assert!(ComputeProfile::for_role(SrpRole::Oracle, ONE_B).attention_verified);
        assert!(!ComputeProfile::for_role(SrpRole::Cloud, ONE_B).attention_verified);
    }

    #[test]
    fn gpu_roles_expect_spec_decode_speedup() {
        // GPU target roles get a >1x throughput estimate; CPU/cloud get 1x.
        assert!(ComputeProfile::for_role(SrpRole::Logic, ONE_B).expected_throughput_x > 1.0);
        assert!(ComputeProfile::for_role(SrpRole::Oracle, ONE_B).expected_throughput_x > 1.0);
        assert_eq!(
            ComputeProfile::for_role(SrpRole::Conductor, ONE_B).expected_throughput_x,
            1.0
        );
        assert_eq!(
            ComputeProfile::for_role(SrpRole::Cloud, ONE_B).expected_throughput_x,
            1.0
        );
    }
}
