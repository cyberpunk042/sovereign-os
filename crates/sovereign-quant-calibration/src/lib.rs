//! `sovereign-quant-calibration` — per-layer mixed-precision assignment.
//!
//! Low-precision inference is only free if it doesn't break accuracy, and
//! *which* layers tolerate which precision is an empirical question — a weight
//! matrix of near-uniform magnitudes barely notices ternary quantization,
//! while a high-dynamic-range one needs NVFP4 or f32. This crate answers it by
//! measurement: for a given weight matrix and a set of representative inputs,
//! it runs the [`Linear`] forward at each precision, compares against the f32
//! reference output, and reports the error. [`recommend`] then picks the
//! **lowest-bit precision that stays within an error budget** — the
//! mixed-precision layer-assignment a sovereign runtime makes to push as much
//! work as possible onto the cheap ternary/NVFP4 kernels.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_linear::{Linear, LinearError, Precision};
use thiserror::Error;

/// Schema version of the calibration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The precisions, ordered cheapest-bits first.
pub const PRECISIONS_BY_COST: [Precision; 3] =
    [Precision::Ternary, Precision::Nvfp4, Precision::F32];

/// Things that can go wrong calibrating.
#[derive(Debug, Error, PartialEq)]
pub enum CalibrationError {
    /// No representative inputs were supplied.
    #[error("calibration needs at least one input vector")]
    NoInputs,
    /// A linear-layer error from building or running a precision.
    #[error("linear: {0}")]
    Linear(#[from] LinearError),
}

/// Error metrics for one precision relative to the f32 reference output.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct PrecisionReport {
    /// Which precision this measures.
    pub precision: Precision,
    /// Effective bits stored per weight parameter.
    pub bits_per_param: f64,
    /// Mean absolute error per output element across all inputs.
    pub mean_abs_error: f64,
    /// Largest absolute error of any output element across all inputs.
    pub max_abs_error: f64,
    /// Aggregate relative L2 error `‖Δ‖ / ‖ref‖` over all inputs.
    pub relative_error: f64,
    /// Mean per-input cosine similarity to the reference output.
    pub cosine_similarity: f64,
}

/// Measure every precision against the f32 reference for `weights` over
/// `inputs`. Each input must have length `input_dim`.
pub fn calibrate(
    weights: &[f32],
    output_dim: usize,
    input_dim: usize,
    inputs: &[Vec<f32>],
) -> Result<Vec<PrecisionReport>, CalibrationError> {
    if inputs.is_empty() {
        return Err(CalibrationError::NoInputs);
    }
    // f32 reference outputs.
    let reference = Linear::from_f32(weights, output_dim, input_dim, Precision::F32)?;
    let refs: Vec<Vec<f32>> = inputs
        .iter()
        .map(|x| reference.forward(x))
        .collect::<Result<_, _>>()?;

    let mut reports = Vec::with_capacity(PRECISIONS_BY_COST.len());
    for &precision in &PRECISIONS_BY_COST {
        let layer = Linear::from_f32(weights, output_dim, input_dim, precision)?;

        let mut abs_sum = 0.0f64;
        let mut abs_count = 0usize;
        let mut max_abs = 0.0f64;
        let mut sq_err = 0.0f64; // Σ‖Δ‖²
        let mut sq_ref = 0.0f64; // Σ‖ref‖²
        let mut cos_sum = 0.0f64;
        let mut cos_count = 0usize;

        for (x, r) in inputs.iter().zip(&refs) {
            let y = layer.forward(x)?;
            let mut dot = 0.0f64;
            let mut ny = 0.0f64;
            let mut nr = 0.0f64;
            for (yi, ri) in y.iter().zip(r) {
                let d = (*yi as f64) - (*ri as f64);
                abs_sum += d.abs();
                abs_count += 1;
                if d.abs() > max_abs {
                    max_abs = d.abs();
                }
                sq_err += d * d;
                sq_ref += (*ri as f64) * (*ri as f64);
                dot += (*yi as f64) * (*ri as f64);
                ny += (*yi as f64) * (*yi as f64);
                nr += (*ri as f64) * (*ri as f64);
            }
            if ny > 0.0 && nr > 0.0 {
                cos_sum += dot / (ny.sqrt() * nr.sqrt());
                cos_count += 1;
            }
        }

        reports.push(PrecisionReport {
            precision,
            bits_per_param: layer.bits_per_param(),
            mean_abs_error: if abs_count > 0 {
                abs_sum / abs_count as f64
            } else {
                0.0
            },
            max_abs_error: max_abs,
            relative_error: if sq_ref > 0.0 {
                (sq_err / sq_ref).sqrt()
            } else {
                0.0
            },
            cosine_similarity: if cos_count > 0 {
                cos_sum / cos_count as f64
            } else {
                1.0
            },
        });
    }
    Ok(reports)
}

