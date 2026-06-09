//! `sovereign-hrm-runtime` — M080 HRM (Hierarchical Reasoning Model) runtime.
//!
//! Per arXiv 2506.21734 + `sapientinc/HRM-Text-1B`, HRM is a **fourth
//! architectural class** alongside Transformer / Mamba / BitNet:
//!
//! - **High-level module** — slow, abstract planning loop.
//! - **Low-level module** — fast, detailed computation loop.
//! - **Two-timescale recurrence**: high-level steps are interleaved
//!   with multiple low-level inner steps per outer step.
//! - **Single forward pass** — no explicit CoT supervision; reasoning
//!   emerges from the interleaved recurrence.
//! - **27M-parameter canonical HRM** achieves near-perfect Sudoku +
//!   maze solving + ARC-AGI on 1000 training samples.
//! - **1.18B-parameter HRM-Text-1B** scales the design to text gen.
//!
//! This runtime catalogues the architecture's invariants + a CPU
//! reference impl for verification + scaffolding to bridge to a CUDA
//! backend. Per operator standing direction "you cannot invent crap":
//! we catalogue the published architecture, we do not invent variants.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the HRM runtime configuration surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Canonical HRM parameter count from arXiv 2506.21734 §3.
pub const HRM_CANONICAL_PARAMS: u64 = 27_000_000;

/// HRM-Text-1B parameter count from sapientinc/HRM-Text-1B model card.
pub const HRM_TEXT_1B_PARAMS: u64 = 1_182_800_000;

/// TRM 7M-parameter variant (follow-up to HRM, mentioned in M080).
pub const TRM_PARAMS: u64 = 7_000_000;

/// One of the published HRM variants.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum HrmVariant {
    /// Canonical 27M-parameter HRM per arXiv 2506.21734.
    #[serde(rename = "hrm-canonical")]
    HrmCanonical,
    /// 1.18B-parameter sapientinc/HRM-Text-1B.
    #[serde(rename = "hrm-text-1b")]
    HrmText1B,
    /// 7M-parameter TRM follow-up variant.
    #[serde(rename = "trm-7m")]
    Trm7M,
}

impl HrmVariant {
    /// Approximate parameter count.
    pub fn approx_params(self) -> u64 {
        match self {
            HrmVariant::HrmCanonical => HRM_CANONICAL_PARAMS,
            HrmVariant::HrmText1B => HRM_TEXT_1B_PARAMS,
            HrmVariant::Trm7M => TRM_PARAMS,
        }
    }
}

/// HRM runtime configuration.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct HrmConfig {
    /// Schema version. Must equal [`SCHEMA_VERSION`].
    pub schema_version: String,
    /// Variant identifier.
    pub variant: HrmVariant,
    /// Number of outer (high-level) steps per forward pass.
    pub outer_steps: u32,
    /// Number of inner (low-level) steps per outer step.
    pub inner_steps_per_outer: u32,
    /// High-level module hidden dim.
    pub high_level_dim: u32,
    /// Low-level module hidden dim.
    pub low_level_dim: u32,
    /// Number of HRM blocks (stacked).
    pub num_blocks: u32,
    /// Vocab size (for text variants).
    pub vocab_size: u32,
}

impl HrmConfig {
    /// Construct a canonical-HRM-shaped config (27M params, Sudoku/ARC).
    pub fn canonical() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            variant: HrmVariant::HrmCanonical,
            outer_steps: 8,
            inner_steps_per_outer: 4,
            high_level_dim: 256,
            low_level_dim: 512,
            num_blocks: 2,
            vocab_size: 0,
        }
    }

    /// Construct an HRM-Text-1B-shaped config.
    pub fn text_1b() -> Self {
        Self {
            schema_version: SCHEMA_VERSION.into(),
            variant: HrmVariant::HrmText1B,
            outer_steps: 16,
            inner_steps_per_outer: 8,
            high_level_dim: 2048,
            low_level_dim: 4096,
            num_blocks: 28,
            vocab_size: 50_277,
        }
    }

    /// Total recurrent step count for one forward pass.
    pub fn total_recurrent_steps(&self) -> u64 {
        self.outer_steps as u64 * self.inner_steps_per_outer as u64
    }
}

