//! `sovereign-kv-window` — a bounded sliding-window KV cache with sinks.
//!
//! A naive decoder cache grows by one entry per token forever, so attention
//! cost and memory grow without bound — fatal for the operator's *endless*
//! operation. This crate bounds it: it keeps the first `sinks` tokens (the
//! "attention sinks" that empirically anchor a transformer's attention) plus
//! the most recent `window` tokens, and evicts whatever falls in the middle.
//! Total retained entries never exceed `sinks + window`, however long
//! generation runs.
//!
//! This is a *policy* over key/value vectors, independent of the attention
//! math — [`keys`](WindowedKv::keys) / [`values`](WindowedKv::values) hand the
//! retained set straight to the attention kernel. It is distinct from the
//! tiered VRAM/RAM/NVMe `sovereign-kv-cache`, which decides *where* a cache
//! entry lives; this decides *whether it is kept at all*.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the windowed-cache surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong with a windowed cache.
#[derive(Debug, Error, PartialEq)]
pub enum WindowError {
    /// The window size was zero (a cache must retain at least one recent token).
    #[error("window must be >= 1")]
    ZeroWindow,
    /// A pushed key/value had a width inconsistent with earlier entries.
    #[error("width mismatch: expected {expected}, got {got}")]
    WidthMismatch {
        /// Established entry width.
        expected: usize,
        /// Observed width.
        got: usize,
    },
    /// Key and value widths differed on a push.
    #[error("key width {key} != value width {value}")]
    KeyValueWidth {
        /// Key width.
        key: usize,
        /// Value width.
        value: usize,
    },
}

/// A bounded KV cache: first `sinks` tokens + most recent `window` tokens.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct WindowedKv {
    sinks: usize,
    window: usize,
    keys: Vec<Vec<f32>>,
    values: Vec<Vec<f32>>,
    /// Total tokens ever pushed (including evicted ones).
    seen: usize,
    /// Entry width, fixed by the first push.
    width: Option<usize>,
}

impl WindowedKv {
    /// A cache keeping `sinks` leading tokens and the most recent `window`.
    pub fn new(sinks: usize, window: usize) -> Result<Self, WindowError> {
        if window == 0 {
            return Err(WindowError::ZeroWindow);
        }
        Ok(Self {
            sinks,
            window,
            keys: Vec::new(),
            values: Vec::new(),
            seen: 0,
            width: None,
        })
    }

    /// Maximum entries ever retained (`sinks + window`).
    pub fn capacity(&self) -> usize {
        self.sinks + self.window
    }

    /// Currently retained entry count.
    pub fn retained(&self) -> usize {
        self.values.len()
    }

    /// Total tokens ever pushed (including evicted).
    pub fn seen(&self) -> usize {
        self.seen
    }

    /// Whether anything is retained.
    pub fn is_empty(&self) -> bool {
        self.values.is_empty()
    }

    /// The retained keys, oldest-kept first (sinks, then recent window).
    pub fn keys(&self) -> &[Vec<f32>] {
        &self.keys
    }

    /// The retained values, aligned with [`keys`](Self::keys).
    pub fn values(&self) -> &[Vec<f32>] {
        &self.values
    }

    /// Push a `(key, value)` pair, evicting the middle if over capacity.
    pub fn push(&mut self, key: Vec<f32>, value: Vec<f32>) -> Result<(), WindowError> {
        if key.len() != value.len() {
            return Err(WindowError::KeyValueWidth {
                key: key.len(),
                value: value.len(),
            });
        }
        match self.width {
            None => self.width = Some(key.len()),
            Some(w) if w != key.len() => {
                return Err(WindowError::WidthMismatch {
                    expected: w,
                    got: key.len(),
                });
            }
            Some(_) => {}
        }

        self.keys.push(key);
        self.values.push(value);
        self.seen += 1;
        self.evict();
        Ok(())
    }

