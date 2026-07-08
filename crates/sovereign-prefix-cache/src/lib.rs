//! `sovereign-prefix-cache` — don't recompute a prompt prefix you've seen.
//!
//! In batched serving, many requests share a prefix: the same system prompt, the
//! same few-shot examples, the same conversation history. Recomputing the model's
//! key/value cache for those shared tokens on every request is wasted work.
//! Prefix caching (the idea behind SGLang's RadixAttention and vLLM's automatic
//! prefix cache) keeps the token sequences already processed in a **trie**, so a
//! new request can look up the *longest prefix* that was already computed and
//! resume from there, only running the model on the novel suffix.
//!
//! This crate is that index. [`PrefixCache::insert`] records a token sequence with
//! an associated value (whatever you use to locate the cached KV state — a block
//! id, a handle). [`PrefixCache::longest_prefix_match`] walks the trie as far as
//! the query tokens agree, returning how many tokens matched and the value of the
//! deepest *checkpointed* node on that path — the point to resume generation from.
//! [`PrefixCache::contains`] checks for an exact stored sequence.
//!
//! The trie shares storage across overlapping prefixes, so `N` requests with a
//! common `p`-token prefix store that prefix once. It is generic over the value
//! type and over `u32` token ids.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the prefix-cache surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A trie node over token ids.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
struct Node<V> {
    children: BTreeMap<u32, usize>,
    /// A value stored at this node (set when a sequence ends here, or a
    /// checkpoint was placed).
    value: Option<V>,
}

impl<V> Node<V> {
    fn new() -> Self {
        Self {
            children: BTreeMap::new(),
            value: None,
        }
    }
}

/// A radix/trie prefix cache mapping token sequences to values.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PrefixCache<V> {
    nodes: Vec<Node<V>>,
    /// Number of distinct stored sequences (nodes carrying a value).
    entries: usize,
}

impl<V: Clone> Default for PrefixCache<V> {
    fn default() -> Self {
        Self::new()
    }
}

impl<V: Clone> PrefixCache<V> {
    /// An empty cache (with just the root).
    pub fn new() -> Self {
        Self {
            nodes: vec![Node::new()],
            entries: 0,
        }
    }

    /// Number of stored sequences (value-bearing nodes).
    pub fn len(&self) -> usize {
        self.entries
    }

    /// Whether the cache holds no sequences.
    pub fn is_empty(&self) -> bool {
        self.entries == 0
    }

    /// Number of trie nodes (a measure of shared storage).
    pub fn node_count(&self) -> usize {
        self.nodes.len()
    }

    /// Insert `tokens` with `value`, creating shared trie nodes as needed.
    /// Re-inserting the same sequence replaces its value.
    pub fn insert(&mut self, tokens: &[u32], value: V) {
        let mut cur = 0usize;
        for &t in tokens {
            cur = match self.nodes[cur].children.get(&t) {
                Some(&next) => next,
                None => {
                    let next = self.nodes.len();
                    self.nodes.push(Node::new());
                    self.nodes[cur].children.insert(t, next);
                    next
                }
            };
        }
        if self.nodes[cur].value.is_none() {
            self.entries += 1;
        }
        self.nodes[cur].value = Some(value);
    }

    /// The result of a prefix lookup.
    fn walk(&self, tokens: &[u32]) -> (usize, usize) {
        // returns (deepest node reached, tokens consumed along the existing trie).
        let mut cur = 0usize;
        let mut matched = 0usize;
        for &t in tokens {
            match self.nodes[cur].children.get(&t) {
                Some(&next) => {
                    cur = next;
                    matched += 1;
                }
                None => break,
            }
        }
        (cur, matched)
    }

    /// The longest prefix of `tokens` already in the cache: returns the number of
    /// matched tokens and the value of the deepest value-bearing node on that
    /// path (the checkpoint to resume from), if any. `matched_len` may exceed the
    /// last checkpoint when intermediate nodes carry no value.
    pub fn longest_prefix_match(&self, tokens: &[u32]) -> PrefixMatch<&V> {
        // walk the path, remembering the deepest checkpoint (value-bearing node).
        let mut cur = 0usize;
        let mut matched = 0usize;
        let mut checkpoint_len = 0usize;
        let mut checkpoint: Option<&V> = None;
        if let Some(v) = self.nodes[0].value.as_ref() {
            checkpoint = Some(v);
        }
        for &t in tokens {
            match self.nodes[cur].children.get(&t) {
                Some(&next) => {
                    cur = next;
                    matched += 1;
                    if let Some(v) = self.nodes[cur].value.as_ref() {
                        checkpoint = Some(v);
                        checkpoint_len = matched;
                    }
                }
                None => break,
            }
        }
        PrefixMatch {
            matched_len: matched,
            checkpoint_len,
            value: checkpoint,
        }
    }

