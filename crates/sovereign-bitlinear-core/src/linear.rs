//! The BitLinear layer — multiplication-free ternary linear projection.

use crate::{
    BitLinearError, SCHEMA_VERSION,
    pack::{self, Packing},
    reference,
    ternary::{Trit, quantize_absmean},
};
use serde::{Deserialize, Serialize};

/// Per-forward arithmetic accounting (F06046, F06067).
///
/// The headline number is [`OpCount::floating_muls_eliminated`]: a dense
/// GEMM of the same shape would spend `output_dim × input_dim` multiplies
/// on the inner products; BitLinear spends **zero** there, keeping only
/// `output_dim` scale multiplies.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Default, Serialize, Deserialize)]
pub struct OpCount {
    /// `+1` weights — an activation was added.
    pub adds: usize,
    /// `-1` weights — an activation was subtracted.
    pub subs: usize,
    /// `0` weights — skipped, no arithmetic at all (F06045).
    pub skips: usize,
    /// Floating-point multiplies actually performed (the per-row scales).
    pub float_muls: usize,
}

impl OpCount {
    /// Inner-product multiplies a dense GEMM would have done and BitLinear
    /// did not.
    pub fn floating_muls_eliminated(&self, output_dim: usize, input_dim: usize) -> usize {
        output_dim * input_dim
    }

    /// Fraction of dense multiplies eliminated, in `[0, 1]`.
    pub fn energy_saving_ratio(&self, output_dim: usize, input_dim: usize) -> f64 {
        let dense = reference::dense_mul_count(output_dim, input_dim);
        if dense == 0 {
            return 0.0;
        }
        self.floating_muls_eliminated(output_dim, input_dim) as f64 / dense as f64
    }

    /// Aggregate energy / arithmetic profile of this op count (F06046,
    /// F06067-F06070, R12107-R12110 — the dump's energy monitor).
    ///
    /// `dense_inner_muls` is the inner-product multiply count a dense GEMM of
    /// the same shape(s) would spend and BitLinear eliminated — i.e.
    /// `Σ output_dim · input_dim` over every layer that contributed to this
    /// count (use [`BitLinearLayer::output_dim`]·`input_dim` for one layer,
    /// or `BitLinearMlp::floating_muls_eliminated` for a block). The report
    /// composes across a whole FFN, not just one projection.
    pub fn energy_report(&self, dense_inner_muls: usize) -> EnergyReport {
        let weights = self.adds + self.subs + self.skips;
        let dense_total = dense_inner_muls + self.float_muls;
        EnergyReport {
            adds: self.adds,
            subs: self.subs,
            skips: self.skips,
            float_muls: self.float_muls,
            muls_eliminated: dense_inner_muls,
            energy_saving_ratio: if dense_total == 0 {
                0.0
            } else {
                dense_inner_muls as f64 / dense_total as f64
            },
            sparsity: if weights == 0 {
                0.0
            } else {
                self.skips as f64 / weights as f64
            },
        }
    }
}

/// The energy / arithmetic profile of a (possibly multi-layer) ternary
/// forward — the dump's energy monitor (F06046, F06067-F06070).
///
/// The headline numbers are [`EnergyReport::muls_eliminated`] (the
/// floating-point inner-product multiplies a dense GEMM would have spent and
/// BitLinear did not) and [`EnergyReport::energy_saving_ratio`] (the fraction
/// of all the GEMM's multiplies removed). [`EnergyReport::sparsity`] is the
/// share of weights that were `0` (skipped entirely — free), the structural
/// saving on top of the multiplication-free property.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct EnergyReport {
    /// `+1` weights — activations added.
    pub adds: usize,
    /// `-1` weights — activations subtracted.
    pub subs: usize,
    /// `0` weights — skipped, no arithmetic at all.
    pub skips: usize,
    /// Floating-point multiplies actually performed (the per-output scales).
    pub float_muls: usize,
    /// Inner-product multiplies a dense GEMM would have done and BitLinear
    /// eliminated.
    pub muls_eliminated: usize,
    /// Fraction of the dense GEMM's total multiplies removed, in `[0, 1]`.
    pub energy_saving_ratio: f64,
    /// Fraction of weights that were `0` and skipped entirely, in `[0, 1]`.
    pub sparsity: f64,
}