    /// Drop middle entries until at most `sinks + window` remain, keeping the
    /// first `sinks` and the last `window`.
    fn evict(&mut self) {
        let cap = self.capacity();
        if self.keys.len() <= cap {
            return;
        }
        // Indices to keep: 0..sinks and (len-window)..len.
        let len = self.keys.len();
        let keep_recent_from = len - self.window;
        let mut new_keys = Vec::with_capacity(cap);
        let mut new_values = Vec::with_capacity(cap);
        for i in 0..len {
            if i < self.sinks || i >= keep_recent_from {
                new_keys.push(std::mem::take(&mut self.keys[i]));
                new_values.push(std::mem::take(&mut self.values[i]));
            }
        }
        self.keys = new_keys;
        self.values = new_values;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn kv(v: f32) -> (Vec<f32>, Vec<f32>) {
        (vec![v, v], vec![v, -v])
    }

    #[test]
    fn zero_window_rejected() {
        assert_eq!(WindowedKv::new(2, 0).unwrap_err(), WindowError::ZeroWindow);
    }

    #[test]
    fn under_capacity_retains_everything() {
        let mut c = WindowedKv::new(1, 3).unwrap(); // cap 4
        for i in 0..4 {
            let (k, v) = kv(i as f32);
            c.push(k, v).unwrap();
        }
        assert_eq!(c.retained(), 4);
        assert_eq!(c.seen(), 4);
    }

    #[test]
    fn over_capacity_keeps_sinks_and_recent_window() {
        let mut c = WindowedKv::new(2, 3).unwrap(); // cap 5
        for i in 0..10 {
            let (k, v) = kv(i as f32);
            c.push(k, v).unwrap();
        }
        assert_eq!(c.seen(), 10);
        assert_eq!(c.retained(), 5);
        // sinks: tokens 0,1 ; recent window: tokens 7,8,9
        let kept: Vec<f32> = c.values().iter().map(|v| v[0]).collect();
        assert_eq!(kept, vec![0.0, 1.0, 7.0, 8.0, 9.0]);
    }

    #[test]
    fn never_exceeds_capacity_over_a_long_run() {
        let mut c = WindowedKv::new(4, 16).unwrap(); // cap 20
        for i in 0..10_000 {
            let (k, v) = kv(i as f32);
            c.push(k, v).unwrap();
            assert!(c.retained() <= c.capacity());
        }
        assert_eq!(c.retained(), 20);
        assert_eq!(c.seen(), 10_000);
        // the four sinks are still tokens 0..=3
        let sinks: Vec<f32> = c.values()[..4].iter().map(|v| v[0]).collect();
        assert_eq!(sinks, vec![0.0, 1.0, 2.0, 3.0]);
    }

    #[test]
    fn zero_sinks_is_a_pure_sliding_window() {
        let mut c = WindowedKv::new(0, 3).unwrap();
        for i in 0..6 {
            let (k, v) = kv(i as f32);
            c.push(k, v).unwrap();
        }
        let kept: Vec<f32> = c.values().iter().map(|v| v[0]).collect();
        assert_eq!(kept, vec![3.0, 4.0, 5.0]); // only the last 3
    }

    #[test]
    fn width_mismatch_is_caught() {
        let mut c = WindowedKv::new(1, 2).unwrap();
        c.push(vec![1.0, 2.0], vec![1.0, 2.0]).unwrap();
        assert_eq!(
            c.push(vec![1.0], vec![1.0]).unwrap_err(),
            WindowError::WidthMismatch {
                expected: 2,
                got: 1
            }
        );
    }

    #[test]
    fn key_value_width_must_match() {
        let mut c = WindowedKv::new(1, 2).unwrap();
        assert_eq!(
            c.push(vec![1.0, 2.0], vec![1.0]).unwrap_err(),
            WindowError::KeyValueWidth { key: 2, value: 1 }
        );
    }

    #[test]
    fn serde_round_trip() {
        let mut c = WindowedKv::new(1, 2).unwrap();
        c.push(vec![1.0], vec![2.0]).unwrap();
        let j = serde_json::to_string(&c).unwrap();
        let back: WindowedKv = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }

    // The retained set feeds the real attention kernel unchanged.
    #[test]
    fn windowed_cache_feeds_attention() {
        use sovereign_attention::Attention;
        let head = Attention::new(2);
        let mut c = WindowedKv::new(1, 2).unwrap(); // cap 3
        for i in 0..8 {
            let (k, v) = kv(i as f32 * 0.1);
            c.push(k, v).unwrap();
        }
        assert_eq!(c.retained(), 3);
        let q = vec![0.5, -0.5];
        let out = head.attend(&q, c.keys(), c.values()).unwrap();
        assert_eq!(out.len(), 2);
        assert!(out.iter().all(|v| v.is_finite()));
    }
}
