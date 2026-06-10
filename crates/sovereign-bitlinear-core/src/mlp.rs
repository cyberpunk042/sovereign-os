//! Multi-layer ternary feed-forward block — composing [`BitLinearLayer`]
//! into the transformer **FFN**, the dominant ternary compute in a
//! BitNet-style model.
//!
//! A single [`BitLinearLayer`] is one multiplication-free projection. A
//! real network block is a *stack*: project, apply a nonlinearity, project
//! again. This module assembles the primitive into that block while
//! preserving the two invariants the primitive guarantees:
//!
//! - **Multiplication-free inner products.** Every layer's matmul still
//!   spends zero inner-product multiplies (only `output_dim` scale
//!   multiplies per layer); [`BitLinearMlp::forward`] sums the per-layer
//!   [`OpCount`]s so the whole block's arithmetic is accountable.
//! - **Bit-for-bit exactness.** With the ReLU/identity activations here
//!   (both exact on `f32`) the stacked forward equals a dense
//!   multiply-based reference applied layer-by-layer — proven by
//!   `forward_matches_dense_reference`. Removing the multiplies does not
//!   change the answer, even across layers.
//!
//! The activation is applied *between* consecutive layers and never after
//! the final one — the standard FFN shape (`d_model → d_ff → d_model` with
//! one nonlinearity in the middle), constructible via [`BitLinearMlp::ffn`].
//!
//! Standing rule (workspace doctrine): we do not minimize anything.

use crate::{
    BitLinearError,
    linear::{BitLinearLayer, OpCount},
};
use serde::{Deserialize, Serialize};

/// Elementwise activation applied between BitLinear layers.
///
/// Both variants are exact on finite `f32`, which is what lets the stacked
/// ternary forward stay bit-for-bit identical to the dense reference.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
#[serde(rename_all = "kebab-case")]
pub enum Activation {
    /// `max(0, x)` — the standard BitNet-MLP nonlinearity.
    #[default]
    Relu,
    /// `x` — no nonlinearity (a pure linear stack).
    Identity,
}

impl Activation {
    /// Apply in place to an activation vector.
    pub fn apply(self, v: &mut [f32]) {
        match self {
            Activation::Relu => {
                for x in v.iter_mut() {
                    if *x < 0.0 {
                        *x = 0.0;
                    }
                }
            }
            Activation::Identity => {}
        }
    }
}

/// A stack of [`BitLinearLayer`]s with an [`Activation`] between
/// consecutive layers (none after the last) — a ternary feed-forward block.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BitLinearMlp {
    /// The layers, applied front to back. Non-empty; each layer's
    /// `output_dim` equals the next layer's `input_dim`.
    pub layers: Vec<BitLinearLayer>,
    /// Activation applied between consecutive layers.
    pub activation: Activation,
}

impl BitLinearMlp {
    /// Assemble a block from pre-built layers, validating that the stack is
    /// non-empty and that consecutive layers chain
    /// (`layer[k].output_dim == layer[k+1].input_dim`).
    pub fn new(
        layers: Vec<BitLinearLayer>,
        activation: Activation,
    ) -> Result<Self, BitLinearError> {
        if layers.is_empty() {
            return Err(BitLinearError::EmptyStack);
        }
        for (i, pair) in layers.windows(2).enumerate() {
            if pair[0].output_dim != pair[1].input_dim {
                return Err(BitLinearError::StackShapeMismatch {
                    index: i,
                    output_dim: pair[0].output_dim,
                    next: i + 1,
                    next_input_dim: pair[1].input_dim,
                });
            }
        }
        Ok(Self { layers, activation })
    }

    /// Build the canonical two-layer transformer FFN from real-valued
    /// weights: an expand projection `d_model → d_ff`, a ReLU, then a
    /// contract projection `d_ff → d_model`. `expand`/`contract` are
    /// row-major weight matrices (`d_ff × d_model` and `d_model × d_ff`).
    pub fn ffn(
        expand: &[f32],
        contract: &[f32],
        d_model: usize,
        d_ff: usize,
        packing: crate::Packing,
    ) -> Result<Self, BitLinearError> {
        let l0 = BitLinearLayer::from_weights(expand, d_ff, d_model, packing)?;
        let l1 = BitLinearLayer::from_weights(contract, d_model, d_ff, packing)?;
        Self::new(vec![l0, l1], Activation::Relu)
    }

    /// Input width the block expects (first layer's `input_dim`).
    pub fn input_dim(&self) -> usize {
        self.layers[0].input_dim
    }

