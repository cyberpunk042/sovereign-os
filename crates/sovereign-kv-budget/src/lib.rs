//! `sovereign-kv-budget` — size the KV cache.
//!
//! Every decoded token leaves a key and a value vector *per layer per KV head*
//! in the cache, and that cache — not the weights — is what blows up with long
//! contexts and large batches. Deciding which tier (VRAM / RAM / NVMe) a
//! request lands in, how long a context it can have, or how big a batch fits,
//! all start from one number: how many bytes the cache costs.
//!
//! This crate computes it. With grouped-query attention the cache scales with
//! the *KV* head count, not the query head count, so a GQA model's cache is
//! much smaller — the calculation reflects that. The two questions a planner
//! asks are both here: [`kv_bytes`] (how much does this context cost?) and
//! [`max_seq_len`] (how long a context fits this budget?).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the kv-budget surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// The shape and precision of a model's KV cache.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct KvShape {
    /// Number of transformer layers.
    pub num_layers: usize,
    /// Number of key/value heads (GQA: fewer than query heads).
    pub num_kv_heads: usize,
    /// Per-head dimension.
    pub head_dim: usize,
    /// Bytes per cached element (e.g. 2 for fp16, 1 for int8/fp8).
    pub bytes_per_elem: usize,
}

impl KvShape {
    /// Build a shape.
    pub fn new(
        num_layers: usize,
        num_kv_heads: usize,
        head_dim: usize,
        bytes_per_elem: usize,
    ) -> Self {
        Self {
            num_layers,
            num_kv_heads,
            head_dim,
            bytes_per_elem,
        }
    }

    /// Bytes the cache grows by per decoded token, per batch item. Counts both
    /// the key and the value (the factor of 2).
    pub fn bytes_per_token(&self) -> u64 {
        2 * self.num_layers as u64
            * self.num_kv_heads as u64
            * self.head_dim as u64
            * self.bytes_per_elem as u64
    }

    /// Total KV-cache bytes for `seq_len` tokens at batch size `batch`.
    pub fn kv_bytes(&self, seq_len: usize, batch: usize) -> u64 {
        self.bytes_per_token() * seq_len as u64 * batch as u64
    }

    /// The longest sequence length whose KV cache fits `budget_bytes` at batch
    /// size `batch`. `0` if even one token doesn't fit; saturates a zero batch.
    pub fn max_seq_len(&self, budget_bytes: u64, batch: usize) -> usize {
        let per_token = self.bytes_per_token().saturating_mul(batch.max(1) as u64);
        if per_token == 0 {
            return 0;
        }
        (budget_bytes / per_token) as usize
    }

    /// The largest batch size whose KV cache for `seq_len` fits `budget_bytes`.
    pub fn max_batch(&self, budget_bytes: u64, seq_len: usize) -> usize {
        let per_item = self.bytes_per_token().saturating_mul(seq_len as u64);
        if per_item == 0 {
            return 0;
        }
        (budget_bytes / per_item) as usize
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    // a Llama-2-7B-ish shape with GQA: 32 layers, 8 kv heads, 128 head_dim, fp16
    fn shape() -> KvShape {
        KvShape::new(32, 8, 128, 2)
    }

    #[test]
    fn bytes_per_token_is_correct() {
        // 2 * 32 * 8 * 128 * 2 = 131072 bytes = 128 KiB/token
        assert_eq!(shape().bytes_per_token(), 131_072);
    }

    #[test]
    fn kv_bytes_for_a_context() {
        // 128 KiB/token * 2048 tokens = 256 MiB
        assert_eq!(shape().kv_bytes(2048, 1), 268_435_456);
        // batch of 4 → 1 GiB
        assert_eq!(shape().kv_bytes(2048, 4), 4 * 268_435_456);
    }

    #[test]
    fn max_seq_len_inverts_the_budget() {
        // 1 GiB / 128 KiB per token = 8192 tokens
        assert_eq!(shape().max_seq_len(1_073_741_824, 1), 8192);
        // half the budget → half the context
        assert_eq!(shape().max_seq_len(536_870_912, 1), 4096);
        // batch 2 → half the context per item
        assert_eq!(shape().max_seq_len(1_073_741_824, 2), 4096);
    }

    #[test]
    fn gqa_cache_is_smaller_than_full_mha() {
        // 8 kv heads vs 32 query heads → 4x smaller cache
        let gqa = KvShape::new(32, 8, 128, 2);
        let mha = KvShape::new(32, 32, 128, 2);
        assert_eq!(mha.bytes_per_token(), 4 * gqa.bytes_per_token());
    }

    #[test]
    fn lower_precision_shrinks_the_cache() {
        let fp16 = KvShape::new(32, 8, 128, 2);
        let int8 = KvShape::new(32, 8, 128, 1);
        assert_eq!(fp16.bytes_per_token(), 2 * int8.bytes_per_token());
    }

    #[test]
    fn max_batch_inverts_for_batch() {
        let s = shape();
        // 1 GiB, seq 2048 (256 MiB/item) → 4 items
        assert_eq!(s.max_batch(1_073_741_824, 2048), 4);
    }

    #[test]
    fn tiny_budget_fits_nothing() {
        assert_eq!(shape().max_seq_len(1000, 1), 0); // < one token
    }

    #[test]
    fn serde_round_trip() {
        let s = shape();
        let j = serde_json::to_string(&s).unwrap();
        let back: KvShape = serde_json::from_str(&j).unwrap();
        assert_eq!(s, back);
    }
}
