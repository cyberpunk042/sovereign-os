//! `sovereign-mha` — multi-head attention with grouped-query support.
//!
//! A real decoder runs attention with *many* heads, and modern ones share
//! key/value heads across groups of query heads to shrink the KV cache.
//! This crate generalizes the single-head [`sovereign-attention`] kernel to
//! that layout:
//!
//! * **MHA** — `num_kv_heads == num_q_heads`: every query head has its own
//!   key/value head (classic multi-head attention).
//! * **GQA** — `1 < num_kv_heads < num_q_heads`: query heads are partitioned
//!   into `num_kv_heads` groups, each group sharing one key/value head.
//! * **MQA** — `num_kv_heads == 1`: all query heads share a single KV head
//!   (maximal cache saving).
//!
//! The query vector is `num_q_heads · head_dim` wide; each cached position
//! holds a `num_kv_heads · head_dim` key and value. For each query head the
//! engine slices out its sub-vector, looks up its KV group, runs the per-head
//! softmax attention, and concatenates the contexts back into a
//! `num_q_heads · head_dim` output. The KV-grouping map and the reduction to
//! the single-head kernel are pinned as tests.
//!
//! [`sovereign-attention`]: https://github.com/cyberpunk042/sovereign-os/tree/main/crates/sovereign-attention
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use sovereign_attention::{Attention, AttentionError};
use thiserror::Error;

/// Schema version of the MHA surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Things that can go wrong configuring or running multi-head attention.
#[derive(Debug, Error, PartialEq)]
pub enum MhaError {
    /// `num_q_heads` was not a multiple of `num_kv_heads`.
    #[error("num_q_heads ({q}) must be a multiple of num_kv_heads ({kv})")]
    HeadGrouping {
        /// Query-head count.
        q: usize,
        /// KV-head count.
        kv: usize,
    },
    /// The query vector had the wrong width.
    #[error("query width mismatch: expected {expected} (num_q_heads·head_dim), got {got}")]
    QueryWidth {
        /// Expected width.
        expected: usize,
        /// Observed width.
        got: usize,
    },
    /// A key/value vector had the wrong width.
    #[error("kv width mismatch at position {index}: expected {expected}, got {got}")]
    KvWidth {
        /// Cache position.
        index: usize,
        /// Expected width (`num_kv_heads·head_dim`).
        expected: usize,
        /// Observed width.
        got: usize,
    },
    /// Number of keys did not equal number of values.
    #[error("key/value count mismatch: {keys} keys vs {values} values")]
    KeyValueCountMismatch {
        /// Key count.
        keys: usize,
        /// Value count.
        values: usize,
    },
    /// Attention was asked to read from an empty context.
    #[error("empty context: nothing to attend over")]
    EmptyContext,
    /// A per-head attention error bubbled up.
    #[error("head attention: {0}")]
    Head(#[from] AttentionError),
}

/// A multi-head attention configuration.
#[derive(Debug, Clone, Copy, PartialEq, Serialize, Deserialize)]
pub struct Mha {
    /// Number of query heads.
    pub num_q_heads: usize,
    /// Number of key/value heads (≤ `num_q_heads`, and divides it).
    pub num_kv_heads: usize,
    /// Per-head dimension.
    pub head_dim: usize,
    /// The shared per-head softmax scale.
    pub scale: f32,
}

impl Mha {
    /// Build an MHA config with the canonical `1/sqrt(head_dim)` scale.
    ///
    /// # Panics
    /// Panics on a zero count/dim. Returns [`MhaError::HeadGrouping`] if
    /// `num_q_heads` is not a multiple of `num_kv_heads`.
    pub fn new(num_q_heads: usize, num_kv_heads: usize, head_dim: usize) -> Result<Self, MhaError> {
        assert!(
            num_q_heads > 0 && num_kv_heads > 0 && head_dim > 0,
            "counts/dim must be > 0"
        );
        if num_q_heads % num_kv_heads != 0 {
            return Err(MhaError::HeadGrouping {
                q: num_q_heads,
                kv: num_kv_heads,
            });
        }
        Ok(Self {
            num_q_heads,
            num_kv_heads,
            head_dim,
            scale: 1.0 / (head_dim as f32).sqrt(),
        })
    }

