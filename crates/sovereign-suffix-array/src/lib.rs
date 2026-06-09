//! `sovereign-suffix-array` — index every suffix of a text for fast queries.
//!
//! A *suffix array* is the sorted order of all suffixes of a string, stored as
//! their start offsets. Once built, two things become cheap. **Substring search:**
//! every occurrence of a pattern `p` forms a contiguous block in that sorted
//! order, so a pair of binary searches finds the block — and hence the count and
//! all positions — in `O(m log n)`. **Longest repeated substring:** the longest
//! string that occurs at least twice is the maximum *longest-common-prefix*
//! between two adjacent suffixes in the array, which detects the degenerate
//! "the the the…" / copied-paragraph repetition that decoding can fall into.
//!
//! Construction is by **prefix doubling**: rank suffixes by their first
//! character, then repeatedly by their first 2, 4, 8, … characters using the
//! previous ranks, sorting in `O(n log n)` per round for `O(n log² n)` overall —
//! simple, allocation-light, and deterministic. The LCP array is then built in
//! `O(n)` with **Kasai's algorithm**, which walks the suffixes in text order and
//! reuses the previous LCP minus one.
//!
//! Indexing is over **bytes**, so any UTF-8 text works; returned positions are
//! byte offsets, and patterns match their exact byte sequences.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};
use std::cmp::Ordering;

/// Schema version of the suffix-array surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A suffix array over a byte string, plus its LCP array.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SuffixArray {
    text: Vec<u8>,
    /// `sa[i]` is the start offset of the `i`-th suffix in sorted order.
    sa: Vec<usize>,
    /// `lcp[i]` is the longest common prefix of `sa[i-1]` and `sa[i]`
    /// (`lcp[0] == 0`).
    lcp: Vec<usize>,
}

impl SuffixArray {
    /// Build the suffix array (and LCP array) for `text`.
    pub fn new(text: impl Into<Vec<u8>>) -> Self {
        let text = text.into();
        let sa = build_suffix_array(&text);
        let lcp = build_lcp(&text, &sa);
        Self { text, lcp, sa }
    }

    /// The number of suffixes (= text length).
    pub fn len(&self) -> usize {
        self.sa.len()
    }

    /// Whether the indexed text is empty.
    pub fn is_empty(&self) -> bool {
        self.sa.is_empty()
    }

    /// The indexed text bytes.
    pub fn text(&self) -> &[u8] {
        &self.text
    }

    /// The suffix array (suffix start offsets in sorted order).
    pub fn suffixes(&self) -> &[usize] {
        &self.sa
    }

    /// The LCP array.
    pub fn lcp(&self) -> &[usize] {
        &self.lcp
    }

    /// Compare `pattern` against the suffix starting at `pos`, but only over the
    /// pattern's length — i.e. does the suffix *start with* a string ordered like
    /// `pattern`? `Equal` means the suffix begins with `pattern`.
    fn cmp_prefix(&self, pos: usize, pattern: &[u8]) -> Ordering {
        let suffix = &self.text[pos..];
        let take = suffix.len().min(pattern.len());
        match suffix[..take].cmp(&pattern[..take]) {
            Ordering::Equal => {
                if suffix.len() < pattern.len() {
                    // suffix is a strict prefix of pattern → suffix is "smaller"
                    Ordering::Less
                } else {
                    Ordering::Equal
                }
            }
            other => other,
        }
    }

