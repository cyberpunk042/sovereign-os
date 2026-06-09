//! `sovereign-completion-cache` — an LRU cache for model completions.
//!
//! Generation in this runtime is deterministic: the same prompt, settings, and
//! seed always produce the same completion. So the same request never needs to
//! run twice — and the cheapest inference of all is the one you don't do. This
//! crate caches completions keyed by the request, turning a repeat into a free
//! lookup (the literal `$0` case).
//!
//! It is a bounded least-recently-used cache: [`get`](CompletionCache::get)
//! returns a cached completion and marks it fresh; [`put`](CompletionCache::put)
//! inserts one, evicting the least-recently-used entry when full. Hit/miss
//! counts are tracked so a runtime can report its cache effectiveness.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, VecDeque};

/// Schema version of the completion-cache surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// FNV-1a 64-bit hash.
fn fnv1a(bytes: &[u8]) -> u64 {
    let mut h: u64 = 0xcbf2_9ce4_8422_2325;
    for &b in bytes {
        h ^= b as u64;
        h = h.wrapping_mul(0x0000_0100_0000_01b3);
    }
    h
}

/// A deterministic request key from a prompt and its generation parameters.
pub fn request_key(prompt: &str, max_new: usize, seed: u64) -> u64 {
    let mut buf = Vec::with_capacity(prompt.len() + 16);
    buf.extend_from_slice(prompt.as_bytes());
    buf.push(0xff); // separator so prompt/param boundary is unambiguous
    buf.extend_from_slice(&(max_new as u64).to_le_bytes());
    buf.extend_from_slice(&seed.to_le_bytes());
    fnv1a(&buf)
}

/// A bounded LRU cache of completions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CompletionCache {
    capacity: usize,
    entries: HashMap<u64, String>,
    /// recency order, least-recent at the front
    order: VecDeque<u64>,
    hits: u64,
    misses: u64,
}

impl CompletionCache {
    /// A cache holding up to `capacity` completions.
    ///
    /// # Panics
    /// Panics if `capacity == 0`.
    pub fn new(capacity: usize) -> Self {
        assert!(capacity > 0, "capacity must be > 0");
        Self {
            capacity,
            entries: HashMap::new(),
            order: VecDeque::new(),
            hits: 0,
            misses: 0,
        }
    }

    /// Number of cached entries.
    pub fn len(&self) -> usize {
        self.entries.len()
    }

    /// Whether the cache is empty.
    pub fn is_empty(&self) -> bool {
        self.entries.is_empty()
    }

    /// Cache hits so far.
    pub fn hits(&self) -> u64 {
        self.hits
    }

    /// Cache misses so far.
    pub fn misses(&self) -> u64 {
        self.misses
    }

    /// Hit rate over all lookups (`0.0` if none).
    pub fn hit_rate(&self) -> f64 {
        let total = self.hits + self.misses;
        if total == 0 {
            0.0
        } else {
            self.hits as f64 / total as f64
        }
    }

    fn touch(&mut self, key: u64) {
        if let Some(pos) = self.order.iter().position(|&k| k == key) {
            self.order.remove(pos);
        }
        self.order.push_back(key);
    }

    /// Look up a completion by key, marking it most-recently-used. Updates
    /// hit/miss stats.
    pub fn get(&mut self, key: u64) -> Option<String> {
        if self.entries.contains_key(&key) {
            self.hits += 1;
            self.touch(key);
            self.entries.get(&key).cloned()
        } else {
            self.misses += 1;
            None
        }
    }

    /// Convenience: look up by `(prompt, max_new, seed)`.
    pub fn get_request(&mut self, prompt: &str, max_new: usize, seed: u64) -> Option<String> {
        self.get(request_key(prompt, max_new, seed))
    }

    /// Insert a completion, evicting the least-recently-used entry if full.
    pub fn put(&mut self, key: u64, completion: impl Into<String>) {
        let existed = self.entries.insert(key, completion.into()).is_some();
        if existed {
            // updated an existing entry → just refresh its recency
            self.touch(key);
            return;
        }
        self.order.push_back(key);
        // a fresh insert may push us over capacity → evict the LRU (front),
        // which is never the key we just appended.
        if self.entries.len() > self.capacity {
            if let Some(evict) = self.order.pop_front() {
                self.entries.remove(&evict);
            }
        }
    }

    /// Convenience: insert by `(prompt, max_new, seed)`.
    pub fn put_request(
        &mut self,
        prompt: &str,
        max_new: usize,
        seed: u64,
        completion: impl Into<String>,
    ) {
        self.put(request_key(prompt, max_new, seed), completion);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn put_then_get_round_trips() {
        let mut c = CompletionCache::new(4);
        c.put(1, "hello");
        assert_eq!(c.get(1).as_deref(), Some("hello"));
        assert_eq!(c.hits(), 1);
        assert_eq!(c.misses(), 0);
    }

    #[test]
    fn miss_returns_none_and_counts() {
        let mut c = CompletionCache::new(4);
        assert_eq!(c.get(99), None);
        assert_eq!(c.misses(), 1);
    }

    #[test]
    fn request_key_is_deterministic_and_param_sensitive() {
        let k1 = request_key("hi", 8, 1);
        let k2 = request_key("hi", 8, 1);
        assert_eq!(k1, k2);
        assert_ne!(k1, request_key("hi", 8, 2)); // seed
        assert_ne!(k1, request_key("hi", 9, 1)); // max_new
        assert_ne!(k1, request_key("ho", 8, 1)); // prompt
    }

    #[test]
    fn request_helpers_round_trip() {
        let mut c = CompletionCache::new(4);
        c.put_request("prompt", 8, 5, "the completion");
        assert_eq!(
            c.get_request("prompt", 8, 5).as_deref(),
            Some("the completion")
        );
        assert_eq!(c.get_request("prompt", 8, 6), None); // different seed
    }

    #[test]
    fn lru_evicts_least_recently_used() {
        let mut c = CompletionCache::new(2);
        c.put(1, "a");
        c.put(2, "b");
        c.put(3, "c"); // evicts key 1 (LRU)
        assert_eq!(c.get(1), None);
        assert_eq!(c.get(2).as_deref(), Some("b"));
        assert_eq!(c.get(3).as_deref(), Some("c"));
        assert_eq!(c.len(), 2);
    }

    #[test]
    fn access_protects_from_eviction() {
        let mut c = CompletionCache::new(2);
        c.put(1, "a");
        c.put(2, "b");
        let _ = c.get(1); // key 1 now most-recent
        c.put(3, "c"); // should evict key 2, not key 1
        assert_eq!(c.get(1).as_deref(), Some("a"));
        assert_eq!(c.get(2), None);
    }

    #[test]
    fn put_existing_updates_without_growing() {
        let mut c = CompletionCache::new(2);
        c.put(1, "a");
        c.put(1, "a2");
        assert_eq!(c.len(), 1);
        assert_eq!(c.get(1).as_deref(), Some("a2"));
    }

    #[test]
    fn hit_rate_reflects_lookups() {
        let mut c = CompletionCache::new(4);
        c.put(1, "x");
        let _ = c.get(1); // hit
        let _ = c.get(2); // miss
        assert!((c.hit_rate() - 0.5).abs() < 1e-9);
    }

    #[test]
    fn serde_round_trip() {
        let mut c = CompletionCache::new(4);
        c.put(1, "a");
        c.put(2, "b");
        let j = serde_json::to_string(&c).unwrap();
        let back: CompletionCache = serde_json::from_str(&j).unwrap();
        assert_eq!(c, back);
    }
}