/// A ternary linear projection layer (F06078).
///
/// Stores weights packed (never as floats) and runs the forward pass
/// directly on the packed ternary codes — no de-quantization back to
/// floating point at execution (F06059).
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct BitLinearLayer {
    /// Schema version of the serialized layer.
    pub schema_version: String,
    /// Number of input features.
    pub input_dim: usize,
    /// Number of output features.
    pub output_dim: usize,
    /// Packing scheme for [`BitLinearLayer::packed`].
    pub packing: Packing,
    /// Packed ternary weights, `output_dim × input_dim` trits, row-major.
    pub packed: Vec<u8>,
    /// Per-tensor absmean scale `γ`.
    pub scale: f32,
}

impl BitLinearLayer {
    /// Build a layer from a real-valued weight matrix (`output_dim ×
    /// input_dim`, row-major) by absmean-quantizing then packing.
    pub fn from_weights(
        weights: &[f32],
        output_dim: usize,
        input_dim: usize,
        packing: Packing,
    ) -> Result<Self, BitLinearError> {
        let expected = output_dim * input_dim;
        if weights.len() != expected {
            return Err(BitLinearError::ShapeMismatch {
                got: weights.len(),
                expected,
            });
        }
        let (trits, scale) = quantize_absmean(weights);
        Ok(Self {
            schema_version: SCHEMA_VERSION.to_string(),
            input_dim,
            output_dim,
            packing,
            packed: pack::pack(&trits, packing),
            scale,
        })
    }

    /// Build directly from already-ternary weights and a known scale.
    pub fn from_trits(
        trits: &[Trit],
        scale: f32,
        output_dim: usize,
        input_dim: usize,
        packing: Packing,
    ) -> Result<Self, BitLinearError> {
        let expected = output_dim * input_dim;
        if trits.len() != expected {
            return Err(BitLinearError::ShapeMismatch {
                got: trits.len(),
                expected,
            });
        }
        Ok(Self {
            schema_version: SCHEMA_VERSION.to_string(),
            input_dim,
            output_dim,
            packing,
            packed: pack::pack(trits, packing),
            scale,
        })
    }

    /// Recover the ternary weights from the packed buffer.
    pub fn trits(&self) -> Result<Vec<Trit>, BitLinearError> {
        pack::unpack(&self.packed, self.output_dim * self.input_dim, self.packing)
    }

    /// Multiplication-free forward pass (F06042-F06045, F06052).
    ///
    /// `y[o] = scale · Σ_i (±x[i] | skip)`. The inner sum uses only
    /// conditional add/sub; the sole multiply per output is the final
    /// scale. Returns the output vector and the [`OpCount`].
    ///
    /// For finite inputs this is bit-for-bit identical to
    /// [`reference::dense_forward`] on the same weights — multiplying by
    /// `±1.0` is exact, so removing the multiply changes nothing.
    pub fn forward(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        if x.len() != self.input_dim {
            return Err(BitLinearError::InputMismatch {
                got: x.len(),
                expected: self.input_dim,
            });
        }
        let trits = self.trits()?;
        let mut y = vec![0.0f32; self.output_dim];
        let mut ops = OpCount::default();
        for o in 0..self.output_dim {
            let row = &trits[o * self.input_dim..(o + 1) * self.input_dim];
            let mut acc = 0.0f32;
            for (t, &xi) in row.iter().zip(x.iter()) {
                match t {
                    Trit::Plus => {
                        acc += xi;
                        ops.adds += 1;
                    }
                    Trit::Minus => {
                        acc -= xi;
                        ops.subs += 1;
                    }
                    Trit::Zero => ops.skips += 1,
                }
            }
            y[o] = self.scale * acc;
            ops.float_muls += 1;
        }
        Ok((y, ops))
    }

    /// Bits per parameter this layer actually spends on weights.
    pub fn bits_per_param(&self) -> f64 {
        pack::bits_per_param(self.packing, self.output_dim * self.input_dim)
    }