/// HRM runtime errors.
#[derive(Debug, Error)]
pub enum HrmError {
    /// Schema version drift.
    #[error("schema version mismatch: expected {expected}, got {actual}")]
    SchemaMismatch {
        /// Expected schema version.
        expected: String,
        /// Observed schema version.
        actual: String,
    },
    /// Outer/inner step count is zero (would skip recurrence entirely).
    #[error("recurrence step count is zero: outer={outer} inner={inner}")]
    ZeroRecurrence {
        /// Outer steps.
        outer: u32,
        /// Inner steps per outer.
        inner: u32,
    },
    /// Configured dims are not aligned with variant expectations.
    #[error("config dim mismatch: high={high} low={low} expected high <= low")]
    DimMismatch {
        /// High-level dim.
        high: u32,
        /// Low-level dim.
        low: u32,
    },
    /// HRM is not a LoRA adaptable architecture per operator standing direction.
    /// Surfaces at the foundry boundary, not in the runtime hot path.
    #[error("HRM does not support LoRA adapters: distinct architecture class")]
    NotLoraCompatible,
}

impl HrmConfig {
    /// Validate config invariants.
    pub fn validate(&self) -> Result<(), HrmError> {
        if self.schema_version != SCHEMA_VERSION {
            return Err(HrmError::SchemaMismatch {
                expected: SCHEMA_VERSION.into(),
                actual: self.schema_version.clone(),
            });
        }
        if self.outer_steps == 0 || self.inner_steps_per_outer == 0 {
            return Err(HrmError::ZeroRecurrence {
                outer: self.outer_steps,
                inner: self.inner_steps_per_outer,
            });
        }
        if self.high_level_dim > self.low_level_dim {
            return Err(HrmError::DimMismatch {
                high: self.high_level_dim,
                low: self.low_level_dim,
            });
        }
        Ok(())
    }
}

/// State tracked across a recurrent forward pass.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub struct RecurrentState {
    /// High-level module hidden state.
    pub high_level: Vec<f32>,
    /// Low-level module hidden state.
    pub low_level: Vec<f32>,
    /// Current outer step (0..outer_steps).
    pub outer_step: u32,
    /// Current inner step within current outer (0..inner_steps_per_outer).
    pub inner_step: u32,
}

impl RecurrentState {
    /// Initialise state to zeros for a config.
    pub fn zeros(config: &HrmConfig) -> Self {
        Self {
            high_level: vec![0.0; config.high_level_dim as usize],
            low_level: vec![0.0; config.low_level_dim as usize],
            outer_step: 0,
            inner_step: 0,
        }
    }
}

/// Hard safety cap on driver iterations, independent of config cadence.
pub const MAX_HRM_STEPS: u64 = 1 << 24;

/// Outcome of driving the recurrent loop to completion.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct HrmRun {
    /// Total inner-step ticks executed.
    pub steps: u64,
    /// Outer step the state reached.
    pub outer_reached: u32,
    /// True if an ACT halt predicate stopped the loop before the cadence end.
    pub halted_early: bool,
}

/// Stepper for the HRM two-timescale loop. CPU reference impl.
/// Reference math omitted — this struct exposes the iteration cadence
/// so downstream impls (CUDA kernel, ROCm kernel) can mirror it.
pub struct HrmStepper<'c> {
    config: &'c HrmConfig,
}

impl<'c> HrmStepper<'c> {
    /// Construct stepper, validating config.
    pub fn new(config: &'c HrmConfig) -> Result<Self, HrmError> {
        config.validate()?;
        Ok(Self { config })
    }

    /// Whether the loop should continue. Returns false after the final
    /// outer step's final inner step.
    pub fn should_continue(&self, state: &RecurrentState) -> bool {
        state.outer_step < self.config.outer_steps
    }

