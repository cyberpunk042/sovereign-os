//! `sovereign-ffn` — the SwiGLU gated feed-forward network.
//!
//! A transformer block is attention followed by a position-wise MLP. Modern
//! models use the **SwiGLU** variant of that MLP: two parallel projections
//! lift the model-width input `x` to a wider hidden size, one is passed
//! through the SiLU activation and used to *gate* the other, and a third
//! projection brings the gated hidden state back down to model width:
//!
//! ```text
//! gate = W_gate · x      up = W_up · x
//! hidden_i = SiLU(gate_i) · up_i           SiLU(z) = z · σ(z)
//! y = W_down · hidden
//! ```
//!
//! The gating is what gives SwiGLU its edge over a plain ReLU MLP: SiLU is
//! smooth and lets the network learn a soft, input-dependent gate. This crate
//! is the non-linearity half of a transformer block, the natural partner to
//! the attention engine.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the FFN surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong building or running the FFN.
#[derive(Debug, Error, PartialEq)]
pub enum FfnError {
    /// The input length did not match the model dimension.
    #[error("dimension mismatch: expected model dim {expected}, got {got}")]
    DimMismatch {
        /// Configured model dimension.
        expected: usize,
        /// Observed input length.
        got: usize,
    },
    /// A weight matrix had the wrong number of elements for its shape.
    #[error("weight '{which}' must be {expected} elements ({rows}x{cols}), got {got}")]
    WeightShape {
        /// Which matrix (`gate`, `up`, `down`).
        which: &'static str,
        /// Expected element count.
        expected: usize,
        /// Row count.
        rows: usize,
        /// Column count.
        cols: usize,
        /// Observed element count.
        got: usize,
    },
}

/// The SiLU (a.k.a. swish) activation: `z · σ(z)`.
pub fn silu(z: f32) -> f32 {
    z / (1.0 + (-z).exp())
}

/// A SwiGLU feed-forward network.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SwiGlu {
    /// Model (input/output) dimension.
    pub dim: usize,
    /// Hidden (intermediate) dimension.
    pub hidden: usize,
    /// Gate projection, row-major `hidden × dim`.
    pub w_gate: Vec<f32>,
    /// Up projection, row-major `hidden × dim`.
    pub w_up: Vec<f32>,
    /// Down projection, row-major `dim × hidden`.
    pub w_down: Vec<f32>,
}

impl SwiGlu {
    /// Build a SwiGLU FFN from its three weight matrices.
    ///
    /// `w_gate` and `w_up` are `hidden × dim`; `w_down` is `dim × hidden`
    /// (all row-major). Returns an error if any matrix is mis-shaped.
    pub fn new(
        dim: usize,
        hidden: usize,
        w_gate: Vec<f32>,
        w_up: Vec<f32>,
        w_down: Vec<f32>,
    ) -> Result<Self, FfnError> {
        check_shape("gate", &w_gate, hidden, dim)?;
        check_shape("up", &w_up, hidden, dim)?;
        check_shape("down", &w_down, dim, hidden)?;
        Ok(Self {
            dim,
            hidden,
            w_gate,
            w_up,
            w_down,
        })
    }

    /// Run the FFN on a `dim`-length activation, returning a `dim`-length one.
    pub fn forward(&self, x: &[f32]) -> Result<Vec<f32>, FfnError> {
        if x.len() != self.dim {
            return Err(FfnError::DimMismatch {
                expected: self.dim,
                got: x.len(),
            });
        }
        // gate, up: hidden = W · x
        let gate = matvec(&self.w_gate, x, self.hidden, self.dim);
        let up = matvec(&self.w_up, x, self.hidden, self.dim);
        // hidden = SiLU(gate) ⊙ up
        let hidden: Vec<f32> = gate.iter().zip(&up).map(|(g, u)| silu(*g) * u).collect();
        // y = W_down · hidden
        Ok(matvec(&self.w_down, &hidden, self.dim, self.hidden))
    }
}

fn check_shape(which: &'static str, w: &[f32], rows: usize, cols: usize) -> Result<(), FfnError> {
    let expected = rows * cols;
    if w.len() != expected {
        return Err(FfnError::WeightShape {
            which,
            expected,
            rows,
            cols,
            got: w.len(),
        });
    }
    Ok(())
}