    /// Multiplication-free forward operating **directly on the 2-bit packed
    /// codes** — a single pass over the packed bytes with no intermediate
    /// `Vec<Trit>` materialized (F06060-F06062, "no de-quantization,
    /// single-pass through CPU registers").
    ///
    /// Each weight is a 2-bit code read in place — `01`→add, `10`→subtract,
    /// `00`→skip — exactly the per-element decision an AVX-512 lookup-table
    /// matmul vectorizes across a register lane. This scalar form is the
    /// correctness foundation that SIMD path must reproduce; it returns
    /// bit-for-bit the same `(y, OpCount)` as [`BitLinearLayer::forward`].
    ///
    /// Requires [`Packing::TwoBit`] (the byte-aligned packing the LUT path
    /// targets); other packings return
    /// [`BitLinearError::PackedForwardUnsupported`].
    pub fn forward_packed(&self, x: &[f32]) -> Result<(Vec<f32>, OpCount), BitLinearError> {
        if self.packing != Packing::TwoBit {
            return Err(BitLinearError::PackedForwardUnsupported {
                packing: self.packing,
            });
        }
        if x.len() != self.input_dim {
            return Err(BitLinearError::InputMismatch {
                got: x.len(),
                expected: self.input_dim,
            });
        }
        let mut y = vec![0.0f32; self.output_dim];
        let mut ops = OpCount::default();
        for o in 0..self.output_dim {
            let row_start = o * self.input_dim;
            let mut acc = 0.0f32;
            for (i, &xi) in x.iter().enumerate() {
                let idx = row_start + i;
                // 4 trits per byte, 2 bits each, low-order first.
                let code = (self.packed[idx / 4] >> ((idx % 4) * 2)) & 0b11;
                match code {
                    1 => {
                        acc += xi;
                        ops.adds += 1;
                    }
                    2 => {
                        acc -= xi;
                        ops.subs += 1;
                    }
                    _ => ops.skips += 1, // 0 → Zero, skipped
                }
            }
            y[o] = self.scale * acc;
            ops.float_muls += 1;
        }
        Ok((y, ops))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn forward_matches_dense_reference() {
        // Deterministic pseudo-random finite weights + activations.
        let (output_dim, input_dim) = (7, 11);
        let n = output_dim * input_dim;
        let mut state = 0x2545_f491_4f6c_dd1du64;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            // map to roughly [-4, 4)
            ((state >> 40) as f32 / 0x10_0000 as f32) * 8.0 - 4.0
        };
        let weights: Vec<f32> = (0..n).map(|_| next()).collect();
        let x: Vec<f32> = (0..input_dim).map(|_| next()).collect();

        for packing in [Packing::Base3, Packing::TwoBit] {
            let layer = BitLinearLayer::from_weights(&weights, output_dim, input_dim, packing)
                .expect("build");
            let (y, _ops) = layer.forward(&x).expect("forward");

            let trits = layer.trits().unwrap();
            let reference = reference::dense_forward(&trits, layer.scale, input_dim, &x);

            // Bit-for-bit: ±1.0 multiplies are exact.
            assert_eq!(y, reference, "mismatch under {packing:?}");
        }
    }

    #[test]
    fn forward_eliminates_inner_multiplies() {
        let (output_dim, input_dim) = (4, 8);
        let weights = vec![0.5f32; output_dim * input_dim];
        let layer =
            BitLinearLayer::from_weights(&weights, output_dim, input_dim, Packing::Base3).unwrap();
        let x = vec![1.0f32; input_dim];
        let (_y, ops) = layer.forward(&x).unwrap();

        // Only output_dim float multiplies (the scales) ever happen.
        assert_eq!(ops.float_muls, output_dim);
        // The inner products that a dense GEMM would multiply:
        assert_eq!(
            ops.floating_muls_eliminated(output_dim, input_dim),
            output_dim * input_dim
        );
        // adds + subs + skips accounts for every weight.
        assert_eq!(ops.adds + ops.subs + ops.skips, output_dim * input_dim);
    }

    #[test]
    fn energy_saving_is_high() {
        let ops = OpCount::default();
        // 1024x1024 layer: eliminated/(elim+1024) ~ 0.999.
        let r = ops.energy_saving_ratio(1024, 1024);
        assert!(r > 0.999, "got {r}");
    }

    #[test]
    fn shape_mismatch_rejected() {
        let err = BitLinearLayer::from_weights(&[1.0, 2.0], 2, 2, Packing::Base3).unwrap_err();
        assert!(matches!(err, BitLinearError::ShapeMismatch { .. }));
    }

    #[test]
    fn input_mismatch_rejected() {
        let layer = BitLinearLayer::from_weights(&[1.0; 6], 2, 3, Packing::Base3).unwrap();
        let err = layer.forward(&[1.0, 2.0]).unwrap_err();
        assert!(matches!(err, BitLinearError::InputMismatch { .. }));
    }

    #[test]
    fn serde_round_trip() {
        let layer =
            BitLinearLayer::from_weights(&[1.0, -1.0, 0.2, -0.2], 2, 2, Packing::TwoBit).unwrap();
        let json = serde_json::to_string(&layer).unwrap();
        let back: BitLinearLayer = serde_json::from_str(&json).unwrap();
        assert_eq!(layer, back);
    }

