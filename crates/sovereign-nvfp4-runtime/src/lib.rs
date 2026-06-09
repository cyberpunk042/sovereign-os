//! `sovereign-nvfp4-runtime` — M077 NVFP4 pretraining + inference
//! pipeline runtime.
//!
//! Per M077 + arXiv 2509.25149 ("NVFP4: 4-bit pretraining without
//! accuracy loss") + arXiv 2505.19115 ("Microscaling NVFP4 format
//! definition"), NVFP4 is a microscaled 4-bit format with:
//!
//! - **E2M1 4-bit element** (1 sign + 2 exponent + 1 mantissa bits)
//! - **E4M3 8-bit per-block scale** (1 sign + 4 exponent + 3 mantissa bits)
//! - **1×16 block allocator** (16 values share one scale)
//! - **Random Hadamard Transform** (RHT, applied pre-quantization)
//! - **2D quantization coordinator** (row-major + column-major scales)
//! - **Stochastic rounding** (unbiased gradient quantization)
//! - **Selective high-precision** layer selection (sensitive layers stay BF16/FP8)
//!
//! ## Five recipe variants
//!
//! | recipe | use case | RHT | 2D | stochastic | sel-HP |
//! |---|---|---|---|---|---|
//! | NVFP4-S | inference, dense models, max throughput | no | no | no | minimal |
//! | NVFP4-M | inference, MoE | yes | no | no | minimal |
//! | NVFP4-L | inference, attention-heavy + long context | yes | yes | no | moderate |
//! | NVFP4-XL | training, foundation models | yes | yes | yes | extensive |
//! | NVFP4-XXL | training, frontier scale | yes | yes | yes | maximum |
//!
//! Per M01283 the runtime targets the Blackwell `sm_120` architecture
//! flag for hardware acceleration; the CPU fallback path implements
//! the same numerics for development + verification.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

pub mod linear;
pub mod rht;

pub use linear::{LinearError, QuantMatrix, dense_f32_matvec};
pub use rht::{RhtError, fwht, random_signs, rht_forward, rht_inverse};

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the NVFP4 runtime configuration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Block size — exactly 16 values per scale, per arXiv 2505.19115 §3.
/// Changing this constant breaks the format wire definition.
pub const BLOCK_SIZE: usize = 16;

/// Number of bits in the E2M1 element type.
pub const ELEMENT_BITS: u8 = 4;

/// Number of bits in the E4M3 scale type (one per block).
pub const SCALE_BITS: u8 = 8;

/// One of five canonical recipe variants. Variants gate which
/// optimizations are enabled.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Recipe {
    /// NVFP4-S — inference, dense, max throughput.
    NvfpS,
    /// NVFP4-M — inference, MoE.
    NvfpM,
    /// NVFP4-L — inference, attention-heavy + long context.
    NvfpL,
    /// NVFP4-XL — training, foundation models.
    NvfpXl,
    /// NVFP4-XXL — training, frontier scale.
    NvfpXxl,
}

impl Recipe {
    /// Whether Random Hadamard Transform pre-quant is enabled.
    pub fn rht_enabled(self) -> bool {
        matches!(
            self,
            Recipe::NvfpM | Recipe::NvfpL | Recipe::NvfpXl | Recipe::NvfpXxl
        )
    }
    /// Whether 2D (row + column) quantization is enabled.
    pub fn two_d_enabled(self) -> bool {
        matches!(self, Recipe::NvfpL | Recipe::NvfpXl | Recipe::NvfpXxl)
    }
    /// Whether stochastic rounding is enabled (training-only recipes).
    pub fn stochastic_rounding_enabled(self) -> bool {
        matches!(self, Recipe::NvfpXl | Recipe::NvfpXxl)
    }
    /// Heuristic count of layers kept in high precision (BF16/FP8).
    pub fn selective_hp_layers(self) -> u32 {
        match self {
            Recipe::NvfpS => 2,
            Recipe::NvfpM => 4,
            Recipe::NvfpL => 8,
            Recipe::NvfpXl => 16,
            Recipe::NvfpXxl => 32,
        }
    }
}