/// Row-major `rows × cols` matrix times a `cols`-length vector → `rows`.
fn matvec(w: &[f32], x: &[f32], rows: usize, cols: usize) -> Vec<f32> {
    let mut out = vec![0.0f32; rows];
    for (r, o) in out.iter_mut().enumerate() {
        let row = &w[r * cols..(r + 1) * cols];
        *o = row.iter().zip(x).map(|(a, b)| a * b).sum();
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: &[f32], b: &[f32], eps: f32) -> bool {
        a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() <= eps)
    }

    #[test]
    fn silu_zero_is_zero() {
        assert_eq!(silu(0.0), 0.0);
    }

    #[test]
    fn silu_is_monotone_for_large_inputs() {
        // SiLU(z) → z for large positive z, → 0 for large negative z.
        assert!((silu(20.0) - 20.0).abs() < 1e-3);
        assert!(silu(-20.0).abs() < 1e-6);
        // smooth, with a slight dip below zero for small negatives
        assert!(silu(-1.0) < 0.0);
    }

    #[test]
    fn output_has_model_dimension() {
        let ffn = SwiGlu::new(2, 3, vec![0.1; 6], vec![0.2; 6], vec![0.3; 6]).unwrap();
        let y = ffn.forward(&[1.0, -1.0]).unwrap();
        assert_eq!(y.len(), 2);
    }

    #[test]
    fn identity_gate_passes_up_projection() {
        // dim=1, hidden=1. gate weight 0 → SiLU(0)=0 → hidden 0 → output 0,
        // regardless of up/down. Pins the gating wiring.
        let ffn = SwiGlu::new(1, 1, vec![0.0], vec![5.0], vec![7.0]).unwrap();
        let y = ffn.forward(&[3.0]).unwrap();
        assert_eq!(y, vec![0.0]);
    }

    #[test]
    fn known_value_end_to_end() {
        // dim=1, hidden=1, all weights 1.
        // x=[2]: gate=2, up=2, hidden=SiLU(2)*2, y=hidden.
        let ffn = SwiGlu::new(1, 1, vec![1.0], vec![1.0], vec![1.0]).unwrap();
        let y = ffn.forward(&[2.0]).unwrap();
        let expected = silu(2.0) * 2.0;
        assert!(approx(&y, &[expected], 1e-6), "{y:?} vs {expected}");
    }

    #[test]
    fn gating_is_elementwise_in_hidden_space() {
        // dim=1, hidden=2; gate=[1,0], up=[1,1], down=[1,1].
        // x=[1]: gate=[1,0], up=[1,1]; hidden=[SiLU(1)*1, SiLU(0)*1]=[SiLU(1),0]
        // y = 1*SiLU(1) + 1*0 = SiLU(1)
        let ffn = SwiGlu::new(1, 2, vec![1.0, 0.0], vec![1.0, 1.0], vec![1.0, 1.0]).unwrap();
        let y = ffn.forward(&[1.0]).unwrap();
        assert!(approx(&y, &[silu(1.0)], 1e-6), "{y:?}");
    }

    #[test]
    fn dim_mismatch_is_caught() {
        let ffn = SwiGlu::new(2, 2, vec![1.0; 4], vec![1.0; 4], vec![1.0; 4]).unwrap();
        assert_eq!(
            ffn.forward(&[1.0]).unwrap_err(),
            FfnError::DimMismatch {
                expected: 2,
                got: 1
            }
        );
    }

    #[test]
    fn weight_shape_is_validated() {
        let err = SwiGlu::new(2, 3, vec![1.0; 5], vec![1.0; 6], vec![1.0; 6]).unwrap_err();
        assert_eq!(
            err,
            FfnError::WeightShape {
                which: "gate",
                expected: 6,
                rows: 3,
                cols: 2,
                got: 5
            }
        );
    }

    #[test]
    fn serde_round_trip() {
        let ffn = SwiGlu::new(2, 2, vec![1.0; 4], vec![2.0; 4], vec![3.0; 4]).unwrap();
        let j = serde_json::to_string(&ffn).unwrap();
        let back: SwiGlu = serde_json::from_str(&j).unwrap();
        assert_eq!(ffn, back);
    }
}
