//! `sovereign-linear` — a precision-generic linear layer.
//!
//! A transformer is mostly `y = W·x` matvecs (the Q/K/V/O projections and the
//! FFN). The dump's whole premise is running those in *low precision* — so a
//! linear layer must be able to execute on the quantization kernels, not just
//! f32. This crate is that one type: a [`Linear`] built from an f32 weight
//! matrix and a chosen [`Precision`], dispatching `forward` to the matching
//! backend:
//!
//! * [`Precision::F32`] — dense f32 reference matvec (exact).
//! * [`Precision::Ternary`] — 1.58-bit BitLinear: absmean-quantized {−1,0,+1}
//!   weights, a multiplication-free hot path ([`sovereign-bitlinear-core`]).
//! * [`Precision::Nvfp4`] — 4-bit NVFP4 microscaling, 16-value blocks sharing
//!   one E4M3 scale ([`sovereign-nvfp4-runtime`]).
//! * [`Precision::Int8`] — INT8 VNNI: per-row symmetric `i8` weights,
//!   asymmetric `u8` activations with zero-point correction, `i32`
//!   accumulation via VPDPBUSD-style dots ([`sovereign-vnni`]) — the Zen-5
//!   tier-1 hot path from the operator's AVX-512 note (M085).
//! * [`Precision::Bf16`] — BF16 weights, f32 accumulation via VDPBF16PS-style
//!   dots (the operator's `VPDOTBF16PLUS`, [`sovereign-vnni`] `MatBf16`) — the
//!   second Zen-5 tier-1 dot path: half f32's weight memory at f32 range.
//!
//! [`sovereign-vnni`]: https://docs.rs/sovereign-vnni
//!
//! The point is *substitutability*: the same `forward(x)` contract regardless
//! of precision, so a model can pick a precision per layer and the rest of the
//! stack is unchanged. The exactness of the f32 path, the exact reconstruction
//! of ternary on uniform-magnitude weights, and argmax-preservation under
//! NVFP4 are pinned as tests.
//!
//! [`sovereign-bitlinear-core`]: https://docs.rs/sovereign-bitlinear-core
//! [`sovereign-nvfp4-runtime`]: https://docs.rs/sovereign-nvfp4-runtime
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_bitlinear_core::{BitLinearLayer, EnergyReport, Packing};
use sovereign_nvfp4_runtime::{
    QuantMatrix, RhtQuantMatrix, TwoDQuantMatrix, relative_frobenius_error,
};
use sovereign_vnni::{MatBf16, MatI8};
use thiserror::Error;

/// Schema version of the linear-layer surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The precision a [`Linear`] runs at.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum Precision {
    /// Dense f32 reference.
    F32,
    /// Ternary 1.58-bit BitLinear (multiplication-free).
    Ternary,
    /// 4-bit NVFP4 microscaling.
    Nvfp4,
    /// INT8 VNNI (VPDPBUSD): per-row symmetric `i8` weights, asymmetric `u8`
    /// activations, `i32` accumulation — the Zen-5 tier-1 hot path.
    Int8,
    /// BF16 (VDPBF16PS / the operator's `VPDOTBF16PLUS`): weights stored as
    /// BFloat16, dot products accumulated in f32 — half the weight memory of
    /// f32 at f32 range, the second Zen-5 tier-1 dot path.
    Bf16,
}

/// Things that can go wrong building or running a linear layer.
#[derive(Debug, Error, PartialEq)]
pub enum LinearError {
    /// The weight matrix had the wrong element count for its shape.
    #[error("weight shape: expected {expected} ({output_dim}x{input_dim}), got {got}")]
    WeightShape {
        /// Expected element count.
        expected: usize,
        /// Output rows.
        output_dim: usize,
        /// Input columns.
        input_dim: usize,
        /// Observed count.
        got: usize,
    },
    /// The input vector width did not match `input_dim`.
    #[error("input width: expected {expected}, got {got}")]
    InputWidth {
        /// Expected width.
        expected: usize,
        /// Observed width.
        got: usize,
    },
    /// A backend kernel rejected the construction or call.
    #[error("backend: {0}")]
    Backend(String),
}

/// Which NVFP4 accuracy recipe (M077) a `Precision::Nvfp4` layer uses. All
/// store at the same 4.5 bits/param; they differ in how the weights are
/// conditioned before 4-bit microscaling.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub enum NvfpRecipe {
    /// Plain per-row block microscaling.
    #[default]
    Plain,
    /// Random Hadamard transform — spreads block outliers (seeded).
    Rht(u64),
    /// Two-dimensional per-row + per-column scaling.
    TwoD,
}

/// An INT8 (VNNI) weight backend: per-row symmetrically quantized `i8`
/// weights plus the per-row scales and row sums the asymmetric-activation
/// dequantization needs.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
struct Int8Layer {
    /// The `i8` weight matrix (executed via VPDPBUSD-style dots).
    mat: MatI8,
    /// Per-row dequantization scales (`max|W[r]| / 127`).
    row_scales: Vec<f32>,
    /// Per-row weight sums (`Σ_j Wq[r][j]`), the zero-point correction term.
    row_sums: Vec<i32>,
}

