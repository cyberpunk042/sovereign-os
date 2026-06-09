//! `sovereign-hyperloglog` — count distinct items in kilobytes, not gigabytes.
//!
//! "How many *distinct* tokens has this stream produced?" — vocabulary growth,
//! output diversity, distinct-n-gram counts — is a cardinality question. Holding
//! a hash set answers it exactly but costs memory linear in the number of
//! distinct items. **HyperLogLog** answers it approximately in fixed memory: a
//! few kilobytes give a relative error of about `1.04 / √m` for `m` registers,
//! whether the true count is a thousand or a billion.
//!
//! The intuition is order statistics on hashes. Hash each item to 64 bits; the
//! top `p` bits pick one of `m = 2^p` registers, and the register records the
//! largest "rank" seen — the position of the first 1-bit in the remaining bits,
//! i.e. one more than the run of leading zeros. A run of `k` leading zeros
//! happens with probability `2^-k`, so the longest run in a register hints at how
//! many distinct items landed there. Combining all registers with a bias-corrected
//! **harmonic mean** turns those hints into a count, and at low cardinalities —
//! where many registers are still empty — the estimator switches to **linear
//! counting** over the empty-register fraction, which is far more accurate there.
//!
//! Sketches with the same precision are **mergeable** by taking the register-wise
//! maximum, so per-shard sketches combine into a whole-stream estimate without
//! re-reading anything.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use thiserror::Error;

/// Schema version of the HyperLogLog surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Errors constructing or combining sketches.
#[derive(Debug, Clone, PartialEq, Eq, Error)]
pub enum HllError {
    /// Precision out of the supported range.
    #[error("precision must be in 4..=16, got {0}")]
    BadPrecision(u8),
    /// Two sketches of different precision cannot be merged.
    #[error("cannot merge sketches of precision {a} and {b}")]
    PrecisionMismatch {
        /// This sketch's precision.
        a: u8,
        /// The other sketch's precision.
        b: u8,
    },
}

/// A HyperLogLog sketch with `2^precision` registers.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HyperLogLog {
    precision: u8,
    /// `2^precision` registers, each holding a rank (0..=64 - precision + 1).
    registers: Vec<u8>,
}

impl HyperLogLog {
    /// A sketch with the given `precision` (`p`), using `2^p` registers. A larger
    /// `p` means more memory and lower error (`≈ 1.04 / √(2^p)`). `p = 14`
    /// (16 384 registers, ~0.8% error) is a common default.
    pub fn new(precision: u8) -> Result<Self, HllError> {
        if !(4..=16).contains(&precision) {
            return Err(HllError::BadPrecision(precision));
        }
        let m = 1usize << precision;
        Ok(Self {
            precision,
            registers: vec![0; m],
        })
    }

    /// The precision `p`.
    pub fn precision(&self) -> u8 {
        self.precision
    }

    /// The number of registers `m = 2^p`.
    pub fn registers(&self) -> usize {
        self.registers.len()
    }

    /// FNV-1a 64-bit hash of a key.
    fn hash(key: &[u8]) -> u64 {
        let mut h: u64 = 0xcbf2_9ce4_8422_2325;
        for &b in key {
            h ^= b as u64;
            h = h.wrapping_mul(0x0000_0100_0000_01b3);
        }
        // extra avalanche so FNV's low bits are well mixed for register choice
        h ^= h >> 33;
        h = h.wrapping_mul(0xff51_afd7_ed55_8ccd);
        h ^= h >> 33;
        h
    }

    /// Add a key to the sketch.
    pub fn add(&mut self, key: &[u8]) {
        let x = Self::hash(key);
        let p = self.precision as u32;
        // top p bits choose the register.
        let idx = (x >> (64 - p)) as usize;
        // rank = 1 + number of leading zeros of the remaining (64 - p) bits.
        let remaining = x << p; // shift the used bits out; low bits become zero
        // count leading zeros over the (64 - p)-bit window. Since we shifted left
        // by p, the window occupies the top (64 - p) bits; trailing p bits are 0,
        // so cap the rank at (64 - p + 1).
        let max_rank = (64 - p + 1) as u8;
        let rank = if remaining == 0 {
            max_rank
        } else {
            (remaining.leading_zeros() as u8 + 1).min(max_rank)
        };
        if rank > self.registers[idx] {
            self.registers[idx] = rank;
        }
    }

    /// Add a string key.
    pub fn add_str(&mut self, key: &str) {
        self.add(key.as_bytes());
    }

    /// The bias-correction constant `α_m` for `m` registers.
    fn alpha(m: usize) -> f64 {
        match m {
            16 => 0.673,
            32 => 0.697,
            64 => 0.709,
            _ => 0.7213 / (1.0 + 1.079 / m as f64),
        }
    }

