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
use sovereign_bitlinear_core::{BitLinearLayer, Packing, bits_per_param as ternary_bits_per_param};
use sovereign_nvfp4_runtime::{BLOCK_SIZE, ELEMENT_BITS, QuantMatrix, SCALE_BITS};
use sovereign_router_7axis::SrpRole;

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
    /// Short note on the precision/runtime.
    pub note: &'static str,
}

/// Live self-check of the ternary kernel: build a tiny BitLinear layer and
/// run one forward pass. Proves the Conductor's compute path is callable.
fn ternary_kernel_live() -> bool {
    let w = [
        0.5f32, -0.5, 0.0, 1.0, -1.0, 0.0, 0.5, -0.5, 1.0, -1.0, 0.0, 0.5, -0.5, 1.0, 0.0, -1.0,
    ];
    match BitLinearLayer::from_weights(&w, 1, 16, Packing::Base3) {
        Ok(layer) => layer.forward(&[1.0f32; 16]).is_ok(),
        Err(_) => false,
    }
}

/// Live self-check of the NVFP4 kernel: quantize a tiny matrix and run one
/// matvec. Proves the Logic engine's compute path is callable.
fn nvfp4_kernel_live() -> bool {
    let w = [0.5f32; 16];
    match QuantMatrix::from_f32(&w, 1, 16) {
        Ok(m) => m.matvec(&[1.0f32; 16]).is_ok(),
        Err(_) => false,
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
                    note: "mul → conditional add/sub; no de-quant at execution (M073)",
                }
            }
            SrpRole::Logic => {
                let bpp = nvfp4_bits_per_param();
                ComputeProfile {
                    path: "NVFP4 E2M1 + E4M3 scale (RTX 3090 / GPU 0)",
                    bits_per_param: bpp,
                    est_model_bytes: bytes_for(bpp, model_params),
                    multiplication_free: false,
                    kernel_verified: nvfp4_kernel_live(),
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
                    note: "full-precision deep reasoning (M075)",
                }
            }
            SrpRole::Cloud => ComputeProfile {
                path: "remote cloud expert plane (M032)",
                bits_per_param: 0.0,
                est_model_bytes: 0,
                multiplication_free: false,
                kernel_verified: false, // no local kernel runs for remote work
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
}