    /// The half-open range `[lo, hi)` of suffix-array indices whose suffixes
    /// start with `pattern`. Empty pattern matches everything.
    fn equal_range(&self, pattern: &[u8]) -> (usize, usize) {
        if pattern.is_empty() {
            return (0, self.sa.len());
        }
        // lower bound: first index where suffix is NOT Less than pattern
        let mut lo = 0usize;
        let mut hi = self.sa.len();
        while lo < hi {
            let mid = (lo + hi) / 2;
            if self.cmp_prefix(self.sa[mid], pattern) == Ordering::Less {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }
        let start = lo;
        // upper bound: first index where suffix is Greater than pattern
        let mut hi2 = self.sa.len();
        let mut lo2 = start;
        while lo2 < hi2 {
            let mid = (lo2 + hi2) / 2;
            if self.cmp_prefix(self.sa[mid], pattern) == Ordering::Greater {
                hi2 = mid;
            } else {
                lo2 = mid + 1;
            }
        }
        (start, lo2)
    }

    /// Whether `pattern` occurs anywhere in the text.
    pub fn contains(&self, pattern: &[u8]) -> bool {
        if pattern.is_empty() {
            return true;
        }
        let (lo, hi) = self.equal_range(pattern);
        lo < hi
    }

    /// The number of occurrences of `pattern` in the text.
    pub fn count(&self, pattern: &[u8]) -> usize {
        let (lo, hi) = self.equal_range(pattern);
        hi - lo
    }

    /// All start offsets where `pattern` occurs, in ascending order.
    pub fn positions(&self, pattern: &[u8]) -> Vec<usize> {
        if pattern.is_empty() {
            return Vec::new();
        }
        let (lo, hi) = self.equal_range(pattern);
        let mut out: Vec<usize> = self.sa[lo..hi].to_vec();
        out.sort_unstable();
        out
    }

    /// The longest substring that occurs at least twice, as a byte slice into
    /// the text (the first such span if several tie). Empty if no repeat exists
    /// (text shorter than 2 or all distinct).
    pub fn longest_repeated_substring(&self) -> &[u8] {
        let mut best_len = 0usize;
        let mut best_pos = 0usize;
        for i in 1..self.lcp.len() {
            if self.lcp[i] > best_len {
                best_len = self.lcp[i];
                best_pos = self.sa[i];
            }
        }
        &self.text[best_pos..best_pos + best_len]
    }
}

/// Prefix-doubling suffix-array construction. Returns suffix start offsets in
/// sorted order. `O(n log² n)`.
fn build_suffix_array(text: &[u8]) -> Vec<usize> {
    let n = text.len();
    if n == 0 {
        return Vec::new();
    }
    let mut sa: Vec<usize> = (0..n).collect();
    // initial rank = byte value
    let mut rank: Vec<i64> = text.iter().map(|&b| b as i64).collect();
    let mut tmp = vec![0i64; n];

    let mut k = 1usize;
    while k < n {
        // sort by (rank[i], rank[i+k]) pairs
        let key = |i: usize| -> (i64, i64) {
            let second = if i + k < n { rank[i + k] } else { -1 };
            (rank[i], second)
        };
        sa.sort_by(|&a, &b| key(a).cmp(&key(b)));

        // recompute ranks from the new order
        tmp[sa[0]] = 0;
        for i in 1..n {
            let prev = sa[i - 1];
            let cur = sa[i];
            tmp[cur] = tmp[prev] + if key(prev) == key(cur) { 0 } else { 1 };
        }
        rank.copy_from_slice(&tmp);

        if rank[sa[n - 1]] as usize == n - 1 {
            break; // all ranks distinct → fully sorted
        }
        k <<= 1;
    }
    sa
}

/// Kasai's `O(n)` LCP construction. `lcp[i]` = LCP of `sa[i-1]` and `sa[i]`.
fn build_lcp(text: &[u8], sa: &[usize]) -> Vec<usize> {
    let n = sa.len();
    let mut lcp = vec![0usize; n];
    if n == 0 {
        return lcp;
    }
    // inverse permutation: rank of each suffix position in sa
    let mut inv = vec![0usize; n];
    for (i, &s) in sa.iter().enumerate() {
        inv[s] = i;
    }
    let mut h = 0usize;
    for i in 0..n {
        if inv[i] > 0 {
            let j = sa[inv[i] - 1];
            while i + h < n && j + h < n && text[i + h] == text[j + h] {
                h += 1;
            }
            lcp[inv[i]] = h;
            h = h.saturating_sub(1);
        } else {
            h = 0;
        }
    }
    lcp
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn suffix_array_is_sorted_order_of_suffixes() {
        let sa = SuffixArray::new("banana");
        // sorted suffixes of "banana": a, ana, anana, banana, na, nana
        // offsets:                     5, 3,   1,     0,      4,  2
        assert_eq!(sa.suffixes(), &[5, 3, 1, 0, 4, 2]);
    }

    #[test]
    fn counts_and_locates_substrings() {
        let sa = SuffixArray::new("banana");
        assert_eq!(sa.count(b"a"), 3);
        assert_eq!(sa.count(b"na"), 2);
        assert_eq!(sa.count(b"ana"), 2);
        assert_eq!(sa.count(b"ban"), 1);
        assert_eq!(sa.count(b"xyz"), 0);
        assert_eq!(sa.positions(b"ana"), vec![1, 3]);
        assert_eq!(sa.positions(b"na"), vec![2, 4]);
    }

    #[test]
    fn contains_matches_naive_search() {
        let text = "the quick brown fox jumps over the lazy dog";
        let sa = SuffixArray::new(text);
        for pat in ["the", "quick", "dog", "over the", "cat", "z d", ""] {
            assert_eq!(
                sa.contains(pat.as_bytes()),
                text.contains(pat),
                "mismatch on '{pat}'"
            );
        }
    }

    #[test]
    fn count_matches_naive_over_many_patterns() {
        let text = "abracadabra abracadabra";
        let sa = SuffixArray::new(text);
        for pat in ["a", "abra", "bra", "cad", "ra a", "z"] {
            let naive = text.matches(pat).count();
            assert_eq!(sa.count(pat.as_bytes()), naive, "count mismatch on '{pat}'");
        }
    }

    #[test]
    fn longest_repeated_substring_basic() {
        // "banana": longest repeat is "ana"
        let sa = SuffixArray::new("banana");
        assert_eq!(sa.longest_repeated_substring(), b"ana");
    }

    #[test]
    fn longest_repeated_detects_degenerate_repetition() {
        // a generation that collapsed into repeating a phrase
        let text = "the model said the model said the model said stop";
        let sa = SuffixArray::new(text);
        let lrs = sa.longest_repeated_substring();
        let lrs_str = std::str::from_utf8(lrs).unwrap();
        assert!(lrs_str.contains("the model said"), "got '{lrs_str}'");
    }

    #[test]
    fn no_repeat_yields_empty() {
        let sa = SuffixArray::new("abcdef");
        assert_eq!(sa.longest_repeated_substring(), b"");
    }

    #[test]
    fn empty_text_is_well_behaved() {
        let sa = SuffixArray::new("");
        assert!(sa.is_empty());
        assert_eq!(sa.len(), 0);
        assert!(!sa.contains(b"x"));
        assert!(sa.contains(b"")); // empty pattern trivially present
        assert_eq!(sa.count(b"a"), 0);
        assert_eq!(sa.longest_repeated_substring(), b"");
    }

    #[test]
    fn lcp_is_consistent_with_adjacent_suffixes() {
        let text = b"mississippi";
        let sa = SuffixArray::new(text.to_vec());
        let suf = sa.suffixes();
        let lcp = sa.lcp();
        for i in 1..suf.len() {
            // recompute LCP of adjacent suffixes naively and compare
            let a = &text[suf[i - 1]..];
            let b = &text[suf[i]..];
            let naive = a.iter().zip(b.iter()).take_while(|(x, y)| x == y).count();
            assert_eq!(lcp[i], naive, "lcp mismatch at {i}");
        }
    }

    #[test]
    fn works_on_multibyte_utf8() {
        let text = "café au lait, café noir";
        let sa = SuffixArray::new(text);
        assert_eq!(sa.count("café".as_bytes()), 2);
        let lrs = std::str::from_utf8(sa.longest_repeated_substring()).unwrap();
        assert!(lrs.contains("café"), "got '{lrs}'");
    }

    #[test]
    fn serde_round_trip() {
        let sa = SuffixArray::new("mississippi");
        let j = serde_json::to_string(&sa).unwrap();
        let back: SuffixArray = serde_json::from_str(&j).unwrap();
        assert_eq!(sa, back);
        assert_eq!(back.count(b"ssi"), 2);
    }
}
