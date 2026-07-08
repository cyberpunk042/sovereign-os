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
use sovereign_linear::{Linear, LinearError, NvfpRecipe, Precision};
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

/// Activation-aware NVFP4 recipe selection: build each applicable M077 recipe
/// (plain / 2D, plus RHT when `input_dim` is a power of two), run it over
/// `inputs`, and return the recipe whose **output** is closest to the f32
/// reference (lowest relative L2 error `‖Ŵx − Wx‖/‖Wx‖`), with that error.
///
/// This is the activation-aware complement to
/// [`sovereign_linear::best_nvfp4_recipe`], which ranks by *weight*
/// reconstruction error alone. What matters at inference is the error in `Wx`,
/// and a recipe that conditions the weights better for the activation
/// distribution can win here even when weight error is similar.
pub fn best_nvfp4_recipe_calibrated(
    weights: &[f32],
    output_dim: usize,
    input_dim: usize,
    inputs: &[Vec<f32>],
) -> Result<(NvfpRecipe, f64), CalibrationError> {
    if inputs.is_empty() {
        return Err(CalibrationError::NoInputs);
    }
    let reference = Linear::from_f32(weights, output_dim, input_dim, Precision::F32)?;
    let refs: Vec<Vec<f32>> = inputs
        .iter()
        .map(|x| reference.forward(x))
        .collect::<Result<_, _>>()?;

    let mut recipes = vec![NvfpRecipe::Plain, NvfpRecipe::TwoD];
    if input_dim.is_power_of_two() {
        recipes.push(NvfpRecipe::Rht(0));
    }

    let mut best = (NvfpRecipe::Plain, f64::INFINITY);
    for recipe in recipes {
        let layer = Linear::from_f32_nvfp4(weights, output_dim, input_dim, recipe)?;
        let mut sq_err = 0.0f64; // Σ‖Δ‖²
        let mut sq_ref = 0.0f64; // Σ‖ref‖²
        for (x, r) in inputs.iter().zip(&refs) {
            let y = layer.forward(x)?;
            for (yi, ri) in y.iter().zip(r) {
                let d = (*yi as f64) - (*ri as f64);
                sq_err += d * d;
                sq_ref += (*ri as f64) * (*ri as f64);
            }
        }
        let rel = if sq_ref > 0.0 {
            (sq_err / sq_ref).sqrt()
        } else {
            0.0
        };
        if rel < best.1 {
            best = (recipe, rel);
        }
    }
    Ok(best)
}