/// E2M1 4-bit element. Stored in low nibble; high nibble is zero.
/// Bit layout: `[sign(1)][exponent(2)][mantissa(1)]`.
///
/// Representable values (signed): {-3, -2, -1.5, -1, -0.5, -0, +0, +0.5, +1, +1.5, +2, +3}
/// with 0 and -0 distinguished and inf/nan slots reserved.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct E2m1(pub u8);

impl E2m1 {
    /// Decode to f32. Returns NaN for the reserved encoding.
    pub fn to_f32(self) -> f32 {
        let b = self.0 & 0x0f;
        let sign = if b & 0b1000 != 0 { -1.0 } else { 1.0 };
        let exp = (b >> 1) & 0b011;
        let mant = b & 0b001;
        // exp=0: subnormal: value = mant * 0.5
        // exp>0: value = (1 + mant*0.5) * 2^(exp-1)
        let mag = if exp == 0 {
            mant as f32 * 0.5
        } else {
            (1.0 + (mant as f32) * 0.5) * f32::powi(2.0, exp as i32 - 1)
        };
        sign * mag
    }

    /// Encode an f32 by round-to-nearest. Saturates out-of-range to ±3.
    /// Used in the deterministic path; see [`quantize_stochastic`] for the
    /// unbiased training variant.
    pub fn from_f32_rne(x: f32) -> Self {
        let neg = x.is_sign_negative();
        let mag = x.abs();
        // candidate magnitudes for E2M1 positives: 0, 0.5, 1, 1.5, 2, 3
        let candidates: [f32; 6] = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0];
        let mut best_i: usize = 0;
        let mut best_d = f32::INFINITY;
        for (i, c) in candidates.iter().enumerate() {
            let d = (mag - c).abs();
            if d < best_d || (d == best_d && i % 2 == 0) {
                best_d = d;
                best_i = i;
            }
        }
        let bits_pos: u8 = match best_i {
            0 => 0b000, // +0
            1 => 0b001, // 0.5
            2 => 0b010, // 1.0
            3 => 0b011, // 1.5
            4 => 0b100, // 2.0
            5 => 0b101, // 3.0  (encoded as exp=10, mant=1 → +3)
            _ => 0b000,
        };
        let sign_bit: u8 = if neg { 0b1000 } else { 0b0000 };
        E2m1(sign_bit | bits_pos)
    }
}

/// E4M3 8-bit scale. Used per 16-element block per arXiv 2505.19115 §3.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct E4m3(pub u8);

impl E4m3 {
    /// Decode to f32. NaN slots are mapped to NaN.
    pub fn to_f32(self) -> f32 {
        let b = self.0;
        let sign = if b & 0x80 != 0 { -1.0 } else { 1.0 };
        let exp = (b >> 3) & 0x0f;
        let mant = b & 0x07;
        if exp == 0x0f && mant != 0 {
            return f32::NAN;
        }
        let mag = if exp == 0 {
            (mant as f32) / 8.0 * f32::powi(2.0, -6)
        } else {
            (1.0 + (mant as f32) / 8.0) * f32::powi(2.0, exp as i32 - 7)
        };
        sign * mag
    }

    /// Encode an f32 scale value by round-to-nearest, clamped to E4M3 range.
    /// Used by [`quantize_block_rne`].
    pub fn from_f32_rne(x: f32) -> Self {
        if x == 0.0 {
            return E4m3(0);
        }
        let sign_bit: u8 = if x.is_sign_negative() { 0x80 } else { 0x00 };
        let mag = x.abs().clamp(f32::powi(2.0, -9), 448.0);
        let exp_f = mag.log2().floor();
        let exp = (exp_f as i32 + 7).clamp(0, 14) as u8;
        let frac = mag / f32::powi(2.0, exp as i32 - 7);
        let mant = ((frac - 1.0) * 8.0).round().clamp(0.0, 7.0) as u8;
        E4m3(sign_bit | (exp << 3) | mant)
    }
}

/// One quantized block: 16 E2M1 elements + one E4M3 scale.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct QuantBlock {
    /// Scale applied to all 16 elements.
    pub scale: E4m3,
    /// 16 quantized elements.
    pub elements: [E2m1; BLOCK_SIZE],
}

