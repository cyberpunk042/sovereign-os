//! `sovereign-decoder-layer` — a uniform contract over the block family.
//!
//! Three crates implement a decoder block — the f32
//! [`sovereign-transformer-block`], the precision-selectable
//! [`sovereign-quant-block`], and the multi-head GQA
//! [`sovereign-mha-block`] — each with the same shape: consume a hidden
//! state, advance a KV cache, return the next hidden state. This crate gives
//! them one trait, [`DecoderLayer`], and a [`LayerStack`] that chains a
//! *heterogeneous* list of them.
//!
//! That heterogeneity is the point: the mixed-precision assignment
//! `sovereign-quant-calibration` recommends only matters if a model can
//! actually run, say, an f32 layer, then a ternary layer, then an NVFP4
//! multi-head layer, all in one residual stream. With a common contract it
//! can — the stack just calls `step` down the line. The trait is object-safe,
//! so a stack is a `Vec<Box<dyn DecoderLayer>>` of any mix of block types,
//! and a single-layer stack reproduces the underlying block exactly (pinned
//! as a test).
//!
//! [`sovereign-transformer-block`]: https://docs.rs/sovereign-transformer-block
//! [`sovereign-quant-block`]: https://docs.rs/sovereign-quant-block
//! [`sovereign-mha-block`]: https://docs.rs/sovereign-mha-block
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_mha_block::MhaDecoderBlock;
use sovereign_quant_block::QuantDecoderBlock;
use sovereign_transformer_block::DecoderBlock;
use thiserror::Error;

/// Schema version of the decoder-layer surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong running a layer or a stack.
#[derive(Debug, Error, PartialEq)]
pub enum LayerError {
    /// A wrapped block error (message preserved across block types).
    #[error("layer {index}: {message}")]
    Block {
        /// Position of the failing layer in the stack (0 for a bare layer).
        index: usize,
        /// The block's error message.
        message: String,
    },
    /// The stack was built with no layers.
    #[error("a decoder stack needs at least one layer")]
    Empty,
}

/// One decoder layer: advance one position through it.
///
/// Object-safe, so a [`LayerStack`] can hold any mix of block types. Requires
/// `Debug` (every block type derives it) so a stack of trait objects is itself
/// `Debug`, and `Send` so a built model can be owned by a worker/daemon thread
/// (the gateway serves generation from thread-per-connection handlers). Every
/// block type is plain owned data (`Vec<f32>` weights + scalars), so `Send` is
/// already satisfied — this only records the guarantee the trait object needs.
pub trait DecoderLayer: std::fmt::Debug + Send {
    /// Consume `hidden`, advance this layer's KV cache, return the next hidden
    /// state. The error message is the underlying block's, stringified.
    fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, String>;

    /// Number of positions currently in this layer's KV cache.
    fn cached_positions(&self) -> usize;
}

impl DecoderLayer for DecoderBlock {
    fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, String> {
        DecoderBlock::step(self, hidden).map_err(|e| e.to_string())
    }
    fn cached_positions(&self) -> usize {
        self.len()
    }
}

impl DecoderLayer for QuantDecoderBlock {
    fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, String> {
        QuantDecoderBlock::step(self, hidden).map_err(|e| e.to_string())
    }
    fn cached_positions(&self) -> usize {
        self.len()
    }
}

impl DecoderLayer for MhaDecoderBlock {
    fn step(&mut self, hidden: &[f32]) -> Result<Vec<f32>, String> {
        MhaDecoderBlock::step(self, hidden).map_err(|e| e.to_string())
    }
    fn cached_positions(&self) -> usize {
        self.len()
    }
}

/// A heterogeneous stack of decoder layers sharing one residual stream.
#[derive(Debug)]
pub struct LayerStack {
    layers: Vec<Box<dyn DecoderLayer>>,
}

impl LayerStack {
    /// Build a stack from an ordered list of layers (any mix of block types).
    pub fn new(layers: Vec<Box<dyn DecoderLayer>>) -> Result<Self, LayerError> {
        if layers.is_empty() {
            return Err(LayerError::Empty);
        }
        Ok(Self { layers })
    }

    /// Number of layers.
    pub fn depth(&self) -> usize {
        self.layers.len()
    }

    /// Decode positions seen so far (the first layer's KV depth; every layer
    /// advances in lockstep).
    pub fn positions(&self) -> usize {
        self.layers
            .first()
            .map(|l| l.cached_positions())
            .unwrap_or(0)
    }