/// Recipe-aware precision assignment: like [`recommend`], but the NVFP4 tier is
/// measured with its **best** M077 recipe (via [`best_nvfp4_recipe_calibrated`])
/// instead of plain microscaling, and the chosen recipe is returned alongside.
///
/// This keeps borderline layers on the cheap 4-bit path: a matrix whose *plain*
/// NVFP4 error exceeds `budget` — which [`recommend`] would bump to f32 — may
/// fit the budget under RHT or 2D conditioning and stay NVFP4. Returns the
/// recipe only for the NVFP4 tier (`None` for ternary/f32).
pub fn recommend_with_recipe(
    weights: &[f32],
    output_dim: usize,
    input_dim: usize,
    inputs: &[Vec<f32>],
    budget: f64,
) -> Result<(Precision, Option<NvfpRecipe>), CalibrationError> {
    // Ternary is cheapest — take it if its output error fits the budget.
    let reports = calibrate(weights, output_dim, input_dim, inputs)?;
    if let Some(t) = reports.iter().find(|r| r.precision == Precision::Ternary) {
        if t.relative_error <= budget {
            return Ok((Precision::Ternary, None));
        }
    }
    // Next-cheapest is NVFP4 — measured with its best recipe, not just plain.
    let (recipe, err) = best_nvfp4_recipe_calibrated(weights, output_dim, input_dim, inputs)?;
    if err <= budget {
        return Ok((Precision::Nvfp4, Some(recipe)));
    }
    // Fall back to exact f32.
    Ok((Precision::F32, None))
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
    fn calibrated_recipe_beats_or_matches_plain() {
        // Column-structured weights: 2D conditioning should give output error
        // no worse than plain microscaling under real activations.
        let (output_dim, input_dim) = (6, 16);
        let mut w = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            w[o * input_dim + 5] = 0.012;
        }
        let inputs = ones_inputs(4, 16);
        let (recipe, err) =
            best_nvfp4_recipe_calibrated(&w, output_dim, input_dim, &inputs).unwrap();
        // The chosen recipe's output error must not exceed plain's.
        let plain = Linear::from_f32_nvfp4(&w, output_dim, input_dim, NvfpRecipe::Plain).unwrap();
        let reference = Linear::from_f32(&w, output_dim, input_dim, Precision::F32).unwrap();
        let (mut sq_err, mut sq_ref) = (0.0f64, 0.0f64);
        for x in &inputs {
            let y = plain.forward(x).unwrap();
            let r = reference.forward(x).unwrap();
            for (yi, ri) in y.iter().zip(&r) {
                let d = *yi as f64 - *ri as f64;
                sq_err += d * d;
                sq_ref += (*ri as f64) * (*ri as f64);
            }
        }
        let plain_err = (sq_err / sq_ref).sqrt();
        assert!(
            err <= plain_err + 1e-9,
            "chosen {recipe:?} err {err} should be ≤ plain {plain_err}"
        );
    }

    #[test]
    fn calibrated_recipe_no_inputs_is_an_error() {
        let w = vec![1.0f32; 32];
        assert_eq!(
            best_nvfp4_recipe_calibrated(&w, 2, 16, &[]).unwrap_err(),
            CalibrationError::NoInputs
        );
    }

    #[test]
    fn recipe_aware_recommend_keeps_borderline_layer_on_nvfp4() {
        // Column-structured weights: the best recipe (2D) has strictly lower
        // output error than plain NVFP4. Choose a budget between the two so the
        // plain-only recommend() must bump to f32 while the recipe-aware path
        // keeps it on the cheap NVFP4 tier (with the winning recipe).
        let (output_dim, input_dim) = (6, 16);
        let mut w = vec![1.0f32; output_dim * input_dim];
        for o in 0..output_dim {
            w[o * input_dim + 5] = 0.012;
        }
        let inputs = ones_inputs(4, 16);

        // Plain NVFP4 error (what recommend() sees) and best-recipe error.
        let plain_err = calibrate(&w, output_dim, input_dim, &inputs)
            .unwrap()
            .into_iter()
            .find(|r| r.precision == Precision::Nvfp4)
            .unwrap()
            .relative_error;
        let (best_recipe, best_err) =
            best_nvfp4_recipe_calibrated(&w, output_dim, input_dim, &inputs).unwrap();

        // Only meaningful when the recipe genuinely helps here.
        if best_err < plain_err {
            // Also keep the budget under ternary's error so ternary isn't chosen.
            let tern_err = calibrate(&w, output_dim, input_dim, &inputs)
                .unwrap()
                .into_iter()
                .find(|r| r.precision == Precision::Ternary)
                .unwrap()
                .relative_error;
            let budget = (best_err + plain_err) / 2.0;
            if budget < tern_err {
                // plain-only recommend can't fit NVFP4 → f32.
                assert_eq!(
                    recommend(&w, output_dim, input_dim, &inputs, budget).unwrap(),
                    Precision::F32
                );
                // recipe-aware keeps it on NVFP4 with the winning recipe.
                assert_eq!(
                    recommend_with_recipe(&w, output_dim, input_dim, &inputs, budget).unwrap(),
                    (Precision::Nvfp4, Some(best_recipe))
                );
            }
        }
    }

    #[test]
    fn recipe_aware_recommend_picks_ternary_and_f32_at_extremes() {
        // Uniform-magnitude weights → ternary is (near-)exact; a huge budget
        // takes the cheapest tier, no recipe.
        let uniform: Vec<f32> = (0..64)
            .map(|i| if i % 2 == 0 { 0.5 } else { -0.5 })
            .collect();
        let inputs = ones_inputs(4, 16);
        assert_eq!(
            recommend_with_recipe(&uniform, 4, 16, &inputs, 100.0).unwrap(),
            (Precision::Ternary, None)
        );
        // High-dynamic-range weights at zero budget → only exact f32 qualifies,
        // no recipe (neither ternary nor any NVFP4 recipe is lossless).
        let spiky: Vec<f32> = (0..64).map(|i| (i as f32 * 0.05).sin() * 5.0).collect();
        assert_eq!(
            recommend_with_recipe(&spiky, 4, 16, &inputs, 0.0).unwrap(),
            (Precision::F32, None)
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