    /// Query heads per KV head (the GQA group size).
    pub fn group_size(&self) -> usize {
        self.num_q_heads / self.num_kv_heads
    }

    /// Which KV head query head `q_head` reads from.
    pub fn kv_head_for(&self, q_head: usize) -> usize {
        q_head / self.group_size()
    }

    /// Full query width (`num_q_heads · head_dim`).
    pub fn query_width(&self) -> usize {
        self.num_q_heads * self.head_dim
    }

    /// Full key/value width (`num_kv_heads · head_dim`).
    pub fn kv_width(&self) -> usize {
        self.num_kv_heads * self.head_dim
    }

    /// Run multi-head attention. `query` is `query_width()` wide; each entry of
    /// `keys`/`values` is `kv_width()` wide (one cached position). Returns a
    /// `query_width()`-wide output (the concatenated per-head contexts).
    pub fn attend(
        &self,
        query: &[f32],
        keys: &[Vec<f32>],
        values: &[Vec<f32>],
    ) -> Result<Vec<f32>, MhaError> {
        if query.len() != self.query_width() {
            return Err(MhaError::QueryWidth {
                expected: self.query_width(),
                got: query.len(),
            });
        }
        if keys.len() != values.len() {
            return Err(MhaError::KeyValueCountMismatch {
                keys: keys.len(),
                values: values.len(),
            });
        }
        if keys.is_empty() {
            return Err(MhaError::EmptyContext);
        }
        let kvw = self.kv_width();
        for (index, (k, v)) in keys.iter().zip(values).enumerate() {
            if k.len() != kvw {
                return Err(MhaError::KvWidth {
                    index,
                    expected: kvw,
                    got: k.len(),
                });
            }
            if v.len() != kvw {
                return Err(MhaError::KvWidth {
                    index,
                    expected: kvw,
                    got: v.len(),
                });
            }
        }

        let head = Attention::with_scale(self.head_dim, self.scale);
        let d = self.head_dim;
        let mut out = vec![0.0f32; self.query_width()];

        for q_head in 0..self.num_q_heads {
            let q_slice = &query[q_head * d..(q_head + 1) * d];
            let kvh = self.kv_head_for(q_head);
            // gather this KV head's slice across all cached positions
            let keys_h: Vec<Vec<f32>> = keys
                .iter()
                .map(|k| k[kvh * d..(kvh + 1) * d].to_vec())
                .collect();
            let values_h: Vec<Vec<f32>> = values
                .iter()
                .map(|v| v[kvh * d..(kvh + 1) * d].to_vec())
                .collect();
            let ctx = head.attend(q_slice, &keys_h, &values_h)?;
            out[q_head * d..(q_head + 1) * d].copy_from_slice(&ctx);
        }
        Ok(out)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn approx(a: &[f32], b: &[f32], eps: f32) -> bool {
        a.len() == b.len() && a.iter().zip(b).all(|(x, y)| (x - y).abs() <= eps)
    }

    #[test]
    fn grouping_must_divide() {
        assert_eq!(
            Mha::new(6, 4, 8).unwrap_err(),
            MhaError::HeadGrouping { q: 6, kv: 4 }
        );
        assert!(Mha::new(8, 4, 16).is_ok());
    }

    #[test]
    fn group_size_and_kv_map() {
        // 4 query heads, 2 kv heads → group size 2; heads 0,1→kv0, 2,3→kv1.
        let mha = Mha::new(4, 2, 8).unwrap();
        assert_eq!(mha.group_size(), 2);
        assert_eq!(mha.kv_head_for(0), 0);
        assert_eq!(mha.kv_head_for(1), 0);
        assert_eq!(mha.kv_head_for(2), 1);
        assert_eq!(mha.kv_head_for(3), 1);
    }

    #[test]
    fn mqa_maps_every_head_to_kv_zero() {
        let mha = Mha::new(8, 1, 4).unwrap();
        assert_eq!(mha.group_size(), 8);
        for h in 0..8 {
            assert_eq!(mha.kv_head_for(h), 0);
        }
    }

    #[test]
    fn output_has_full_query_width() {
        let mha = Mha::new(3, 1, 2).unwrap(); // MQA, width 6
        let q = vec![1.0; 6];
        let keys = vec![vec![1.0, 0.0], vec![0.0, 1.0]];
        let values = vec![vec![5.0, 6.0], vec![7.0, 8.0]];
        let out = mha.attend(&q, &keys, &values).unwrap();
        assert_eq!(out.len(), 6);
    }

    #[test]
    fn single_head_equals_plain_attention() {
        // MHA(1,1,d) must equal the underlying single-head kernel exactly.
        let mha = Mha::new(1, 1, 3).unwrap();
        let q = vec![0.3, -1.1, 2.0];
        let keys = vec![vec![1.0, 0.0, -1.0], vec![0.5, 0.5, 0.5]];
        let values = vec![vec![1.0, 0.0, 2.0], vec![0.0, 1.0, -1.0]];
        let mha_out = mha.attend(&q, &keys, &values).unwrap();

        let plain = Attention::new(3).attend(&q, &keys, &values).unwrap();
        assert!(approx(&mha_out, &plain, 1e-6));
    }

    #[test]
    fn mqa_heads_share_kv_but_differ_by_query() {
        // 2 query heads, 1 kv head. Two distinct queries → the two output
        // halves are computed against the SAME kv but differ because the
        // queries differ.
        let mha = Mha::new(2, 1, 2).unwrap();
        // head 0 query strongly selects key 0; head 1 query selects key 1.
        let q = vec![100.0, 0.0, /*head1*/ 0.0, 100.0];
        let keys = vec![vec![1.0, 0.0], vec![0.0, 1.0]];
        let values = vec![vec![1.0, 1.0], vec![9.0, 9.0]];
        let out = mha.attend(&q, &keys, &values).unwrap();
        // head 0 ≈ value 0, head 1 ≈ value 1
        assert!(approx(&out[0..2], &[1.0, 1.0], 1e-3), "{out:?}");
        assert!(approx(&out[2..4], &[9.0, 9.0], 1e-3), "{out:?}");
    }

    #[test]
    fn gqa_groups_read_their_assigned_kv_head() {
        // 2 q heads, 2 kv heads (= plain MHA). Each head reads its own KV head.
        let mha = Mha::new(2, 2, 1).unwrap(); // head_dim 1
        // q = [head0=1, head1=1]; keys per position = [kv0, kv1]
        let q = vec![1.0, 1.0];
        // one cached position; kv0 value=3, kv1 value=7
        let keys = vec![vec![1.0, 1.0]];
        let values = vec![vec![3.0, 7.0]];
        let out = mha.attend(&q, &keys, &values).unwrap();
        // single position → each head's context is just its kv head's value
        assert!(approx(&out, &[3.0, 7.0], 1e-6), "{out:?}");
    }

    #[test]
    fn query_width_mismatch_is_caught() {
        let mha = Mha::new(2, 1, 2).unwrap();
        let err = mha
            .attend(&[1.0, 2.0], &[vec![1.0, 1.0]], &[vec![1.0, 1.0]])
            .unwrap_err();
        assert_eq!(
            err,
            MhaError::QueryWidth {
                expected: 4,
                got: 2
            }
        );
    }

    #[test]
    fn kv_width_mismatch_is_caught() {
        let mha = Mha::new(2, 2, 2).unwrap(); // kv width 4
        let err = mha
            .attend(&[1.0; 4], &[vec![1.0, 1.0]], &[vec![1.0, 1.0]])
            .unwrap_err();
        assert_eq!(
            err,
            MhaError::KvWidth {
                index: 0,
                expected: 4,
                got: 2
            }
        );
    }

    #[test]
    fn empty_context_is_an_error() {
        let mha = Mha::new(2, 1, 2).unwrap();
        assert_eq!(
            mha.attend(&[1.0; 4], &[], &[]).unwrap_err(),
            MhaError::EmptyContext
        );
    }

    #[test]
    fn serde_round_trip() {
        let mha = Mha::new(8, 2, 16).unwrap();
        let j = serde_json::to_string(&mha).unwrap();
        let back: Mha = serde_json::from_str(&j).unwrap();
        assert_eq!(mha, back);
    }
}