    /// Output width the block produces (last layer's `output_dim`).
    pub fn output_dim(&self) -> usize {
        self.layers[self.layers.len() - 1].output_dim
    }

    /// Forward through the whole stack. The activation is applied between
    /// layers, never after the last. Returns the output vector and the
    /// summed [`OpCount`] across every layer.
    pub fn forward(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        let n = self.layers.len();
        let mut cur = x.to_vec();
        let mut total = OpCount::default();
        for (i, layer) in self.layers.iter().enumerate() {
            let (mut y, ops) = layer.forward(&cur)?;
            total.adds += ops.adds;
            total.subs += ops.subs;
            total.skips += ops.skips;
            total.float_muls += ops.float_muls;
            if i + 1 < n {
                self.activation.apply(&mut y);
            }
            cur = y;
        }
        Ok((cur, total))
    }

    /// Inner-product floating multiplies a dense GEMM stack of the same
    /// shapes would spend — all of which this block eliminates.
    pub fn floating_muls_eliminated(&self) -> usize {
        self.layers.iter().map(|l| l.output_dim * l.input_dim).sum()
    }

    /// Block-level packed-domain forward: every layer runs
    /// [`BitLinearLayer::forward_packed`] (single pass over the 2-bit codes,
    /// no `Vec<Trit>`), with the activation applied between layers exactly as
    /// in [`BitLinearMlp::forward`]. Bit-for-bit equal to `forward`; requires
    /// every layer to use [`Packing::TwoBit`], else
    /// [`BitLinearError::PackedForwardUnsupported`].
    pub fn forward_packed(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        let n = self.layers.len();
        let mut cur = x.to_vec();
        let mut total = OpCount::default();
        for (i, layer) in self.layers.iter().enumerate() {
            let (mut y, ops) = layer.forward_packed(&cur)?;
            total.adds += ops.adds;
            total.subs += ops.subs;
            total.skips += ops.skips;
            total.float_muls += ops.float_muls;
            if i + 1 < n {
                self.activation.apply(&mut y);
            }
            cur = y;
        }
        Ok((cur, total))
    }

    /// Residual-wrapped forward — `y = x + block(x)` — the way a transformer
    /// uses the FFN: a sublayer whose output is *added* to the residual
    /// stream rather than replacing it. Requires `input_dim == output_dim`
    /// (the block must map the residual stream back to itself); returns
    /// [`BitLinearError::ResidualShapeMismatch`] otherwise.
    ///
    /// The residual add is the structural identity guarantee: a block whose
    /// weights are all `0` (every projection outputs zero) leaves the
    /// residual stream untouched, so stacking such sublayers can never
    /// degrade the signal — the property that makes deep stacks trainable.
    pub fn forward_residual(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        if self.input_dim() != self.output_dim() {
            return Err(BitLinearError::ResidualShapeMismatch {
                input_dim: self.input_dim(),
                output_dim: self.output_dim(),
            });
        }
        let (mut y, ops) = self.forward(x)?;
        for (yi, &xi) in y.iter_mut().zip(x.iter()) {
            *yi += xi;
        }
        Ok((y, ops))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{Packing, reference};

    /// Deterministic xorshift finite-weight generator in roughly `[-4, 4)`.
    fn rng(seed: u64) -> impl FnMut() -> f32 {
        let mut state = seed;
        move || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            ((state >> 40) as f32 / 0x10_0000 as f32) * 8.0 - 4.0
        }
    }

    /// Dense multiply-based reference for the whole stack, applying the
    /// same activation between layers. The ternary block must match this
    /// bit-for-bit.
    fn dense_stack(mlp: &BitLinearMlp, x: &[f32]) -> Vec<f32> {
        let n = mlp.layers.len();
        let mut cur = x.to_vec();
        for (i, layer) in mlp.layers.iter().enumerate() {
            let trits = layer.trits().unwrap();
            let mut y = reference::dense_forward(&trits, layer.scale, layer.input_dim, &cur);
            if i + 1 < n {
                mlp.activation.apply(&mut y);
            }
            cur = y;
        }
        cur
    }