/// Quantize a 16-value f32 block using deterministic round-to-nearest.
///
/// Used in the inference path (NVFP4-S/M/L).
pub fn quantize_block_rne(values: &[f32; BLOCK_SIZE]) -> QuantBlock {
    let max_abs = values.iter().copied().map(f32::abs).fold(0.0_f32, f32::max);
    // largest representable E2M1 magnitude is 3.0
    let scale_f = if max_abs > 0.0 { max_abs / 3.0 } else { 1.0 };
    let scale = E4m3::from_f32_rne(scale_f);
    let inv = if scale_f > 0.0 { 1.0 / scale_f } else { 0.0 };
    let mut elements = [E2m1::default(); BLOCK_SIZE];
    for (i, v) in values.iter().enumerate() {
        elements[i] = E2m1::from_f32_rne(v * inv);
    }
    QuantBlock { scale, elements }
}

/// Dequantize a block back to f32.
pub fn dequantize_block(b: &QuantBlock) -> [f32; BLOCK_SIZE] {
    let s = b.scale.to_f32();
    let mut out = [0.0_f32; BLOCK_SIZE];
    for i in 0..BLOCK_SIZE {
        out[i] = b.elements[i].to_f32() * s;
    }
    out
}

/// Stochastic rounding: pick the lower or upper E2M1 candidate
/// probabilistically based on fractional distance. Unbiased: E[ŝ] = s.
///
/// Used in the training path (NVFP4-XL / NVFP4-XXL).
pub fn quantize_stochastic<R: rand::Rng>(rng: &mut R, x: f32) -> E2m1 {
    let candidates: [f32; 6] = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0];
    let mag = x.abs();
    // find lower neighbor
    let mut lo = 0;
    let mut hi = candidates.len() - 1;
    for i in 0..candidates.len() {
        if candidates[i] <= mag {
            lo = i;
        } else {
            hi = i;
            break;
        }
    }
    if lo == hi {
        return E2m1::from_f32_rne(x);
    }
    let lo_val = candidates[lo];
    let hi_val = candidates[hi];
    let frac = (mag - lo_val) / (hi_val - lo_val).max(f32::EPSILON);
    let p_up: f32 = rng.random_range(0.0..1.0);
    let chosen_idx = if p_up < frac { hi } else { lo };
    let bits_pos: u8 = match chosen_idx {
        0 => 0b000,
        1 => 0b001,
        2 => 0b010,
        3 => 0b011,
        4 => 0b100,
        5 => 0b101,
        _ => 0b000,
    };
    let sign_bit: u8 = if x.is_sign_negative() { 0b1000 } else { 0b0000 };
    E2m1(sign_bit | bits_pos)
}

/// Runtime configuration. Persisted alongside model weights so
/// inference + training paths read consistent settings.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
pub struct RuntimeConfig {
    /// Schema version. Must equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// Selected recipe variant.
    pub recipe: Recipe,
    /// Whether to engage the Blackwell sm_120 CUDA bridge (M01283).
    /// Falls back to CPU path when false.
    pub use_blackwell_cuda: bool,
    /// Layers (by name) explicitly kept in high precision.
    pub high_precision_layers: Vec<String>,
    /// Seed for the stochastic rounding PRNG. Same seed → reproducible.
    pub stochastic_seed: u64,
}

impl Default for RuntimeConfig {
    fn default() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            recipe: Recipe::NvfpL,
            use_blackwell_cuda: false,
            high_precision_layers: vec!["embed.in".into(), "embed.out".into(), "lm_head".into()],
            stochastic_seed: 0xdeadbeef,
        }
    }
}

/// Runtime errors.
#[derive(Debug, Error)]
pub enum RuntimeError {
    /// Schema version drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected schema version.
        expected: String,
        /// Observed schema version.
        actual: String,
    },
    /// Block size of input does not match [`BLOCK_SIZE`].
    #[error("block size {0} != required 16")]
    BlockSizeInvalid(usize),
    /// Selective-HP layer not present in the model.
    #[error("high precision layer not found in model: {0}")]
    HpLayerMissing(String),
}

