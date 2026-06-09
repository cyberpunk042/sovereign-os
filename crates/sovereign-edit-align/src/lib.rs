//! `sovereign-edit-align` — not just *how far*, but *what changed*.
//!
//! Edit distance counts the operations that turn one sequence into another;
//! alignment returns the operations *themselves*. That is what you need to
//! highlight a diff, show a spelling correction inline, or break a word-error-rate
//! number down into substitutions, insertions, and deletions. This crate runs the
//! classic edit-distance dynamic program and then **backtraces** through the cost
//! matrix to recover one minimal edit script.
//!
//! Each step of the script is an [`AlignedOp`] tagging an [`EditOp`] — a token
//! kept (`Match`), changed (`Substitute`), added in the target (`Insert`), or
//! dropped from the source (`Delete`) — together with the source and target
//! indices it touches (whichever apply). Reading the ops in order both explains
//! the difference and lets you reconstruct the target from the source.
//!
//! [`align`] works over any `&[T: PartialEq]`; [`align_str`] aligns the characters
//! of two strings; [`summary`] tallies the operation counts (and the substitution
//! count + indels equals the Levenshtein distance).
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the edit-align surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// A single edit operation in an alignment.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EditOp {
    /// The two elements are equal (kept).
    Match,
    /// The source element is replaced by the target element.
    Substitute,
    /// A target element is inserted (no source element).
    Insert,
    /// A source element is deleted (no target element).
    Delete,
}

/// One aligned operation with the indices it relates.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct AlignedOp {
    /// What kind of edit this is.
    pub op: EditOp,
    /// Index into the source sequence, if the op consumes one (`Match`,
    /// `Substitute`, `Delete`).
    pub source: Option<usize>,
    /// Index into the target sequence, if the op consumes one (`Match`,
    /// `Substitute`, `Insert`).
    pub target: Option<usize>,
}

/// Operation tallies of an alignment.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize, Default)]
pub struct Summary {
    /// Number of matched (unchanged) elements.
    pub matches: usize,
    /// Number of substitutions.
    pub substitutions: usize,
    /// Number of insertions.
    pub insertions: usize,
    /// Number of deletions.
    pub deletions: usize,
}

impl Summary {
    /// The Levenshtein distance implied by the alignment (subs + ins + dels).
    pub fn distance(&self) -> usize {
        self.substitutions + self.insertions + self.deletions
    }
}

/// Align two slices, returning a minimal edit script transforming `source` into
/// `target`. Costs are 1 for substitute/insert/delete, 0 for a match.
pub fn align<T: PartialEq>(source: &[T], target: &[T]) -> Vec<AlignedOp> {
    let n = source.len();
    let m = target.len();
    // cost[i][j] = edit distance of source[..i] and target[..j].
    let mut cost = vec![vec![0usize; m + 1]; n + 1];
    for (i, row) in cost.iter_mut().enumerate() {
        row[0] = i;
    }
    for j in 0..=m {
        cost[0][j] = j;
    }
    for i in 1..=n {
        for j in 1..=m {
            let sub_cost = if source[i - 1] == target[j - 1] { 0 } else { 1 };
            cost[i][j] = (cost[i - 1][j - 1] + sub_cost)
                .min(cost[i - 1][j] + 1) // delete
                .min(cost[i][j - 1] + 1); // insert
        }
    }

    // backtrace, preferring diagonal (match/sub) then deletion then insertion.
    let mut ops = Vec::new();
    let (mut i, mut j) = (n, m);
    while i > 0 || j > 0 {
        if i > 0 && j > 0 {
            let sub_cost = if source[i - 1] == target[j - 1] { 0 } else { 1 };
            if cost[i][j] == cost[i - 1][j - 1] + sub_cost {
                ops.push(AlignedOp {
                    op: if sub_cost == 0 {
                        EditOp::Match
                    } else {
                        EditOp::Substitute
                    },
                    source: Some(i - 1),
                    target: Some(j - 1),
                });
                i -= 1;
                j -= 1;
                continue;
            }
        }
        if i > 0 && cost[i][j] == cost[i - 1][j] + 1 {
            ops.push(AlignedOp {
                op: EditOp::Delete,
                source: Some(i - 1),
                target: None,
            });
            i -= 1;
        } else {
            // insertion (j > 0 guaranteed here)
            ops.push(AlignedOp {
                op: EditOp::Insert,
                source: None,
                target: Some(j - 1),
            });
            j -= 1;
        }
    }
    ops.reverse();
    ops
}