    /// Run one position through every layer in order, threading the hidden
    /// state down the stack, and return the final hidden state.
    pub fn run(&mut self, hidden: &[f32]) -> Result<Vec<f32>, LayerError> {
        let mut h = hidden.to_vec();
        for (index, layer) in self.layers.iter_mut().enumerate() {
            h = layer
                .step(&h)
                .map_err(|message| LayerError::Block { index, message })?;
        }
        Ok(h)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use sovereign_ffn::SwiGlu;
    use sovereign_linear::Precision;
    use sovereign_mha_block::MhaBlockWeights;
    use sovereign_quant_block::QuantBlockWeights;
    use sovereign_rmsnorm::RmsNorm;
    use sovereign_transformer_block::BlockWeights;

    const MD: usize = 4;

    fn mat(s: f32, n: usize) -> Vec<f32> {
        (0..n).map(|i| ((i as f32 + s) * 0.017).sin()).collect()
    }

    fn transformer_layer() -> DecoderBlock {
        let bw = BlockWeights {
            model_dim: MD,
            head_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(1.0, MD * MD),
            w_k: mat(2.0, MD * MD),
            w_v: mat(3.0, MD * MD),
            w_o: mat(4.0, MD * MD),
            ffn: SwiGlu::new(
                MD,
                MD,
                mat(5.0, MD * MD),
                mat(6.0, MD * MD),
                mat(7.0, MD * MD),
            )
            .unwrap(),
        };
        DecoderBlock::new(bw).unwrap()
    }

    fn quant_layer(p: Precision) -> QuantDecoderBlock {
        let qw = QuantBlockWeights {
            model_dim: MD,
            head_dim: MD,
            hidden_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(8.0, MD * MD),
            w_k: mat(9.0, MD * MD),
            w_v: mat(10.0, MD * MD),
            w_o: mat(11.0, MD * MD),
            w_gate: mat(12.0, MD * MD),
            w_up: mat(13.0, MD * MD),
            w_down: mat(14.0, MD * MD),
        };
        QuantDecoderBlock::from_weights(&qw, p).unwrap()
    }

    fn mha_layer(p: Precision) -> MhaDecoderBlock {
        // 2 query heads, 1 kv head (MQA), head_dim 2 → q_dim 4 = MD.
        let (nq, nkv, hd) = (2, 1, 2);
        let mw = MhaBlockWeights {
            model_dim: MD,
            head_dim: hd,
            num_q_heads: nq,
            num_kv_heads: nkv,
            hidden_dim: MD,
            attn_norm: RmsNorm::new(MD),
            ffn_norm: RmsNorm::new(MD),
            w_q: mat(15.0, nq * hd * MD),
            w_k: mat(16.0, nkv * hd * MD),
            w_v: mat(17.0, nkv * hd * MD),
            w_o: mat(18.0, MD * nq * hd),
            w_gate: mat(19.0, MD * MD),
            w_up: mat(20.0, MD * MD),
            w_down: mat(21.0, MD * MD),
        };
        MhaDecoderBlock::from_weights(&mw, p).unwrap()
    }

    #[test]
    fn heterogeneous_stack_runs_finite() {
        // f32 transformer → ternary quant → NVFP4 multi-head, one residual stream.
        let layers: Vec<Box<dyn DecoderLayer>> = vec![
            Box::new(transformer_layer()),
            Box::new(quant_layer(Precision::Ternary)),
            Box::new(mha_layer(Precision::Nvfp4)),
        ];
        let mut stack = LayerStack::new(layers).unwrap();
        assert_eq!(stack.depth(), 3);
        for step in 0..5 {
            let x: Vec<f32> = (0..MD).map(|i| ((i + step) as f32 * 0.25).sin()).collect();
            let y = stack.run(&x).unwrap();
            assert_eq!(y.len(), MD);
            assert!(y.iter().all(|v| v.is_finite()), "step {step}");
        }
        assert_eq!(stack.positions(), 5);
    }

    #[test]
    fn single_layer_stack_equals_the_block() {
        let mut bare = quant_layer(Precision::F32);
        let mut stack = LayerStack::new(vec![Box::new(quant_layer(Precision::F32))]).unwrap();
        for step in 0..4 {
            let x: Vec<f32> = (0..MD).map(|i| ((i + step) as f32 * 0.3).cos()).collect();
            assert_eq!(stack.run(&x).unwrap(), bare.step(&x).unwrap());
        }
    }

    #[test]
    fn every_block_type_satisfies_the_contract() {
        let mut layers: Vec<Box<dyn DecoderLayer>> = vec![
            Box::new(transformer_layer()),
            Box::new(quant_layer(Precision::F32)),
            Box::new(mha_layer(Precision::F32)),
        ];
        let x = vec![0.1, 0.2, -0.3, 0.4];
        for l in &mut layers {
            let y = l.step(&x).unwrap();
            assert_eq!(y.len(), MD);
            assert_eq!(l.cached_positions(), 1);
        }
    }

    #[test]
    fn empty_stack_is_rejected() {
        let err = LayerStack::new(Vec::new()).unwrap_err();
        assert_eq!(err, LayerError::Empty);
    }

    #[test]
    fn width_mismatch_surfaces_the_failing_layer() {
        let mut stack = LayerStack::new(vec![Box::new(transformer_layer())]).unwrap();
        let err = stack.run(&[1.0, 2.0]).unwrap_err();
        match err {
            LayerError::Block { index, .. } => assert_eq!(index, 0),
            other => panic!("unexpected {other:?}"),
        }
    }
}