    /// Advance state by one inner-step tick (caller supplies the
    /// per-step computation; this method only manages cadence).
    pub fn advance(&self, state: &mut RecurrentState) {
        state.inner_step += 1;
        if state.inner_step >= self.config.inner_steps_per_outer {
            state.inner_step = 0;
            state.outer_step += 1;
        }
    }

    /// Drive the fixed two-timescale cadence to completion — the HRM
    /// "single forward pass". Returns the run summary; the number of steps
    /// equals [`HrmConfig::total_recurrent_steps`].
    pub fn run(&self, state: &mut RecurrentState) -> HrmRun {
        self.run_with_halt(state, |_| false)
    }

    /// Drive the loop with an ACT-style early-halt predicate (adaptive
    /// computation depth): stop as soon as `halt(state)` is true, otherwise
    /// run the full cadence. The predicate is the caller's convergence test
    /// — consistent with `advance` leaving the per-step math to the caller.
    pub fn run_with_halt(
        &self,
        state: &mut RecurrentState,
        mut halt: impl FnMut(&RecurrentState) -> bool,
    ) -> HrmRun {
        let mut steps = 0u64;
        while self.should_continue(state) {
            if halt(state) {
                return HrmRun {
                    steps,
                    outer_reached: state.outer_step,
                    halted_early: true,
                };
            }
            self.advance(state);
            steps += 1;
            if steps >= MAX_HRM_STEPS {
                break;
            }
        }
        HrmRun {
            steps,
            outer_reached: state.outer_step,
            halted_early: false,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn canonical_config_validates() {
        HrmConfig::canonical().validate().unwrap();
    }

    #[test]
    fn text_1b_config_validates() {
        HrmConfig::text_1b().validate().unwrap();
    }

    #[test]
    fn variant_params_match_constants() {
        assert_eq!(HrmVariant::HrmCanonical.approx_params(), 27_000_000);
        assert_eq!(HrmVariant::HrmText1B.approx_params(), 1_182_800_000);
        assert_eq!(HrmVariant::Trm7M.approx_params(), 7_000_000);
    }

    #[test]
    fn total_recurrent_steps_multiplies() {
        let c = HrmConfig::canonical();
        assert_eq!(c.total_recurrent_steps(), 32); // 8 outer × 4 inner
        let t = HrmConfig::text_1b();
        assert_eq!(t.total_recurrent_steps(), 128); // 16 × 8
    }

    #[test]
    fn zero_recurrence_rejected() {
        let mut c = HrmConfig::canonical();
        c.outer_steps = 0;
        assert!(matches!(
            c.validate().unwrap_err(),
            HrmError::ZeroRecurrence { .. }
        ));
        c.outer_steps = 8;
        c.inner_steps_per_outer = 0;
        assert!(matches!(
            c.validate().unwrap_err(),
            HrmError::ZeroRecurrence { .. }
        ));
    }

    #[test]
    fn dim_mismatch_rejected_when_high_exceeds_low() {
        let mut c = HrmConfig::canonical();
        c.high_level_dim = 1024;
        c.low_level_dim = 256;
        assert!(matches!(
            c.validate().unwrap_err(),
            HrmError::DimMismatch { .. }
        ));
    }

    #[test]
    fn zeros_state_sized_correctly() {
        let c = HrmConfig::canonical();
        let s = RecurrentState::zeros(&c);
        assert_eq!(s.high_level.len(), 256);
        assert_eq!(s.low_level.len(), 512);
        assert_eq!(s.outer_step, 0);
        assert_eq!(s.inner_step, 0);
        assert!(s.high_level.iter().all(|&x| x == 0.0));
    }

    #[test]
    fn stepper_advances_outer_after_inner_rollover() {
        let c = HrmConfig::canonical();
        let stepper = HrmStepper::new(&c).unwrap();
        let mut s = RecurrentState::zeros(&c);
        for _ in 0..4 {
            // 4 inner steps per outer
            stepper.advance(&mut s);
        }
        assert_eq!(s.outer_step, 1);
        assert_eq!(s.inner_step, 0);
    }

    #[test]
    fn stepper_full_loop_completes() {
        let c = HrmConfig::canonical();
        let stepper = HrmStepper::new(&c).unwrap();
        let mut s = RecurrentState::zeros(&c);
        let mut total = 0;
        while stepper.should_continue(&s) {
            stepper.advance(&mut s);
            total += 1;
            if total > 1000 {
                panic!("loop did not terminate");
            }
        }
        assert_eq!(total, 32);
        assert_eq!(s.outer_step, c.outer_steps);
    }

    #[test]
    fn schema_drift_rejected() {
        let mut c = HrmConfig::canonical();
        c.schema_version = "9.9.9".into();
        assert!(matches!(
            c.validate().unwrap_err(),
            HrmError::SchemaMismatch { .. }
        ));
    }

    #[test]
    fn variant_serde_uses_canonical_names() {
        assert_eq!(
            serde_json::to_string(&HrmVariant::HrmCanonical).unwrap(),
            "\"hrm-canonical\""
        );
        assert_eq!(
            serde_json::to_string(&HrmVariant::HrmText1B).unwrap(),
            "\"hrm-text-1b\""
        );
        assert_eq!(
            serde_json::to_string(&HrmVariant::Trm7M).unwrap(),
            "\"trm-7m\""
        );
    }

    #[test]
    fn config_serde_roundtrip() {
        let original = HrmConfig::canonical();
        let j = serde_json::to_string(&original).unwrap();
        let back: HrmConfig = serde_json::from_str(&j).unwrap();
        assert_eq!(original, back);
    }

    #[test]
    fn stepper_rejects_invalid_config() {
        let mut c = HrmConfig::canonical();
        c.outer_steps = 0;
        assert!(HrmStepper::new(&c).is_err());
    }

    // --- driver loop (single forward pass + adaptive halt) ---

    #[test]
    fn run_executes_the_full_cadence() {
        let cfg = HrmConfig::canonical();
        let stepper = HrmStepper::new(&cfg).unwrap();
        let mut state = RecurrentState::zeros(&cfg);
        let run = stepper.run(&mut state);
        assert_eq!(run.steps, cfg.total_recurrent_steps());
        assert!(!run.halted_early);
        assert_eq!(run.outer_reached, cfg.outer_steps);
        // loop is exhausted
        assert!(!stepper.should_continue(&state));
    }

    #[test]
    fn run_with_halt_stops_adaptively() {
        let cfg = HrmConfig::canonical();
        let stepper = HrmStepper::new(&cfg).unwrap();
        let mut state = RecurrentState::zeros(&cfg);
        // ACT: halt as soon as the first outer step completes.
        let run = stepper.run_with_halt(&mut state, |s| s.outer_step >= 1);
        assert!(run.halted_early);
        assert_eq!(run.outer_reached, 1);
        assert!(run.steps > 0);
        assert!(run.steps < cfg.total_recurrent_steps());
    }

    #[test]
    fn run_with_never_halt_matches_run() {
        let cfg = HrmConfig::canonical();
        let stepper = HrmStepper::new(&cfg).unwrap();
        let mut a = RecurrentState::zeros(&cfg);
        let mut b = RecurrentState::zeros(&cfg);
        let ra = stepper.run(&mut a);
        let rb = stepper.run_with_halt(&mut b, |_| false);
        assert_eq!(ra, rb);
    }

    #[test]
    fn immediate_halt_runs_zero_steps() {
        let cfg = HrmConfig::canonical();
        let stepper = HrmStepper::new(&cfg).unwrap();
        let mut state = RecurrentState::zeros(&cfg);
        let run = stepper.run_with_halt(&mut state, |_| true);
        assert_eq!(run.steps, 0);
        assert!(run.halted_early);
    }
}