    #[test]
    fn forward_matches_dense_reference() {
        // A real FFN: d_model=12 -> d_ff=48 -> d_model=12, ReLU in the middle.
        let (d_model, d_ff) = (12, 48);
        let mut next = rng(0x9E37_79B9_7F4A_7C15);
        let expand: Vec<f32> = (0..d_ff * d_model).map(|_| next()).collect();
        let contract: Vec<f32> = (0..d_model * d_ff).map(|_| next()).collect();
        let x: Vec<f32> = (0..d_model).map(|_| next()).collect();

        for packing in [Packing::Base3, Packing::TwoBit] {
            let mlp = BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, packing).unwrap();
            assert_eq!(mlp.input_dim(), d_model);
            assert_eq!(mlp.output_dim(), d_model);

            let (y, _ops) = mlp.forward(&x).unwrap();
            let reference = dense_stack(&mlp, &x);
            // ReLU + ±1 multiplies are exact, so the stack is bit-for-bit.
            assert_eq!(y, reference, "stack mismatch under {packing:?}");
        }
    }

    #[test]
    fn relu_gates_negatives_between_layers() {
        // Construct a deterministic case where the intermediate is
        // guaranteed negative, so ReLU vs identity MUST diverge — proving
        // the activation is wired BETWEEN layers, not skipped.
        use crate::Trit;
        // l0: 2 outputs of width 4. Row 0 is all -1 → with x = all +1 the
        // intermediate[0] = scale * (-4) < 0; row 1 all +1 → +4 > 0.
        let l0_trits = [
            Trit::Minus,
            Trit::Minus,
            Trit::Minus,
            Trit::Minus, // row 0 → negative
            Trit::Plus,
            Trit::Plus,
            Trit::Plus,
            Trit::Plus, // row 1 → positive
        ];
        let l0 = BitLinearLayer::from_trits(&l0_trits, 1.0, 2, 4, Packing::Base3).unwrap();
        // l1: 1 output of width 2, both +1 → sums the two intermediates.
        let l1_trits = [Trit::Plus, Trit::Plus];
        let l1 = BitLinearLayer::from_trits(&l1_trits, 1.0, 1, 2, Packing::Base3).unwrap();
        let x = [1.0f32; 4];

        let mid = l0.forward(&x).unwrap().0;
        assert_eq!(mid, vec![-4.0, 4.0], "intermediate not as constructed");

        let relu = BitLinearMlp::new(vec![l0.clone(), l1.clone()], Activation::Relu).unwrap();
        let ident = BitLinearMlp::new(vec![l0, l1], Activation::Identity).unwrap();

        // Identity: sum(-4, 4) = 0. ReLU: sum(relu(-4)=0, 4) = 4. Distinct.
        assert_eq!(ident.forward(&x).unwrap().0, vec![0.0]);
        assert_eq!(relu.forward(&x).unwrap().0, vec![4.0]);
    }

    #[test]
    fn opcount_sums_across_layers() {
        let (d_model, d_ff) = (6, 24);
        let expand = vec![0.5f32; d_ff * d_model];
        let contract = vec![0.5f32; d_model * d_ff];
        let mlp = BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, Packing::Base3).unwrap();
        let (_y, ops) = mlp.forward(&vec![1.0f32; d_model]).unwrap();

        // float_muls = one per output across both layers (d_ff + d_model).
        assert_eq!(ops.float_muls, d_ff + d_model);
        // Every weight in both layers is accounted as add/sub/skip.
        let weights = d_ff * d_model + d_model * d_ff;
        assert_eq!(ops.adds + ops.subs + ops.skips, weights);
        // The whole stack eliminated every inner-product multiply.
        assert_eq!(mlp.floating_muls_eliminated(), weights);
    }

    #[test]
    fn empty_stack_rejected() {
        let err = BitLinearMlp::new(vec![], Activation::Relu).unwrap_err();
        assert!(matches!(err, BitLinearError::EmptyStack));
    }

    #[test]
    fn non_chaining_layers_rejected() {
        // layer0: 4 -> 8, layer1: 5 -> 2. 8 != 5, so the stack must reject.
        let l0 = BitLinearLayer::from_weights(&[0.5; 32], 8, 4, Packing::Base3).unwrap();
        let l1 = BitLinearLayer::from_weights(&[0.5; 10], 2, 5, Packing::Base3).unwrap();
        let err = BitLinearMlp::new(vec![l0, l1], Activation::Relu).unwrap_err();
        assert!(matches!(
            err,
            BitLinearError::StackShapeMismatch {
                index: 0,
                output_dim: 8,
                next: 1,
                next_input_dim: 5,
            }
        ));
    }

    #[test]
    fn deep_stack_chains() {
        // Three layers: 4 -> 8 -> 8 -> 4. Proves >2-layer composition.
        let a = BitLinearLayer::from_weights(&[0.3; 32], 8, 4, Packing::Base3).unwrap();
        let b = BitLinearLayer::from_weights(&[0.3; 64], 8, 8, Packing::Base3).unwrap();
        let c = BitLinearLayer::from_weights(&[0.3; 32], 4, 8, Packing::Base3).unwrap();
        let mlp = BitLinearMlp::new(vec![a, b, c], Activation::Relu).unwrap();
        let (y, _ops) = mlp.forward(&[1.0f32; 4]).unwrap();
        assert_eq!(y.len(), 4);
        assert_eq!(y, dense_stack(&mlp, &[1.0f32; 4]));
    }

    #[test]
    fn serde_round_trip() {
        let mlp = BitLinearMlp::ffn(&[0.5; 8], &[0.5; 8], 2, 4, Packing::TwoBit).unwrap();
        let json = serde_json::to_string(&mlp).unwrap();
        let back: BitLinearMlp = serde_json::from_str(&json).unwrap();
        assert_eq!(mlp, back);
    }

    #[test]
    fn residual_equals_input_plus_block() {
        // A square FFN (d_model == output, via d_model -> d_ff -> d_model).
        let (d_model, d_ff) = (10, 40);
        let mut next = rng(0x0BAD_C0DE_F00D_1234);
        let expand: Vec<f32> = (0..d_ff * d_model).map(|_| next()).collect();
        let contract: Vec<f32> = (0..d_model * d_ff).map(|_| next()).collect();
        let x: Vec<f32> = (0..d_model).map(|_| next()).collect();
        let mlp = BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, Packing::Base3).unwrap();

        let (plain, _) = mlp.forward(&x).unwrap();
        let (res, _) = mlp.forward_residual(&x).unwrap();
        let manual: Vec<f32> = plain.iter().zip(&x).map(|(b, xi)| b + xi).collect();
        assert_eq!(res, manual, "residual must be exactly x + block(x)");
    }

    #[test]
    fn zero_weight_block_is_residual_identity() {
        // All-zero weights → every projection outputs 0 → the residual
        // sublayer is the identity on the stream (the trainability property).
        let (d_model, d_ff) = (8, 16);
        let mlp = BitLinearMlp::ffn(
            &vec![0.0f32; d_ff * d_model],
            &vec![0.0f32; d_model * d_ff],
            d_model,
            d_ff,
            Packing::Base3,
        )
        .unwrap();
        let x: Vec<f32> = (0..d_model).map(|i| i as f32 - 3.5).collect();
        let (res, _) = mlp.forward_residual(&x).unwrap();
        assert_eq!(
            res, x,
            "zero block must leave the residual stream untouched"
        );
    }

    #[test]
    fn packed_forward_matches_forward() {
        // The block-level packed-domain forward equals the unpack-loop
        // forward bit-for-bit (output + OpCount) when every layer is TwoBit.
        let (d_model, d_ff) = (9, 36);
        let mut next = rng(0x5EED_1357_2468_ACEF);
        let expand: Vec<f32> = (0..d_ff * d_model).map(|_| next()).collect();
        let contract: Vec<f32> = (0..d_model * d_ff).map(|_| next()).collect();
        let x: Vec<f32> = (0..d_model).map(|_| next()).collect();
        let mlp = BitLinearMlp::ffn(&expand, &contract, d_model, d_ff, Packing::TwoBit).unwrap();

        let (y_ref, ops_ref) = mlp.forward(&x).unwrap();
        let (y_packed, ops_packed) = mlp.forward_packed(&x).unwrap();
        assert_eq!(y_packed, y_ref);
        assert_eq!(ops_packed, ops_ref);
    }

    #[test]
    fn packed_forward_rejects_base3_block() {
        let mlp = BitLinearMlp::ffn(&[0.5; 8], &[0.5; 8], 2, 4, Packing::Base3).unwrap();
        let err = mlp.forward_packed(&[1.0, 1.0]).unwrap_err();
        assert!(matches!(
            err,
            BitLinearError::PackedForwardUnsupported { .. }
        ));
    }

    #[test]
    fn residual_rejects_non_square_block() {
        // d_model=4 -> d_ff=8 -> 6 (output != input) cannot be residual.
        let l0 = BitLinearLayer::from_weights(&[0.3; 32], 8, 4, Packing::Base3).unwrap();
        let l1 = BitLinearLayer::from_weights(&[0.3; 48], 6, 8, Packing::Base3).unwrap();
        let mlp = BitLinearMlp::new(vec![l0, l1], Activation::Relu).unwrap();
        let err = mlp.forward_residual(&[1.0f32; 4]).unwrap_err();
        assert!(matches!(
            err,
            BitLinearError::ResidualShapeMismatch {
                input_dim: 4,
                output_dim: 6,
            }
        ));
    }
}