/// Align the characters of two strings.
pub fn align_str(source: &str, target: &str) -> Vec<AlignedOp> {
    let a: Vec<char> = source.chars().collect();
    let b: Vec<char> = target.chars().collect();
    align(&a, &b)
}

/// Tally the operations of an alignment.
pub fn summary(ops: &[AlignedOp]) -> Summary {
    let mut s = Summary::default();
    for o in ops {
        match o.op {
            EditOp::Match => s.matches += 1,
            EditOp::Substitute => s.substitutions += 1,
            EditOp::Insert => s.insertions += 1,
            EditOp::Delete => s.deletions += 1,
        }
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Reconstruct the target sequence from the source using the alignment.
    fn reconstruct(source: &[char], target: &[char], ops: &[AlignedOp]) -> Vec<char> {
        let mut out = Vec::new();
        for o in ops {
            match o.op {
                EditOp::Match | EditOp::Substitute => out.push(target[o.target.unwrap()]),
                EditOp::Insert => out.push(target[o.target.unwrap()]),
                EditOp::Delete => { /* source element dropped */ }
            }
        }
        let _ = source;
        out
    }

    #[test]
    fn identical_is_all_matches() {
        let ops = align_str("hello", "hello");
        let s = summary(&ops);
        assert_eq!(s.matches, 5);
        assert_eq!(s.distance(), 0);
        assert!(ops.iter().all(|o| o.op == EditOp::Match));
    }

    #[test]
    fn kitten_to_sitting() {
        // classic: k→s (sub), e→i (sub), insert g → distance 3
        let ops = align_str("kitten", "sitting");
        let s = summary(&ops);
        assert_eq!(s.distance(), 3, "ops {ops:?}");
        assert_eq!(s.substitutions, 2);
        assert_eq!(s.insertions, 1);
        assert_eq!(s.deletions, 0);
    }

    #[test]
    fn reconstruct_target_from_alignment() {
        for (a, b) in [
            ("kitten", "sitting"),
            ("flaw", "lawn"),
            ("", "abc"),
            ("abc", ""),
        ] {
            let av: Vec<char> = a.chars().collect();
            let bv: Vec<char> = b.chars().collect();
            let ops = align(&av, &bv);
            assert_eq!(reconstruct(&av, &bv, &ops), bv, "{a} -> {b}");
        }
    }

    #[test]
    fn pure_insertions_and_deletions() {
        let ins = align_str("ab", "abcd");
        let s = summary(&ins);
        assert_eq!(s.insertions, 2);
        assert_eq!(s.deletions, 0);
        assert_eq!(s.matches, 2);

        let del = align_str("abcd", "ab");
        let s2 = summary(&del);
        assert_eq!(s2.deletions, 2);
        assert_eq!(s2.insertions, 0);
    }

    #[test]
    fn distance_matches_summary() {
        // the alignment's op counts must equal the edit distance
        let ops = align_str("intention", "execution");
        let s = summary(&ops);
        assert_eq!(s.distance(), 5); // known Levenshtein distance
    }

    #[test]
    fn aligned_indices_are_consistent() {
        let ops = align_str("ac", "abc");
        // each Match/Substitute references both indices; Insert only target;
        // Delete only source.
        for o in &ops {
            match o.op {
                EditOp::Match | EditOp::Substitute => {
                    assert!(o.source.is_some() && o.target.is_some());
                }
                EditOp::Insert => assert!(o.source.is_none() && o.target.is_some()),
                EditOp::Delete => assert!(o.source.is_some() && o.target.is_none()),
            }
        }
    }

    #[test]
    fn works_over_word_tokens() {
        // WER-style alignment over word slices
        let a = ["the", "cat", "sat"];
        let b = ["the", "dog", "sat", "down"];
        let ops = align(&a, &b);
        let s = summary(&ops);
        assert_eq!(s.matches, 2); // the, sat
        assert_eq!(s.substitutions, 1); // cat→dog
        assert_eq!(s.insertions, 1); // down
    }

    #[test]
    fn empty_inputs() {
        assert!(align::<char>(&[], &[]).is_empty());
        assert_eq!(summary(&align_str("", "xyz")).insertions, 3);
        assert_eq!(summary(&align_str("xyz", "")).deletions, 3);
    }

    #[test]
    fn serde_round_trip() {
        let ops = align_str("ab", "ac");
        let j = serde_json::to_string(&ops).unwrap();
        let back: Vec<AlignedOp> = serde_json::from_str(&j).unwrap();
        assert_eq!(ops, back);
    }
}
