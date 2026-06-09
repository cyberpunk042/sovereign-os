//! `sovereign-trie` — a prefix trie for completion and prefix routing.
//!
//! When an operator types `/dist` the runtime should offer `/distill`; when a
//! model emits a partial tool name the dispatcher should resolve it by prefix.
//! Both are *prefix* queries, and a trie answers them in time proportional to
//! the query length, not the number of stored words. This crate is that trie:
//! insert words, then ask whether a word is present, whether any word starts
//! with a prefix, or for *all* completions of a prefix.
//!
//! Keys are sequences of Unicode scalar values, so it works on any string.
//! Completions come back sorted for a deterministic, stable autocomplete list.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::collections::BTreeMap;

/// Schema version of the trie surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
struct Node {
    children: BTreeMap<char, Node>,
    is_end: bool,
}

/// A prefix trie of strings.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Trie {
    root: Node,
    len: usize,
}

impl Trie {
    /// An empty trie.
    pub fn new() -> Self {
        Self::default()
    }

    /// Build from an iterator of words.
    pub fn from_words<I, S>(words: I) -> Self
    where
        I: IntoIterator<Item = S>,
        S: AsRef<str>,
    {
        let mut t = Self::new();
        for w in words {
            t.insert(w.as_ref());
        }
        t
    }

    /// Number of distinct words.
    pub fn len(&self) -> usize {
        self.len
    }

    /// Whether the trie has no words.
    pub fn is_empty(&self) -> bool {
        self.len == 0
    }

    /// Insert `word`. Inserting an existing word is a no-op for the count.
    pub fn insert(&mut self, word: &str) {
        let mut node = &mut self.root;
        for c in word.chars() {
            node = node.children.entry(c).or_default();
        }
        if !node.is_end {
            node.is_end = true;
            self.len += 1;
        }
    }

    /// Walk to the node at the end of `prefix`, if it exists.
    fn node_for(&self, prefix: &str) -> Option<&Node> {
        let mut node = &self.root;
        for c in prefix.chars() {
            node = node.children.get(&c)?;
        }
        Some(node)
    }

    /// Whether `word` is stored exactly.
    pub fn contains(&self, word: &str) -> bool {
        self.node_for(word).is_some_and(|n| n.is_end)
    }

    /// Whether any stored word starts with `prefix`.
    pub fn starts_with(&self, prefix: &str) -> bool {
        self.node_for(prefix).is_some()
    }

    /// All stored words that start with `prefix`, sorted.
    pub fn completions(&self, prefix: &str) -> Vec<String> {
        let mut out = Vec::new();
        if let Some(node) = self.node_for(prefix) {
            let mut buf = prefix.to_string();
            collect(node, &mut buf, &mut out);
        }
        out
    }
}

/// Depth-first collect of all words under `node`, appending the current path.
fn collect(node: &Node, buf: &mut String, out: &mut Vec<String>) {
    if node.is_end {
        out.push(buf.clone());
    }
    for (&c, child) in &node.children {
        buf.push(c);
        collect(child, buf, out);
        buf.pop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn t() -> Trie {
        Trie::from_words(["distill", "distinct", "distance", "ingest", "index"])
    }

    #[test]
    fn insert_and_contains() {
        let t = t();
        assert!(t.contains("distill"));
        assert!(t.contains("index"));
        assert!(!t.contains("dist")); // a prefix, not a stored word
        assert!(!t.contains("missing"));
        assert_eq!(t.len(), 5);
    }

    #[test]
    fn duplicate_insert_does_not_grow() {
        let mut t = Trie::new();
        t.insert("a");
        t.insert("a");
        assert_eq!(t.len(), 1);
    }

    #[test]
    fn starts_with_detects_prefixes() {
        let t = t();
        assert!(t.starts_with("dist"));
        assert!(t.starts_with("in"));
        assert!(t.starts_with("distill")); // a full word is its own prefix
        assert!(!t.starts_with("xyz"));
    }

    #[test]
    fn completions_are_sorted_and_complete() {
        let t = t();
        assert_eq!(
            t.completions("dist"),
            vec!["distance", "distill", "distinct"]
        );
        assert_eq!(t.completions("in"), vec!["index", "ingest"]);
    }

    #[test]
    fn completion_of_full_word_includes_itself() {
        let t = t();
        assert_eq!(t.completions("index"), vec!["index"]);
    }

    #[test]
    fn no_completions_for_unknown_prefix() {
        let t = t();
        assert!(t.completions("zzz").is_empty());
    }

    #[test]
    fn empty_prefix_returns_all_words() {
        let t = t();
        let all = t.completions("");
        assert_eq!(all.len(), 5);
        assert!(all.windows(2).all(|w| w[0] <= w[1])); // sorted
    }

    #[test]
    fn works_on_unicode() {
        let mut t = Trie::new();
        t.insert("café");
        t.insert("caña");
        assert!(t.contains("café"));
        assert_eq!(t.completions("ca"), vec!["café", "caña"]);
    }

    #[test]
    fn serde_round_trip() {
        let t = t();
        let j = serde_json::to_string(&t).unwrap();
        let back: Trie = serde_json::from_str(&j).unwrap();
        assert_eq!(t, back);
        assert!(back.contains("distinct"));
    }
}