impl Int8Layer {
    /// Quantize a row-major f32 matrix: each row symmetric to `i8` with its
    /// own scale (an all-zero row gets scale 0 and stays all-zero).
    fn from_f32(weights: &[f32], output_dim: usize, input_dim: usize) -> Result<Self, LinearError> {
        let mut q = vec![0i8; weights.len()];
        let mut row_scales = vec![0.0f32; output_dim];
        for r in 0..output_dim {
            let row = &weights[r * input_dim..(r + 1) * input_dim];
            let max_abs = row.iter().fold(0.0f32, |m, &w| m.max(w.abs()));
            if max_abs > 0.0 {
                let scale = max_abs / 127.0;
                row_scales[r] = scale;
                for (j, &w) in row.iter().enumerate() {
                    q[r * input_dim + j] = (w / scale).round().clamp(-127.0, 127.0) as i8;
                }
            }
        }
        let mat = MatI8::from_i8(&q, output_dim, input_dim)
            .map_err(|e| LinearError::Backend(e.to_string()))?;
        let row_sums = mat.row_sums();
        Ok(Self {
            mat,
            row_scales,
            row_sums,
        })
    }

    /// INT8 forward: quantize the f32 activations to `u8` (asymmetric, with a
    /// zero point), run the VNNI `i32` matvec, then dequantize with the
    /// zero-point correction `y_r = s_w[r]·s_x·(acc_r − zp·Σ Wq[r])`.
    fn forward(&self, x: &[f32]) -> Result<Vec<f32>, LinearError> {
        let (lo, hi) = x
            .iter()
            .fold((0.0f32, 0.0f32), |(lo, hi), &v| (lo.min(v), hi.max(v)));
        let span = hi - lo;
        if span <= 0.0 {
            // A constant-zero-span input quantizes to a single code; with x
            // uniformly `lo`, y = lo · Σ_j W[r][j] reconstructed from row data.
            return Ok(self
                .row_sums
                .iter()
                .zip(&self.row_scales)
                .map(|(&s, &scale)| lo * scale * s as f32)
                .collect());
        }
        let x_scale = span / 255.0;
        let zp = (-lo / x_scale).round().clamp(0.0, 255.0) as u8;
        let q: Vec<u8> = x
            .iter()
            .map(|&v| ((v / x_scale) + zp as f32).round().clamp(0.0, 255.0) as u8)
            .collect();
        let acc = self
            .mat
            .matvec(&q)
            .map_err(|e| LinearError::Backend(e.to_string()))?;
        Ok(acc
            .iter()
            .zip(&self.row_scales)
            .zip(&self.row_sums)
            .map(|((&a, &w_scale), &rs)| w_scale * x_scale * (a - zp as i32 * rs) as f32)
            .collect())
    }
}

/// The precision-specific stored weights.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
enum Backend {
    F32(Vec<f32>),
    Ternary(BitLinearLayer),
    Nvfp4(QuantMatrix),
    Nvfp4Rht(RhtQuantMatrix),
    Nvfp4TwoD(TwoDQuantMatrix),
    Int8(Int8Layer),
    Bf16(MatBf16),
}

/// A linear layer `y = W·x` with a selectable execution precision.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Linear {
    /// Output rows.
    output_dim: usize,
    /// Input columns.
    input_dim: usize,
    backend: Backend,
}