    /// Whether `tokens` is stored exactly (ends at a value-bearing node).
    pub fn contains(&self, tokens: &[u32]) -> bool {
        let (node, matched) = self.walk(tokens);
        matched == tokens.len() && self.nodes[node].value.is_some()
    }

    /// The value stored exactly at `tokens`, if any.
    pub fn get(&self, tokens: &[u32]) -> Option<&V> {
        let (node, matched) = self.walk(tokens);
        if matched == tokens.len() {
            self.nodes[node].value.as_ref()
        } else {
            None
        }
    }
}

/// The outcome of a longest-prefix lookup.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct PrefixMatch<V> {
    /// How many leading tokens existed in the trie (the reusable prefix length).
    pub matched_len: usize,
    /// The token length at the deepest checkpoint (value-bearing node) reached.
    pub checkpoint_len: usize,
    /// The value at that checkpoint, to resume from.
    pub value: Option<V>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn insert_and_exact_get() {
        let mut c: PrefixCache<&str> = PrefixCache::new();
        c.insert(&[1, 2, 3], "block_a");
        assert!(c.contains(&[1, 2, 3]));
        assert_eq!(c.get(&[1, 2, 3]), Some(&"block_a"));
        assert!(!c.contains(&[1, 2]));
        assert_eq!(c.len(), 1);
    }

    #[test]
    fn longest_prefix_reuses_shared_tokens() {
        let mut c: PrefixCache<usize> = PrefixCache::new();
        // a long shared prompt prefix is cached
        c.insert(&[10, 20, 30, 40], 100);
        // a new request shares the first 3 tokens then diverges
        let m = c.longest_prefix_match(&[10, 20, 30, 99, 99]);
        assert_eq!(m.matched_len, 3); // 10,20,30 matched in the trie
        // checkpoint is the deepest stored node on the path; here the only stored
        // node is at depth 4, which is NOT on this path, so checkpoint is root.
        assert_eq!(m.checkpoint_len, 0);
    }

    #[test]
    fn checkpoint_at_intermediate_stored_node() {
        let mut c: PrefixCache<&str> = PrefixCache::new();
        c.insert(&[1, 2], "after_two"); // checkpoint at depth 2
        c.insert(&[1, 2, 3, 4], "after_four"); // deeper sequence shares [1,2]
        // query shares [1,2,3] then diverges → reuse up to the [1,2] checkpoint
        let m = c.longest_prefix_match(&[1, 2, 3, 9]);
        assert_eq!(m.matched_len, 3);
        assert_eq!(m.checkpoint_len, 2);
        assert_eq!(m.value, Some(&"after_two"));
    }

    #[test]
    fn full_match_returns_deepest_checkpoint() {
        let mut c: PrefixCache<&str> = PrefixCache::new();
        c.insert(&[1, 2, 3], "exact");
        let m = c.longest_prefix_match(&[1, 2, 3]);
        assert_eq!(m.matched_len, 3);
        assert_eq!(m.checkpoint_len, 3);
        assert_eq!(m.value, Some(&"exact"));
    }

    #[test]
    fn shared_storage_across_prefixes() {
        let mut c: PrefixCache<u32> = PrefixCache::new();
        c.insert(&[1, 2, 3, 4, 5], 1);
        let before = c.node_count();
        // a sequence sharing the first 4 tokens adds only 1 new node
        c.insert(&[1, 2, 3, 4, 9], 2);
        assert_eq!(c.node_count(), before + 1);
        assert_eq!(c.len(), 2);
    }

    #[test]
    fn no_match_for_disjoint_prefix() {
        let mut c: PrefixCache<&str> = PrefixCache::new();
        c.insert(&[1, 2, 3], "x");
        let m = c.longest_prefix_match(&[9, 9, 9]);
        assert_eq!(m.matched_len, 0);
        assert_eq!(m.value, None);
    }

    #[test]
    fn reinsert_replaces_value() {
        let mut c: PrefixCache<&str> = PrefixCache::new();
        c.insert(&[1], "old");
        c.insert(&[1], "new");
        assert_eq!(c.get(&[1]), Some(&"new"));
        assert_eq!(c.len(), 1); // not double counted
    }

    #[test]
    fn empty_cache_and_query() {
        let c: PrefixCache<&str> = PrefixCache::new();
        assert!(c.is_empty());
        let m = c.longest_prefix_match(&[1, 2, 3]);
        assert_eq!(m.matched_len, 0);
        assert!(m.value.is_none());
    }

    #[test]
    fn serde_round_trip() {
        let mut c: PrefixCache<u32> = PrefixCache::new();
        c.insert(&[1, 2], 7);
        c.insert(&[1, 3], 8);
        let j = serde_json::to_string(&c).unwrap();
        let back: PrefixCache<u32> = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
        assert_eq!(back.get(&[1, 3]), Some(&8));
    }
}