/// Recommend the cheapest precision whose relative L2 error is within
/// `budget`. F32 (relative error 0) is always a valid fallback.
pub fn recommend(
    weights: &[f32],
    output_dim: usize,
    input_dim: usize,
    inputs: &[Vec<f32>],
    budget: f64,
) -> Result<Precision, CalibrationError> {
    let reports = calibrate(weights, output_dim, input_dim, inputs)?;
    // reports are already cheapest-first; pick the first within budget.
    for r in &reports {
        if r.relative_error <= budget {
            return Ok(r.precision);
        }
    }
    Ok(Precision::F32)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn ones_inputs(n: usize, dim: usize) -> Vec<Vec<f32>> {
        (0..n)
            .map(|k| {
                (0..dim)
                    .map(|i| ((i + k) as f32 * 0.1).sin() + 0.5)
                    .collect()
            })
            .collect()
    }

    #[test]
    fn reports_cover_all_precisions_cheapest_first() {
        let w: Vec<f32> = (0..64).map(|i| (i as f32 * 0.05).sin()).collect();
        let reps = calibrate(&w, 4, 16, &ones_inputs(3, 16)).unwrap();
        assert_eq!(reps.len(), 3);
        assert_eq!(reps[0].precision, Precision::Ternary);
        assert_eq!(reps[1].precision, Precision::Nvfp4);
        assert_eq!(reps[2].precision, Precision::F32);
        // bits per param strictly increase with the cost ordering
        assert!(reps[0].bits_per_param < reps[1].bits_per_param);
        assert!(reps[1].bits_per_param < reps[2].bits_per_param);
    }

    #[test]
    fn f32_has_zero_error_and_unit_cosine() {
        let w: Vec<f32> = (0..32).map(|i| (i as f32 * 0.3).cos()).collect();
        let reps = calibrate(&w, 2, 16, &ones_inputs(4, 16)).unwrap();
        let f32_rep = reps.iter().find(|r| r.precision == Precision::F32).unwrap();
        assert!(f32_rep.relative_error < 1e-6);
        assert!(f32_rep.max_abs_error < 1e-4);
        assert!((f32_rep.cosine_similarity - 1.0).abs() < 1e-6);
    }

    #[test]
    fn error_metrics_are_non_negative() {
        let w: Vec<f32> = (0..48).map(|i| (i as f32 * 0.07).sin() * 3.0).collect();
        let reps = calibrate(&w, 3, 16, &ones_inputs(5, 16)).unwrap();
        for r in &reps {
            assert!(r.mean_abs_error >= 0.0);
            assert!(r.max_abs_error >= 0.0);
            assert!(r.relative_error >= 0.0);
            assert!(r.cosine_similarity <= 1.0 + 1e-6);
        }
    }

    #[test]
    fn uniform_magnitude_weights_let_ternary_win() {
        // All |w| equal → ternary is an (almost) exact reconstruction, so a
        // modest budget should pick the cheapest precision: ternary.
        let w: Vec<f32> = (0..64)
            .map(|i| if i % 2 == 0 { 0.5 } else { -0.5 })
            .collect();
        let inputs = ones_inputs(4, 16);
        let reps = calibrate(&w, 4, 16, &inputs).unwrap();
        let tern = reps
            .iter()
            .find(|r| r.precision == Precision::Ternary)
            .unwrap();
        assert!(
            tern.relative_error < 1e-3,
            "ternary rel err {}",
            tern.relative_error
        );
        assert_eq!(
            recommend(&w, 4, 16, &inputs, 0.01).unwrap(),
            Precision::Ternary
        );
    }

    #[test]
    fn zero_budget_forces_f32() {
        let w: Vec<f32> = (0..64).map(|i| (i as f32 * 0.05).sin() * 5.0).collect();
        let inputs = ones_inputs(3, 16);
        // budget 0 → only the exact f32 path qualifies
        assert_eq!(recommend(&w, 4, 16, &inputs, 0.0).unwrap(), Precision::F32);
    }

    #[test]
    fn looser_budget_allows_cheaper_precision() {
        // High-dynamic-range weights: ternary likely exceeds a tight budget but
        // a very loose budget admits the cheapest precision.
        let w: Vec<f32> = (0..64).map(|i| (i as f32 * 0.05).sin() * 5.0).collect();
        let inputs = ones_inputs(3, 16);
        let cheap = recommend(&w, 4, 16, &inputs, 100.0).unwrap();
        assert_eq!(cheap, Precision::Ternary); // any error fits a huge budget
    }

    #[test]
    fn no_inputs_is_an_error() {
        let w = vec![1.0; 32];
        assert_eq!(
            calibrate(&w, 2, 16, &[]).unwrap_err(),
            CalibrationError::NoInputs
        );
    }

    #[test]
    fn report_serde_round_trip() {
        let w: Vec<f32> = (0..32).map(|i| (i as f32 * 0.1).sin()).collect();
        let reps = calibrate(&w, 2, 16, &ones_inputs(2, 16)).unwrap();
        let j = serde_json::to_string(&reps).unwrap();
        let back: Vec<PrecisionReport> = serde_json::from_str(&j).unwrap();
        assert_eq!(reps.len(), back.len());
        for (a, b) in reps.iter().zip(&back) {
            // precision + bits are exact; the f64 metrics round-trip to ~ULP.
            assert_eq!(a.precision, b.precision);
            assert_eq!(a.bits_per_param, b.bits_per_param);
            assert!((a.relative_error - b.relative_error).abs() < 1e-9);
            assert!((a.cosine_similarity - b.cosine_similarity).abs() < 1e-9);
            assert!((a.mean_abs_error - b.mean_abs_error).abs() < 1e-9);
        }
    }
}