impl Linear {
    /// Build a layer from a row-major `output_dim × input_dim` f32 weight
    /// matrix, quantizing into the chosen precision's backend.
    pub fn from_f32(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
        precision: Precision,
    ) -> Result<Self, LinearError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(LinearError::WeightShape {
                expected,
                output_dim,
                input_dim,
                got: weights.len(),
            });
        }
        let backend = match precision {
            Precision::F32 => Backend::F32(weights.to_vec()),
            Precision::Ternary => Backend::Ternary(
                BitLinearLayer::from_weights(weights, output_dim, input_dim, Packing::Base3)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
            Precision::Nvfp4 => Backend::Nvfp4(
                QuantMatrix::from_f32(weights, output_dim, input_dim)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
            Precision::Int8 => Backend::Int8(Int8Layer::from_f32(weights, output_dim, input_dim)?),
            Precision::Bf16 => Backend::Bf16(
                MatBf16::from_f32(weights, output_dim, input_dim)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
        };
        Ok(Self {
            output_dim,
            input_dim,
            backend,
        })
    }

    /// Build a `Precision::Nvfp4` layer that uses a specific M077 accuracy
    /// [`NvfpRecipe`] — the integration point that lets the decoder's NVFP4
    /// projections select RHT outlier-spreading or 2D per-row+per-column
    /// scaling instead of plain microscaling, for sensitive weight matrices.
    pub fn from_f32_nvfp4(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
        recipe: NvfpRecipe,
    ) -> Result<Self, LinearError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(LinearError::WeightShape {
                expected,
                output_dim,
                input_dim,
                got: weights.len(),
            });
        }
        let backend = match recipe {
            NvfpRecipe::Plain => Backend::Nvfp4(
                QuantMatrix::from_f32(weights, output_dim, input_dim)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
            NvfpRecipe::Rht(seed) => Backend::Nvfp4Rht(
                RhtQuantMatrix::from_f32(weights, output_dim, input_dim, seed)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
            NvfpRecipe::TwoD => Backend::Nvfp4TwoD(
                TwoDQuantMatrix::from_f32(weights, output_dim, input_dim)
                    .map_err(|e| LinearError::Backend(e.to_string()))?,
            ),
        };
        Ok(Self {
            output_dim,
            input_dim,
            backend,
        })
    }

    /// Build a `Precision::Nvfp4` layer that auto-selects the lowest-error
    /// M077 [`NvfpRecipe`] for this weight matrix via [`best_nvfp4_recipe`].
    /// This is the per-projection integration point the model builder uses so
    /// each NVFP4 layer gets the accuracy recipe its weight distribution needs
    /// (outlier-heavy → RHT, column-structured → 2D, well-behaved → plain)
    /// without a hand-tuned per-layer table.
    pub fn from_f32_nvfp4_auto(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
    ) -> Result<Self, LinearError> {
        let recipe = best_nvfp4_recipe(weights, output_dim, input_dim);
        Self::from_f32_nvfp4(weights, output_dim, input_dim, recipe)
    }

    /// The M077 [`NvfpRecipe`] backing this layer, or `None` if the layer is
    /// not NVFP4. Lets the model builder report which recipe each projection
    /// auto-selected.
    pub fn nvfp4_recipe(&self) -> Option<NvfpRecipe> {
        match &self.backend {
            Backend::Nvfp4(_) => Some(NvfpRecipe::Plain),
            Backend::Nvfp4Rht(q) => Some(NvfpRecipe::Rht(q.seed())),
            Backend::Nvfp4TwoD(_) => Some(NvfpRecipe::TwoD),
            _ => None,
        }
    }

    /// Output dimension (rows).
    pub fn output_dim(&self) -> usize {
        self.output_dim
    }

    /// Input dimension (columns).
    pub fn input_dim(&self) -> usize {
        self.input_dim
    }

    /// The execution precision.
    pub fn precision(&self) -> Precision {
        match self.backend {
            Backend::F32(_) => Precision::F32,
            Backend::Ternary(_) => Precision::Ternary,
            Backend::Nvfp4(_) | Backend::Nvfp4Rht(_) | Backend::Nvfp4TwoD(_) => Precision::Nvfp4,
            Backend::Int8(_) => Precision::Int8,
            Backend::Bf16(_) => Precision::Bf16,
        }
    }

    /// Effective bits stored per weight parameter at this precision.
    pub fn bits_per_param(&self) -> f64 {
        match &self.backend {
            Backend::F32(_) => 32.0,
            Backend::Ternary(b) => b.bits_per_param(),
            Backend::Nvfp4(q) => q.bits_per_param(),
            Backend::Nvfp4Rht(q) => q.bits_per_param(),
            // 4-bit core + per-row + per-column scales — the NVFP4 nominal.
            Backend::Nvfp4TwoD(_) => 4.5,
            // 8-bit weights + one f32 scale and one i32 row sum per row.
            Backend::Int8(l) => {
                let params = (self.output_dim * self.input_dim) as f64;
                (8.0 * params + 64.0 * l.row_scales.len() as f64) / params
            }
            // BF16 is a flat 16 bits per weight (no per-row side data).
            Backend::Bf16(_) => 16.0,
        }
    }

    /// Energy / arithmetic profile of a ternary forward — the dump's energy
    /// monitor (F06067-F06070) surfaced at the production linear layer.
    ///
    /// Returns `Some(report)` only at [`Precision::Ternary`], where the
    /// inner products are multiplication-free and the savings are real;
    /// `None` for F32 / NVFP4, which spend genuine floating-point multiplies
    /// and have no mul-free accounting to report.
    pub fn energy_report(&self, x: &[f32]) -> Result<Option<EnergyReport>, LinearError> {
        if x.len() != self.input_dim {
            return Err(LinearError::InputWidth {
                expected: self.input_dim,
                got: x.len(),
            });
        }
        match &self.backend {
            Backend::Ternary(b) => {
                let (_y, ops) = b
                    .forward(x)
                    .map_err(|e| LinearError::Backend(e.to_string()))?;
                Ok(Some(ops.energy_report(self.output_dim * self.input_dim)))
            }
            _ => Ok(None),
        }
    }

    /// Run `y = W·x`. `x.len()` must equal [`input_dim`](Self::input_dim);
    /// the result has length [`output_dim`](Self::output_dim).
    pub fn forward(&self, x: &[f32]) -> Result<Vec<f32>, LinearError> {
        if x.len() != self.input_dim {
            return Err(LinearError::InputWidth {
                expected: self.input_dim,
                got: x.len(),
            });
        }
        match &self.backend {
            Backend::F32(w) => Ok(dense_matvec(w, x, self.output_dim, self.input_dim)),
            Backend::Ternary(b) => b
                .forward(x)
                .map(|(y, _ops)| y)
                .map_err(|e| LinearError::Backend(e.to_string())),
            Backend::Nvfp4(q) => q.matvec(x).map_err(|e| LinearError::Backend(e.to_string())),
            Backend::Nvfp4Rht(q) => q.matvec(x).map_err(|e| LinearError::Backend(e.to_string())),
            Backend::Nvfp4TwoD(q) => q.matvec(x).map_err(|e| LinearError::Backend(e.to_string())),
            Backend::Int8(l) => l.forward(x),
            Backend::Bf16(m) => m.matvec(x).map_err(|e| LinearError::Backend(e.to_string())),
        }
    }
}

/// Row-major `rows × cols` matrix times a `cols`-vector.
fn dense_matvec(w: &[f32], x: &[f32], rows: usize, cols: usize) -> Vec<f32> {
    let mut out = vec![0.0f32; rows];
    for (r, o) in out.iter_mut().enumerate() {
        let row = &w[r * cols..(r + 1) * cols];
        *o = row.iter().zip(x).map(|(a, b)| a * b).sum();
    }
    out
}

/// Pick the NVFP4 [`NvfpRecipe`] with the lowest reconstruction error for a
/// given weight matrix — the actionable per-layer recipe decision (the
/// NVFP4 analogue of `is_ternary_friendly`). Builds each applicable recipe,
/// measures `‖W − Ŵ‖/‖W‖`, and returns the cheapest. `Rht` is only
/// considered when `input_dim` is a power of two; ties favor the earlier
/// (simpler) recipe. Use it to feed [`Linear::from_f32_nvfp4`].
pub fn best_nvfp4_recipe(weights: &[f32], output_dim: usize, input_dim: usize) -> NvfpRecipe {
    best_nvfp4_recipe_with_error(weights, output_dim, input_dim).0
}

/// Like [`best_nvfp4_recipe`] but also returns the winning recipe's relative
/// reconstruction error `‖W − Ŵ‖/‖W‖`. The error is what selective-HP needs:
/// a layer whose best recipe still has high error is a candidate to keep in
/// higher precision (see [`recommend_high_precision`]).
pub fn best_nvfp4_recipe_with_error(
    weights: &[f32],
    output_dim: usize,
    input_dim: usize,
) -> (NvfpRecipe, f64) {
    let mut best = NvfpRecipe::Plain;
    let mut best_err = f64::INFINITY;
    let mut consider = |recipe: NvfpRecipe, recon: Option<Vec<f32>>| {
        if let Some(w) = recon {
            let e = relative_frobenius_error(weights, &w);
            if e < best_err {
                best_err = e;
                best = recipe;
            }
        }
    };
    consider(
        NvfpRecipe::Plain,
        QuantMatrix::from_f32(weights, output_dim, input_dim)
            .ok()
            .map(|q| q.dequantized_weights()),
    );
    consider(
        NvfpRecipe::TwoD,
        TwoDQuantMatrix::from_f32(weights, output_dim, input_dim)
            .ok()
            .map(|q| q.dequantized_weights()),
    );
    if input_dim.is_power_of_two() {
        consider(
            NvfpRecipe::Rht(0),
            RhtQuantMatrix::from_f32(weights, output_dim, input_dim, 0)
                .ok()
                .map(|q| q.dequantized_weights()),
        );
    }
    (best, best_err)
}

/// A named projection's weights and shape, for [`recommend_high_precision`].
pub struct NamedProjection<'a> {
    /// The projection's name (e.g. `"lm_head"`, `"layer3.gate"`).
    pub name: &'a str,
    /// Row-major `output_dim × input_dim` weights.
    pub weights: &'a [f32],
    /// Output dimension (rows).
    pub output_dim: usize,
    /// Input dimension (columns).
    pub input_dim: usize,
}