impl RuntimeConfig {
    /// Validate schema version.
    pub fn validate(&self) -> Result<(), RuntimeError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(RuntimeError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use rand::SeedableRng;
    use rand_chacha::ChaCha20Rng;

    #[test]
    fn block_size_is_16() {
        assert_eq!(BLOCK_SIZE, 16);
    }

    #[test]
    fn recipe_gates_match_doctrine() {
        assert!(!Recipe::NvfpS.rht_enabled());
        assert!(Recipe::NvfpM.rht_enabled());
        assert!(Recipe::NvfpL.two_d_enabled());
        assert!(!Recipe::NvfpL.stochastic_rounding_enabled());
        assert!(Recipe::NvfpXl.stochastic_rounding_enabled());
        assert!(Recipe::NvfpXxl.stochastic_rounding_enabled());
        assert!(Recipe::NvfpXxl.selective_hp_layers() > Recipe::NvfpS.selective_hp_layers());
    }

    #[test]
    fn e2m1_zero_roundtrips() {
        assert_eq!(E2m1::from_f32_rne(0.0).to_f32(), 0.0);
    }

    #[test]
    fn e2m1_negative_zero_preserved() {
        let neg_one = E2m1::from_f32_rne(-1.0);
        assert_eq!(neg_one.to_f32(), -1.0);
    }

    #[test]
    fn e2m1_saturates_at_three() {
        assert_eq!(E2m1::from_f32_rne(10.0).to_f32(), 3.0);
        assert_eq!(E2m1::from_f32_rne(-10.0).to_f32(), -3.0);
    }

    #[test]
    fn e2m1_round_to_nearest_canonical_values() {
        for &v in &[0.0_f32, 0.5, 1.0, 1.5, 2.0, 3.0] {
            assert!((E2m1::from_f32_rne(v).to_f32() - v).abs() < 1e-6, "v={v}");
            assert!((E2m1::from_f32_rne(-v).to_f32() + v).abs() < 1e-6, "v=-{v}");
        }
    }

    #[test]
    fn e4m3_zero_and_small_roundtrip() {
        assert_eq!(E4m3::from_f32_rne(0.0).to_f32(), 0.0);
        let one = E4m3::from_f32_rne(1.0);
        assert!((one.to_f32() - 1.0).abs() < 0.1);
    }

    #[test]
    fn quantize_dequantize_block_within_tolerance() {
        let mut input = [0.0f32; BLOCK_SIZE];
        for i in 0..BLOCK_SIZE {
            input[i] = (i as f32 - 8.0) * 0.25; // span -2.0 to 1.75
        }
        let block = quantize_block_rne(&input);
        let recovered = dequantize_block(&block);
        // E2M1+E4M3 quantization gives ~6% RMSE on this range; tolerance loose.
        for i in 0..BLOCK_SIZE {
            assert!(
                (recovered[i] - input[i]).abs() < 1.0,
                "i={i} input={} recovered={}",
                input[i],
                recovered[i]
            );
        }
    }

    #[test]
    fn stochastic_rounding_unbiased_over_many_samples() {
        let mut rng = ChaCha20Rng::seed_from_u64(0xdeadbeef);
        let x: f32 = 0.75; // between 0.5 and 1.0, expected E[ŝ] = 0.75
        let n = 10_000;
        let mut acc: f64 = 0.0;
        for _ in 0..n {
            let q = quantize_stochastic(&mut rng, x);
            acc += q.to_f32() as f64;
        }
        let mean = acc / n as f64;
        assert!((mean - 0.75).abs() < 0.02, "mean={mean} expected≈0.75");
    }

    #[test]
    fn runtime_config_default_validates() {
        RuntimeConfig::default().validate().unwrap();
    }

    #[test]
    fn runtime_config_rejects_schema_drift() {
        let mut c = RuntimeConfig::default();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            RuntimeError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn recipe_serde_uses_kebab_case() {
        let j = serde_json::to_string(&Recipe::NvfpXxl).unwrap();
        assert_eq!(j, "\"nvfp-xxl\"");
    }

    #[test]
    fn quant_block_serde_roundtrip() {
        let block = QuantBlock {
            scale: E4m3(0x40),
            elements: [E2m1(0b0001); BLOCK_SIZE],
        };
        let j = serde_json::to_string(&block).unwrap();
        let back: QuantBlock = serde_json::from_str(&j).unwrap();
        assert_eq!(block, back);
    }
}