    /// The estimated number of distinct items added.
    pub fn estimate(&self) -> f64 {
        let m = self.registers.len();
        let mf = m as f64;
        // harmonic-mean raw estimate
        let mut sum = 0.0;
        let mut zeros = 0usize;
        for &r in &self.registers {
            sum += 2f64.powi(-(r as i32));
            if r == 0 {
                zeros += 1;
            }
        }
        let raw = Self::alpha(m) * mf * mf / sum;

        // small-range correction: linear counting when registers remain empty.
        if raw <= 2.5 * mf && zeros > 0 {
            mf * (mf / zeros as f64).ln()
        } else {
            raw
        }
    }

    /// The estimated cardinality rounded to the nearest integer.
    pub fn len(&self) -> u64 {
        self.estimate().round() as u64
    }

    /// Whether nothing has been added (all registers empty).
    pub fn is_empty(&self) -> bool {
        self.registers.iter().all(|&r| r == 0)
    }

    /// Merge `other` (same precision) by taking the register-wise maximum, so the
    /// result estimates the cardinality of the *union* of both streams.
    pub fn merge(&mut self, other: &HyperLogLog) -> Result<(), HllError> {
        if self.precision != other.precision {
            return Err(HllError::PrecisionMismatch {
                a: self.precision,
                b: other.precision,
            });
        }
        for (a, b) in self.registers.iter_mut().zip(other.registers.iter()) {
            *a = (*a).max(*b);
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn relative_error(est: f64, truth: f64) -> f64 {
        (est - truth).abs() / truth
    }

    #[test]
    fn rejects_bad_precision() {
        assert_eq!(HyperLogLog::new(3), Err(HllError::BadPrecision(3)));
        assert_eq!(HyperLogLog::new(17), Err(HllError::BadPrecision(17)));
        assert!(HyperLogLog::new(14).is_ok());
    }

    #[test]
    fn empty_sketch_estimates_zero() {
        let h = HyperLogLog::new(12).unwrap();
        assert!(h.is_empty());
        assert_eq!(h.len(), 0);
    }

    #[test]
    fn small_cardinality_is_accurate() {
        // linear counting should nail small counts almost exactly
        let mut h = HyperLogLog::new(14).unwrap();
        for i in 0..100u64 {
            h.add(format!("item-{i}").as_bytes());
        }
        let est = h.estimate();
        assert!(relative_error(est, 100.0) < 0.05, "est {est} for 100");
    }

    #[test]
    fn duplicates_do_not_inflate_the_count() {
        let mut h = HyperLogLog::new(12).unwrap();
        for _ in 0..10_000 {
            h.add_str("the same key over and over");
        }
        // one distinct item, regardless of repetition
        assert_eq!(h.len(), 1);
    }

    #[test]
    fn large_cardinality_within_error_bound() {
        let p = 14u8;
        let mut h = HyperLogLog::new(p).unwrap();
        let truth = 100_000u64;
        for i in 0..truth {
            h.add(format!("k{i}").as_bytes());
        }
        let est = h.estimate();
        // standard error ~1.04/sqrt(m); allow ~3 sigma headroom
        let m = (1usize << p) as f64;
        let sigma = 1.04 / m.sqrt();
        let err = relative_error(est, truth as f64);
        assert!(err < 3.0 * sigma, "rel err {err} vs 3σ {}", 3.0 * sigma);
    }

    #[test]
    fn merge_estimates_union() {
        let mut a = HyperLogLog::new(14).unwrap();
        let mut b = HyperLogLog::new(14).unwrap();
        // a: items 0..6000, b: items 4000..10000 → union is 0..10000 = 10000
        for i in 0..6000u64 {
            a.add(format!("u{i}").as_bytes());
        }
        for i in 4000..10000u64 {
            b.add(format!("u{i}").as_bytes());
        }
        a.merge(&b).unwrap();
        let est = a.estimate();
        assert!(relative_error(est, 10_000.0) < 0.03, "union est {est}");
    }

    #[test]
    fn merge_precision_mismatch_errors() {
        let mut a = HyperLogLog::new(12).unwrap();
        let b = HyperLogLog::new(14).unwrap();
        assert!(matches!(
            a.merge(&b),
            Err(HllError::PrecisionMismatch { a: 12, b: 14 })
        ));
    }

    #[test]
    fn deterministic_for_same_input() {
        let mut a = HyperLogLog::new(10).unwrap();
        let mut b = HyperLogLog::new(10).unwrap();
        for i in 0..500u64 {
            a.add(format!("x{i}").as_bytes());
            b.add(format!("x{i}").as_bytes());
        }
        assert_eq!(a, b);
        assert_eq!(a.estimate(), b.estimate());
    }

    #[test]
    fn serde_round_trip() {
        let mut h = HyperLogLog::new(12).unwrap();
        for i in 0..1000u64 {
            h.add(format!("s{i}").as_bytes());
        }
        let j = serde_json::to_string(&h).unwrap();
        let back: HyperLogLog = serde_json::from_str(&j).unwrap();
        assert_eq!(h, back);
        assert_eq!(h.len(), back.len());
    }
}
