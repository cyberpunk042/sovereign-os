//! `sovereign-logit-pipeline` — compose decode-time logit transforms.
//!
//! Generation controls — an allow/ban [`LogitMask`], no-repeat-n-gram blocking,
//! and whatever else — each rewrite the logit row before sampling. Applied
//! individually they're easy to get out of order or forget; this crate gives
//! them one shape. A [`LogitProcessor`] is anything that, given the tokens
//! generated so far and the current logits, mutates the logits in place; a
//! [`LogitPipeline`] runs an ordered list of them. The decode loop calls
//! [`LogitPipeline::apply`] once per position and then samples — every control
//! is in the pipeline, in a defined order.
//!
//! Built-in processors wrap the existing controls ([`MaskProcessor`],
//! [`NoRepeatProcessor`]); the trait is open so callers can add their own.
//!
//! Composes [`sovereign-logit-mask`] and [`sovereign-no-repeat-ngram`].
//!
//! [`sovereign-logit-mask`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-logit-mask
//! [`sovereign-no-repeat-ngram`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-no-repeat-ngram
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use sovereign_logit_mask::LogitMask;
use sovereign_no_repeat_ngram::NoRepeatNgram;

/// Schema version of the logit-pipeline surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A decode-time logit transform. Given the generated `history` and the current
/// `logits`, it mutates the logits in place.
///
/// Object-safe (and `Debug`) so a [`LogitPipeline`] can hold a mix of them.
pub trait LogitProcessor: std::fmt::Debug {
    /// Rewrite `logits` in place using `history` as context.
    fn process(&self, history: &[usize], logits: &mut [f32]);
}

/// A processor that applies a static allow/ban/bias [`LogitMask`].
#[derive(Debug, Clone)]
pub struct MaskProcessor(pub LogitMask);

impl LogitProcessor for MaskProcessor {
    fn process(&self, _history: &[usize], logits: &mut [f32]) {
        self.0.apply(logits);
    }
}

/// A processor that bans tokens which would repeat a previously-seen n-gram.
#[derive(Debug, Clone, Copy)]
pub struct NoRepeatProcessor(pub NoRepeatNgram);

impl LogitProcessor for NoRepeatProcessor {
    fn process(&self, history: &[usize], logits: &mut [f32]) {
        for t in self.0.banned_next(history) {
            if let Some(l) = logits.get_mut(t) {
                *l = f32::NEG_INFINITY;
            }
        }
    }
}

/// An ordered pipeline of logit processors.
#[derive(Debug, Default)]
pub struct LogitPipeline {
    processors: Vec<Box<dyn LogitProcessor>>,
}

impl LogitPipeline {
    /// An empty pipeline (identity transform).
    pub fn new() -> Self {
        Self::default()
    }

    /// Append a processor (builder style).
    pub fn with(mut self, processor: Box<dyn LogitProcessor>) -> Self {
        self.processors.push(processor);
        self
    }

    /// Append a processor.
    pub fn push(&mut self, processor: Box<dyn LogitProcessor>) {
        self.processors.push(processor);
    }

    /// Number of processors.
    pub fn len(&self) -> usize {
        self.processors.len()
    }

    /// Whether the pipeline is empty.
    pub fn is_empty(&self) -> bool {
        self.processors.is_empty()
    }

    /// Run every processor over `logits`, in order, given `history`.
    pub fn apply(&self, history: &[usize], logits: &mut [f32]) {
        for p in &self.processors {
            p.process(history, logits);
        }
    }

    /// Apply to a copy and return it.
    pub fn applied(&self, history: &[usize], logits: &[f32]) -> Vec<f32> {
        let mut out = logits.to_vec();
        self.apply(history, &mut out);
        out
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_pipeline_is_identity() {
        let p = LogitPipeline::new();
        let logits = vec![1.0, 2.0, 3.0];
        assert_eq!(p.applied(&[], &logits), logits);
        assert!(p.is_empty());
    }

    #[test]
    fn mask_processor_bans_tokens() {
        let p = LogitPipeline::new().with(Box::new(MaskProcessor(LogitMask::new().ban(1))));
        let out = p.applied(&[], &[1.0, 2.0, 3.0]);
        assert_eq!(out[1], f32::NEG_INFINITY);
        assert_eq!(out[0], 1.0);
    }

    #[test]
    fn no_repeat_processor_bans_ngram_continuation() {
        // history a b a b a (0 1 0 1 0) → `b` (=1) would repeat "a b"
        let p = LogitPipeline::new().with(Box::new(NoRepeatProcessor(NoRepeatNgram::new(2))));
        let out = p.applied(&[0, 1, 0, 1, 0], &[5.0, 9.0, 1.0, 0.5]);
        assert_eq!(out[1], f32::NEG_INFINITY); // banned
        assert_eq!(out[0], 5.0); // untouched
    }

    #[test]
    fn processors_compose_in_order() {
        // mask bans token 0; no-repeat bans token 1 → both -inf
        let p = LogitPipeline::new()
            .with(Box::new(MaskProcessor(LogitMask::new().ban(0))))
            .with(Box::new(NoRepeatProcessor(NoRepeatNgram::new(2))));
        assert_eq!(p.len(), 2);
        let out = p.applied(&[0, 1, 0, 1, 0], &[5.0, 9.0, 1.0, 0.5]);
        assert_eq!(out[0], f32::NEG_INFINITY); // by mask
        assert_eq!(out[1], f32::NEG_INFINITY); // by no-repeat
        assert_eq!(out[2], 1.0);
    }

    #[test]
    fn push_adds_processors() {
        let mut p = LogitPipeline::new();
        p.push(Box::new(MaskProcessor(LogitMask::new().ban(2))));
        assert_eq!(p.len(), 1);
        assert_eq!(p.applied(&[], &[1.0, 2.0, 3.0])[2], f32::NEG_INFINITY);
    }

    // Integration: piped logits feed the real sampler; banned tokens never win.
    #[test]
    fn piped_bans_are_never_sampled() {
        use sovereign_sampler::{Sampler, SamplerConfig};
        let pipe = LogitPipeline::new()
            .with(Box::new(MaskProcessor(LogitMask::new().ban(3))))
            .with(Box::new(NoRepeatProcessor(NoRepeatNgram::new(2))));
        // token 3 banned by mask; token 1 banned by no-repeat over this history
        let history = [0usize, 1, 0, 1, 0];
        let raw = [0.5, 10.0, 0.3, 9.0];
        let masked = pipe.applied(&history, &raw);
        let sampler = Sampler::new(SamplerConfig::default());
        for seed in 0..300u64 {
            let t = sampler.sample_seeded(&masked, &[], seed).unwrap();
            assert!(t != 1 && t != 3, "banned token {t} sampled at seed {seed}");
        }
    }
}