    #[test]
    fn packed_forward_matches_forward() {
        // The single-pass packed-domain forward must equal the unpack-then-
        // loop forward bit-for-bit, including the OpCount.
        let (output_dim, input_dim) = (9, 13);
        let n = output_dim * input_dim;
        let mut state = 0x1234_5678_9abc_def0u64;
        let mut next = || {
            state ^= state << 13;
            state ^= state >> 7;
            state ^= state << 17;
            ((state >> 40) as f32 / 0x10_0000 as f32) * 8.0 - 4.0
        };
        let weights: Vec<f32> = (0..n).map(|_| next()).collect();
        let x: Vec<f32> = (0..input_dim).map(|_| next()).collect();

        let layer = BitLinearLayer::from_weights(&weights, output_dim, input_dim, Packing::TwoBit)
            .expect("build");
        let (y_ref, ops_ref) = layer.forward(&x).expect("forward");
        let (y_packed, ops_packed) = layer.forward_packed(&x).expect("packed");

        assert_eq!(y_packed, y_ref, "packed forward diverged from forward");
        assert_eq!(ops_packed, ops_ref, "packed OpCount diverged");
    }

    #[test]
    fn packed_forward_rejects_base3() {
        let layer = BitLinearLayer::from_weights(&[1.0; 6], 2, 3, Packing::Base3).unwrap();
        let err = layer.forward_packed(&[1.0, 2.0, 3.0]).unwrap_err();
        assert!(matches!(
            err,
            BitLinearError::PackedForwardUnsupported {
                packing: Packing::Base3
            }
        ));
    }

    #[test]
    fn packed_forward_input_mismatch_rejected() {
        let layer = BitLinearLayer::from_weights(&[1.0; 6], 2, 3, Packing::TwoBit).unwrap();
        let err = layer.forward_packed(&[1.0, 2.0]).unwrap_err();
        assert!(matches!(err, BitLinearError::InputMismatch { .. }));
    }

    #[test]
    fn energy_report_accounts_a_single_layer() {
        // 4×8 layer of all-0.5 weights → all +1 trits (absmean = 0.5).
        let (output_dim, input_dim) = (4, 8);
        let layer = BitLinearLayer::from_weights(
            &vec![0.5f32; output_dim * input_dim],
            output_dim,
            input_dim,
            Packing::Base3,
        )
        .unwrap();
        let (_y, ops) = layer.forward(&vec![1.0f32; input_dim]).unwrap();
        let r = ops.energy_report(output_dim * input_dim);

        assert_eq!(r.muls_eliminated, output_dim * input_dim); // 32 inner muls removed
        assert_eq!(r.float_muls, output_dim); // only the 4 per-row scales
        // ratio = 32 / (32 + 4) = 0.888…
        assert!((r.energy_saving_ratio - 32.0 / 36.0).abs() < 1e-12);
        // all weights non-zero here → zero sparsity.
        assert_eq!(r.sparsity, 0.0);
        assert_eq!(r.adds, output_dim * input_dim);
    }

    #[test]
    fn energy_report_measures_sparsity() {
        // Half-zero weights → ~50% skips. Row of [0, 0, 1, 1] pattern.
        let weights = [0.0f32, 0.0, 1.0, 1.0, 0.0, 0.0, 1.0, 1.0];
        let layer = BitLinearLayer::from_weights(&weights, 2, 4, Packing::Base3).unwrap();
        let (_y, ops) = layer.forward(&[1.0f32; 4]).unwrap();
        let r = ops.energy_report(2 * 4);
        // 4 of 8 weights are zero → sparsity 0.5.
        assert_eq!(r.skips, 4);
        assert_eq!(r.sparsity, 0.5);
    }

    #[test]
    fn energy_report_is_serializable() {
        let ops = OpCount {
            adds: 10,
            subs: 5,
            skips: 1,
            float_muls: 2,
        };
        let r = ops.energy_report(64);
        let json = serde_json::to_string(&r).unwrap();
        let back: EnergyReport = serde_json::from_str(&json).unwrap();
        // Integer fields round-trip exactly; the f64 ratios within one ULP
        // (JSON's decimal text loses the last bit of an f64).
        assert_eq!(r.adds, back.adds);
        assert_eq!(r.subs, back.subs);
        assert_eq!(r.skips, back.skips);
        assert_eq!(r.float_muls, back.float_muls);
        assert_eq!(r.muls_eliminated, back.muls_eliminated);
        assert!((r.energy_saving_ratio - back.energy_saving_ratio).abs() < 1e-12);
        assert!((r.sparsity - back.sparsity).abs() < 1e-12);
    }
}