/// Data-driven selective-HP: given the model's projections, return the names
/// that should stay in higher precision because even their *best* NVFP4 recipe
/// leaves a relative reconstruction error above `tolerance`. Results are ranked
/// worst-error-first and capped at `budget` (the selective-HP layer budget).
///
/// This replaces a hardcoded high-precision-layer list with a measurement: the
/// layers NVFP4 hurts most are protected, whatever they are named. An empty
/// result means every projection quantizes within tolerance.
pub fn recommend_high_precision<'a>(
    projections: &[NamedProjection<'a>],
    tolerance: f64,
    budget: usize,
) -> Vec<&'a str> {
    let mut scored: Vec<(&'a str, f64)> = projections
        .iter()
        .map(|p| {
            let (_, err) = best_nvfp4_recipe_with_error(p.weights, p.output_dim, p.input_dim);
            (p.name, err)
        })
        .filter(|(_, err)| *err > tolerance)
        .collect();
    // Worst error first; NaN (degenerate) sorts last.
    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));
    scored.truncate(budget);
    scored.into_iter().map(|(name, _)| name).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn argmax(v: &[f32]) -> usize {
        let mut best = 0;
        for i in 1..v.len() {
            if v[i] > v[best] {
                best = i;
            }
        }
        best
    }

    #[test]
    fn f32_forward_is_exact() {
        // 2x3 matrix, x = [1,2,3]
        let w = vec![1.0, 0.0, -1.0, 2.0, 1.0, 0.0];
        let lin = Linear::from_f32(&w, 2, 3, Precision::F32).unwrap();
        let y = lin.forward(&[1.0, 2.0, 3.0]).unwrap();
        // row0: 1*1+0*2-1*3 = -2 ; row1: 2*1+1*2+0*3 = 4
        assert_eq!(y, vec![-2.0, 4.0]);
    }

    #[test]
    fn ternary_energy_report_surfaced() {
        // A 4×8 ternary layer reports its mul-free savings.
        let (output_dim, input_dim) = (4, 8);
        let w = vec![0.5f32; output_dim * input_dim];
        let lin = Linear::from_f32(&w, output_dim, input_dim, Precision::Ternary).unwrap();
        let r = lin
            .energy_report(&vec![1.0f32; input_dim])
            .unwrap()
            .expect("ternary layer reports energy");
        assert_eq!(r.muls_eliminated, output_dim * input_dim);
        assert_eq!(r.float_muls, output_dim); // only the per-row scales
        assert!(r.energy_saving_ratio > 0.8);
    }

    #[test]
    fn non_ternary_has_no_energy_report() {
        let w = vec![0.5f32; 8];
        for p in [Precision::F32, Precision::Nvfp4] {
            let lin = Linear::from_f32(&w, 2, 4, p).unwrap();
            assert!(lin.energy_report(&[1.0f32; 4]).unwrap().is_none());
        }
    }

    #[test]
    fn best_nvfp4_recipe_picks_2d_for_column_structure() {
        // A systematically-tiny column → 2D's per-column scale reconstructs
        // it best, so the selector should prefer TwoD.
        let (output_dim, input_dim) = (6, 16);
        let mut weights = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim + 5] = 0.012;
        }
        assert_eq!(
            best_nvfp4_recipe(&weights, output_dim, input_dim),
            NvfpRecipe::TwoD
        );
    }

    #[test]
    fn best_nvfp4_recipe_runs_through_from_f32_nvfp4() {
        let (output_dim, input_dim) = (4, 16);
        let weights: Vec<f32> = (0..output_dim * input_dim)
            .map(|i| ((i % 5) as f32 - 2.0) * 0.4)
            .collect();
        let recipe = best_nvfp4_recipe(&weights, output_dim, input_dim);
        // The chosen recipe builds a working layer.
        let lin = Linear::from_f32_nvfp4(&weights, output_dim, input_dim, recipe).unwrap();
        assert_eq!(lin.precision(), Precision::Nvfp4);
        assert_eq!(
            lin.forward(&vec![1.0f32; input_dim]).unwrap().len(),
            output_dim
        );
    }

    #[test]
    fn nvfp4_recipes_selectable_through_linear() {
        // The decoder's NVFP4 projections can now pick any M077 recipe.
        let (output_dim, input_dim) = (3, 16);
        let w: Vec<f32> = (0..output_dim * input_dim)
            .map(|i| ((i % 5) as f32 - 2.0) * 0.4)
            .collect();
        let x = vec![1.0f32; input_dim];
        for recipe in [NvfpRecipe::Plain, NvfpRecipe::Rht(0xABCD), NvfpRecipe::TwoD] {
            let lin = Linear::from_f32_nvfp4(&w, output_dim, input_dim, recipe).unwrap();
            // All recipes report NVFP4 precision and ~4.5 bits/param.
            assert_eq!(lin.precision(), Precision::Nvfp4);
            assert!((lin.bits_per_param() - 4.5).abs() < 0.01);
            // ...and run a valid forward.
            let y = lin.forward(&x).unwrap();
            assert_eq!(y.len(), output_dim);
            assert!(y.iter().all(|v| v.is_finite()));
        }
    }

    #[test]
    fn nvfp4_auto_selects_best_recipe_and_reports_it() {
        // Column-structured weights → auto-constructor must pick TwoD and a
        // layer built that way must report TwoD via nvfp4_recipe().
        let (output_dim, input_dim) = (6, 16);
        let mut weights = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim + 5] = 0.012;
        }
        let lin = Linear::from_f32_nvfp4_auto(&weights, output_dim, input_dim).unwrap();
        assert_eq!(lin.precision(), Precision::Nvfp4);
        assert_eq!(lin.nvfp4_recipe(), Some(NvfpRecipe::TwoD));
        assert_eq!(
            lin.forward(&vec![1.0f32; input_dim]).unwrap().len(),
            output_dim
        );
    }

    #[test]
    fn recommend_high_precision_flags_the_worst_projection() {
        // benign: equal-magnitude weights → absmean scale maps every weight
        // onto the E2M1 grid almost exactly (near-zero NVFP4 error).
        // awkward: weights sitting between grid points → higher NVFP4 error.
        // Self-calibrate the tolerance from the measured errors so the test is
        // robust to the exact NVFP4 numerics.
        let benign = vec![0.5f32; 64];
        let awkward: Vec<f32> = (0..64).map(|i| 0.07 + (i % 11) as f32 * 0.013).collect();
        let (_, e_benign) = best_nvfp4_recipe_with_error(&benign, 4, 16);
        let (_, e_awkward) = best_nvfp4_recipe_with_error(&awkward, 4, 16);
        assert!(
            e_awkward > e_benign,
            "awkward {e_awkward} should exceed benign {e_benign}"
        );
        let tol = (e_benign + e_awkward) / 2.0;
        let projs = [
            NamedProjection {
                name: "benign",
                weights: &benign,
                output_dim: 4,
                input_dim: 16,
            },
            NamedProjection {
                name: "awkward",
                weights: &awkward,
                output_dim: 4,
                input_dim: 16,
            },
        ];
        let hp = recommend_high_precision(&projs, tol, 4);
        assert_eq!(
            hp,
            vec!["awkward"],
            "only awkward exceeds tol {tol}: {hp:?}"
        );
    }

    #[test]
    fn recommend_high_precision_respects_budget_and_tolerance() {
        let awkward: Vec<f32> = (0..32).map(|i| 0.07 + (i % 11) as f32 * 0.013).collect();
        let (_, err) = best_nvfp4_recipe_with_error(&awkward, 2, 16);
        let projs: Vec<NamedProjection> = ["a", "b", "c"]
            .iter()
            .map(|name| NamedProjection {
                name,
                weights: &awkward,
                output_dim: 2,
                input_dim: 16,
            })
            .collect();
        // All three exceed a tolerance just under their (shared) error; budget
        // caps the protected count at 2.
        assert_eq!(recommend_high_precision(&projs, err * 0.5, 2).len(), 2);
        // A tolerance above every error protects nothing.
        assert!(recommend_high_precision(&projs, err * 2.0, 4).is_empty());
    }

    #[test]
    fn best_nvfp4_recipe_with_error_agrees_with_recipe() {
        let (output_dim, input_dim) = (6, 16);
        let mut weights = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            weights[o * input_dim + 5] = 0.012;
        }
        let (recipe, err) = best_nvfp4_recipe_with_error(&weights, output_dim, input_dim);
        assert_eq!(recipe, best_nvfp4_recipe(&weights, output_dim, input_dim));
        assert!(err.is_finite() && err >= 0.0);
    }

    #[test]
    fn nvfp4_recipe_roundtrips_through_each_backend() {
        // Each explicitly-built recipe is faithfully reported back, including
        // the RHT seed; non-NVFP4 layers report None.
        let (output_dim, input_dim) = (3, 16);
        let w: Vec<f32> = (0..output_dim * input_dim)
            .map(|i| ((i % 5) as f32 - 2.0) * 0.4)
            .collect();
        for recipe in [NvfpRecipe::Plain, NvfpRecipe::Rht(0xABCD), NvfpRecipe::TwoD] {
            let lin = Linear::from_f32_nvfp4(&w, output_dim, input_dim, recipe).unwrap();
            assert_eq!(lin.nvfp4_recipe(), Some(recipe));
        }
        let f32_lin = Linear::from_f32(&w, output_dim, input_dim, Precision::F32).unwrap();
        assert_eq!(f32_lin.nvfp4_recipe(), None);
    }

    #[test]
    fn ternary_is_exact_on_uniform_magnitude_weights() {
        // All |w| equal → absmean scale = |w|, each weight maps to ±1·scale
        // exactly, so ternary forward equals the f32 forward bit-for-bit-ish.
        let w = vec![0.5, -0.5, 0.5, -0.5, 0.5, -0.5]; // 2x3
        let f32_lin = Linear::from_f32(&w, 2, 3, Precision::F32).unwrap();
        let tern = Linear::from_f32(&w, 2, 3, Precision::Ternary).unwrap();
        let x = [1.0, 1.0, 1.0];
        let yf = f32_lin.forward(&x).unwrap();
        let yt = tern.forward(&x).unwrap();
        for (a, b) in yf.iter().zip(&yt) {
            assert!((a - b).abs() < 1e-5, "{yf:?} vs {yt:?}");
        }
    }

    #[test]
    fn ternary_bits_per_param_under_two() {
        // Base3 packs 5 trits/byte → ~1.6 bits/param once the matrix is large
        // enough that padding overhead is amortized (16x16 = 256 params).
        let w: Vec<f32> = (0..256).map(|i| ((i as f32) * 0.013).sin()).collect();
        let tern = Linear::from_f32(&w, 16, 16, Precision::Ternary).unwrap();
        assert!(tern.bits_per_param() < 2.0, "{}", tern.bits_per_param());
        assert_eq!(tern.precision(), Precision::Ternary);
    }

    #[test]
    fn nvfp4_preserves_argmax_on_separated_rows() {
        // Row 1 clearly dominates for x = ones → quantized matvec keeps argmax.
        let w = vec![
            0.1, 0.1, 0.1, 0.1, // row 0 small
            2.0, 2.0, 2.0, 2.0, // row 1 large
            0.5, 0.5, 0.5, 0.5, // row 2 medium
        ];
        let f32_lin = Linear::from_f32(&w, 3, 4, Precision::F32).unwrap();
        let nv = Linear::from_f32(&w, 3, 4, Precision::Nvfp4).unwrap();
        let x = [1.0, 1.0, 1.0, 1.0];
        let yf = f32_lin.forward(&x).unwrap();
        let yn = nv.forward(&x).unwrap();
        assert_eq!(argmax(&yf), argmax(&yn));
        assert_eq!(argmax(&yn), 1);
        assert!(yn.iter().all(|v| v.is_finite()));
    }

    #[test]
    fn nvfp4_bits_per_param_is_four_point_five() {
        let w = vec![1.0; 32]; // 2x16 → exactly one block per row
        let nv = Linear::from_f32(&w, 2, 16, Precision::Nvfp4).unwrap();
        assert!(
            (nv.bits_per_param() - 4.5).abs() < 1e-9,
            "{}",
            nv.bits_per_param()
        );
    }

    #[test]
    fn all_precisions_share_the_forward_contract() {
        // Same shapes + input width regardless of precision.
        let w = vec![0.25; 8]; // 2x4
        let x = [1.0, 1.0, 1.0, 1.0];
        for p in [
            Precision::F32,
            Precision::Ternary,
            Precision::Nvfp4,
            Precision::Int8,
            Precision::Bf16,
        ] {
            let lin = Linear::from_f32(&w, 2, 4, p).unwrap();
            let y = lin.forward(&x).unwrap();
            assert_eq!(y.len(), 2, "precision {p:?}");
            assert_eq!(lin.output_dim(), 2);
            assert_eq!(lin.input_dim(), 4);
        }
    }

    #[test]
    fn int8_forward_is_close_to_f32() {
        // 8-bit weights + 8-bit activations keep the matvec within ~1% of the
        // exact f32 result on well-conditioned data.
        let (output_dim, input_dim) = (4, 16);
        let w: Vec<f32> = (0..output_dim * input_dim)
            .map(|i| ((i as f32) * 0.37).sin())
            .collect();
        let x: Vec<f32> = (0..input_dim).map(|i| ((i as f32) * 0.71).cos()).collect();
        let f32_lin = Linear::from_f32(&w, output_dim, input_dim, Precision::F32).unwrap();
        let int8 = Linear::from_f32(&w, output_dim, input_dim, Precision::Int8).unwrap();
        let yf = f32_lin.forward(&x).unwrap();
        let yq = int8.forward(&x).unwrap();
        let norm: f32 = yf.iter().map(|v| v * v).sum::<f32>().sqrt();
        for (a, b) in yf.iter().zip(&yq) {
            assert!(
                (a - b).abs() < 0.02 * norm.max(1.0),
                "f32 {yf:?} vs int8 {yq:?}"
            );
        }
    }

    #[test]
    fn int8_preserves_argmax_on_separated_rows() {
        let w = vec![
            0.1, 0.1, 0.1, 0.1, // row 0 small
            2.0, 2.0, 2.0, 2.0, // row 1 large
            0.5, 0.5, 0.5, 0.5, // row 2 medium
        ];
        let int8 = Linear::from_f32(&w, 3, 4, Precision::Int8).unwrap();
        let y = int8.forward(&[1.0, 1.0, 1.0, 1.0]).unwrap();
        assert_eq!(argmax(&y), 1);
        assert!(y.iter().all(|v| v.is_finite()));
    }

    #[test]
    fn int8_handles_negative_activations_via_zero_point() {
        // The asymmetric activation scheme must reconstruct dots with negative
        // inputs correctly (the zero-point row-sum correction at work).
        let w = vec![1.0f32, -1.0, 0.5, -0.5, 2.0, 0.0]; // 2x3
        let x = [-1.0f32, 2.0, -0.5];
        let f32_lin = Linear::from_f32(&w, 2, 3, Precision::F32).unwrap();
        let int8 = Linear::from_f32(&w, 2, 3, Precision::Int8).unwrap();
        let yf = f32_lin.forward(&x).unwrap();
        let yq = int8.forward(&x).unwrap();
        for (a, b) in yf.iter().zip(&yq) {
            assert!((a - b).abs() < 0.05, "f32 {yf:?} vs int8 {yq:?}");
        }
    }

    #[test]
    fn int8_constant_input_reconstructs_from_row_sums() {
        // A zero-span (constant) activation vector exercises the degenerate
        // quantization path: y = c · Σ_j W[r][j] via the stored row data.
        let w = vec![1.0f32, -2.0, 3.0, -1.0, 2.0, -3.0]; // rows sum to 2, -2
        let int8 = Linear::from_f32(&w, 2, 3, Precision::Int8).unwrap();
        let y = int8.forward(&[0.5, 0.5, 0.5]).unwrap();
        assert!((y[0] - 1.0).abs() < 0.05, "{y:?}");
        assert!((y[1] + 1.0).abs() < 0.05, "{y:?}");
        // and all-zero input gives exactly zero.
        assert_eq!(int8.forward(&[0.0, 0.0, 0.0]).unwrap(), vec![0.0, 0.0]);
    }

    #[test]
    fn bf16_forward_is_close_to_f32() {
        // BF16 keeps ~7 mantissa bits → matvec stays within ~1% of exact f32.
        let (output_dim, input_dim) = (4, 16);
        let w: Vec<f32> = (0..output_dim * input_dim)
            .map(|i| ((i as f32) * 0.37).sin())
            .collect();
        let x: Vec<f32> = (0..input_dim).map(|i| ((i as f32) * 0.71).cos()).collect();
        let f32_lin = Linear::from_f32(&w, output_dim, input_dim, Precision::F32).unwrap();
        let bf16 = Linear::from_f32(&w, output_dim, input_dim, Precision::Bf16).unwrap();
        assert_eq!(bf16.precision(), Precision::Bf16);
        let yf = f32_lin.forward(&x).unwrap();
        let yb = bf16.forward(&x).unwrap();
        let norm: f32 = yf.iter().map(|v| v * v).sum::<f32>().sqrt();
        for (a, b) in yf.iter().zip(&yb) {
            assert!(
                (a - b).abs() < 0.02 * norm.max(1.0),
                "f32 {yf:?} vs bf16 {yb:?}"
            );
        }
    }

    #[test]
    fn bf16_exact_on_representable_weights_and_preserves_argmax() {
        // powers-of-two weights are exact in BF16 → forward matches f32 exactly.
        let w = vec![0.5f32, -2.0, 1.0, 4.0, 2.0, -0.25]; // 2x3, all exact
        let f32_lin = Linear::from_f32(&w, 2, 3, Precision::F32).unwrap();
        let bf16 = Linear::from_f32(&w, 2, 3, Precision::Bf16).unwrap();
        assert_eq!(
            f32_lin.forward(&[1.0, 1.0, 1.0]).unwrap(),
            bf16.forward(&[1.0, 1.0, 1.0]).unwrap()
        );
        // argmax preserved on separated rows.
        let w2 = vec![0.1, 0.1, 0.1, 0.1, 2.0, 2.0, 2.0, 2.0, 0.5, 0.5, 0.5, 0.5];
        let nb = Linear::from_f32(&w2, 3, 4, Precision::Bf16).unwrap();
        assert_eq!(argmax(&nb.forward(&[1.0, 1.0, 1.0, 1.0]).unwrap()), 1);
    }

    #[test]
    fn bf16_bits_per_param_is_sixteen() {
        let w: Vec<f32> = (0..64).map(|i| ((i as f32) * 0.013).sin()).collect();
        let bf16 = Linear::from_f32(&w, 8, 8, Precision::Bf16).unwrap();
        assert_eq!(bf16.bits_per_param(), 16.0);
        // BF16 spends real FMAs → no mul-free energy report.
        assert!(bf16.energy_report(&[1.0; 8]).unwrap().is_none());
    }

    #[test]
    fn int8_bits_per_param_near_eight() {
        let w: Vec<f32> = (0..256).map(|i| ((i as f32) * 0.013).sin()).collect();
        let int8 = Linear::from_f32(&w, 16, 16, Precision::Int8).unwrap();
        assert_eq!(int8.precision(), Precision::Int8);
        // 8 bits + (32-bit scale + 32-bit row sum)/16 cols = 12 bits at 16x16.
        assert!(
            int8.bits_per_param() > 8.0 && int8.bits_per_param() < 13.0,
            "{}",
            int8.bits_per_param()
        );
        // no mul-free accounting: INT8 spends real multiplies.
        assert!(int8.energy_report(&[1.0; 16]).unwrap().is_none());
    }

    #[test]
    fn weight_shape_is_validated() {
        let err = Linear::from_f32(&[1.0, 2.0, 3.0], 2, 3, Precision::F32).unwrap_err();
        assert_eq!(
            err,
            LinearError::WeightShape {
                expected: 6,
                output_dim: 2,
                input_dim: 3,
                got: 3
            }
        );
    }

    #[test]
    fn input_width_is_validated() {
        let lin = Linear::from_f32(&[1.0; 6], 2, 3, Precision::F32).unwrap();
        assert_eq!(
            lin.forward(&[1.0, 2.0]).unwrap_err(),
            LinearError::InputWidth {
                expected: 3,
                got: 2
            }
        );
    }

    #[test]
    fn serde_round_trip_each_precision() {
        let w = vec![0.5, -0.5, 1.0, -1.0, 0.5, -0.5];
        for p in [
            Precision::F32,
            Precision::Ternary,
            Precision::Nvfp4,
            Precision::Int8,
            Precision::Bf16,
        ] {
            let lin = Linear::from_f32(&w, 2, 3, p).unwrap();
            let j = serde_json::to_string(&lin).unwrap();
            let back: Linear = serde_json::from_str(&j).unwrap();
            assert_eq!(lin, back, "precision {p:?}");
            assert_eq!(
                lin.forward(&[1.0; 3]).unwrap(),
                back.forward(&[1.0; 3]).unwrap()
            );
        }
    }
}
