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

/// The precision-specific stored weights.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
enum Backend {
    F32(Vec<f32>),
    Ternary(BitLinearLayer),
    Nvfp4(QuantMatrix),
    Nvfp4Rht(RhtQuantMatrix),
    Nvfp4TwoD(TwoDQuantMatrix),
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
    best
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
        for p in [Precision::F32, Precision::Ternary, Precision::Nvfp4] {
            let lin = Linear::from_f32(&w, 2, 4, p).unwrap();
            let y = lin.forward(&x).unwrap();
            assert_eq!(y.len(), 2, "precision {p:?}");
            assert_eq!(lin.output_dim(), 2);
            assert_eq!(lin.input_dim(), 4);
        }
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
        for p in [Precision::F32, Precision::Ternary, Precision::Nvfp4] {
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
