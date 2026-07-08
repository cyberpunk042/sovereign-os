//! `sovereign-local-align` — find the best-matching region between two sequences.
//!
//! Global alignment (Needleman-Wunsch) lines up two sequences end to end; that is
//! the wrong tool when one is a short fragment and the other is a long document.
//! To answer *where inside this document does this quote appear, give or take a few
//! edits?* you want **local** alignment: the single contiguous region of highest
//! similarity, ignoring everything before and after it. That is **Smith-Waterman**.
//!
//! It is the global recurrence with one change that makes all the difference: a
//! cell's score is floored at zero. A negative running score resets to zero rather
//! than dragging on, so an alignment can *begin* anywhere, and the best local match
//! is read off by starting the traceback at the highest-scoring cell and walking
//! back until the score returns to zero. The result is the matched span in each
//! sequence, the alignment score, and the operations — matches, mismatches, and
//! gaps — within it.
//!
//! [`align`] works over any slice of comparable tokens (characters, words, ids),
//! so it grounds a generated phrase against source tokens just as well as it does
//! raw text; [`align_str`] is a character-level convenience that also renders the
//! gapped alignment strings. [`Scoring`] sets the match reward and the mismatch and
//! gap penalties. With no positive-scoring region the result is an empty match of
//! score zero.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the local-alignment surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// Scoring scheme: reward for a match, penalties (negative) for mismatch and gap.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct Scoring {
    /// Score added for a matching pair (positive).
    pub match_score: i32,
    /// Score added for a mismatched pair (typically negative).
    pub mismatch: i32,
    /// Score added for a gap (insertion or deletion; typically negative).
    pub gap: i32,
}

impl Default for Scoring {
    fn default() -> Self {
        // a common nucleotide-style scheme; works fine for text too.
        Self {
            match_score: 2,
            mismatch: -1,
            gap: -1,
        }
    }
}

/// One step in a local alignment.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Op {
    /// The aligned tokens are equal.
    Match,
    /// The aligned tokens differ (substitution).
    Mismatch,
    /// A token of the first sequence aligned to a gap (deletion).
    Delete,
    /// A token of the second sequence aligned to a gap (insertion).
    Insert,
}

/// The result of a local alignment: the best-scoring matched region.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct LocalAlignment {
    /// The alignment score of the region.
    pub score: i32,
    /// Half-open span `[start, end)` of the region in the first sequence.
    pub a_range: (usize, usize),
    /// Half-open span `[start, end)` of the region in the second sequence.
    pub b_range: (usize, usize),
    /// The operations across the region, in order.
    pub ops: Vec<Op>,
}

impl LocalAlignment {
    /// Whether the alignment is empty (no positive-scoring region found).
    pub fn is_empty(&self) -> bool {
        self.ops.is_empty()
    }
    /// Number of matching positions in the region.
    pub fn matches(&self) -> usize {
        self.ops.iter().filter(|o| matches!(o, Op::Match)).count()
    }
    /// Length of the aligned region (number of operations).
    pub fn len(&self) -> usize {
        self.ops.len()
    }
    /// Fraction of operations that are exact matches (`0.0` for an empty alignment).
    pub fn identity(&self) -> f64 {
        if self.ops.is_empty() {
            0.0
        } else {
            self.matches() as f64 / self.ops.len() as f64
        }
    }
}

/// Compute the optimal local (Smith-Waterman) alignment of `a` and `b`.
pub fn align<T: PartialEq>(a: &[T], b: &[T], scoring: Scoring) -> LocalAlignment {
    let m = a.len();
    let n = b.len();
    if m == 0 || n == 0 {
        return empty();
    }

    // score matrix h[(m+1)*(n+1)], row-major; h[0][*]=h[*][0]=0.
    let width = n + 1;
    let mut h = vec![0i32; (m + 1) * width];
    let mut best = 0i32;
    let mut best_i = 0usize;
    let mut best_j = 0usize;

    for i in 1..=m {
        for j in 1..=n {
            let s = if a[i - 1] == b[j - 1] {
                scoring.match_score
            } else {
                scoring.mismatch
            };
            let diag = h[(i - 1) * width + (j - 1)] + s;
            let up = h[(i - 1) * width + j] + scoring.gap;
            let left = h[i * width + (j - 1)] + scoring.gap;
            let val = 0.max(diag).max(up).max(left);
            h[i * width + j] = val;
            if val > best {
                best = val;
                best_i = i;
                best_j = j;
            }
        }
    }

    if best == 0 {
        return empty();
    }

    // traceback from the best cell until a zero is reached.
    let mut ops: Vec<Op> = Vec::new();
    let (mut i, mut j) = (best_i, best_j);
    while i > 0 && j > 0 && h[i * width + j] > 0 {
        let cur = h[i * width + j];
        let s = if a[i - 1] == b[j - 1] {
            scoring.match_score
        } else {
            scoring.mismatch
        };
        if cur == h[(i - 1) * width + (j - 1)] + s {
            ops.push(if a[i - 1] == b[j - 1] {
                Op::Match
            } else {
                Op::Mismatch
            });
            i -= 1;
            j -= 1;
        } else if cur == h[(i - 1) * width + j] + scoring.gap {
            ops.push(Op::Delete); // a[i-1] aligned to a gap
            i -= 1;
        } else {
            ops.push(Op::Insert); // b[j-1] aligned to a gap
            j -= 1;
        }
    }
    ops.reverse();

    LocalAlignment {
        score: best,
        a_range: (i, best_i),
        b_range: (j, best_j),
        ops,
    }
}

fn empty() -> LocalAlignment {
    LocalAlignment {
        score: 0,
        a_range: (0, 0),
        b_range: (0, 0),
        ops: Vec::new(),
    }
}

/// A character-level local alignment of two strings, with the gapped alignment
/// rendered (`-` marks a gap).
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct StrAlignment {
    /// The underlying token alignment.
    pub alignment: LocalAlignment,
    /// The first sequence's aligned region, with `-` for gaps.
    pub a_aligned: String,
    /// The second sequence's aligned region, with `-` for gaps.
    pub b_aligned: String,
    /// The matched substring of the first input (no gaps).
    pub a_match: String,
    /// The matched substring of the second input (no gaps).
    pub b_match: String,
}

/// Locally align two strings at the character level.
pub fn align_str(a: &str, b: &str, scoring: Scoring) -> StrAlignment {
    let ac: Vec<char> = a.chars().collect();
    let bc: Vec<char> = b.chars().collect();
    let al = align(&ac, &bc, scoring);

    let mut a_aligned = String::new();
    let mut b_aligned = String::new();
    let (mut ai, mut bi) = (al.a_range.0, al.b_range.0);
    for op in &al.ops {
        match op {
            Op::Match | Op::Mismatch => {
                a_aligned.push(ac[ai]);
                b_aligned.push(bc[bi]);
                ai += 1;
                bi += 1;
            }
            Op::Delete => {
                a_aligned.push(ac[ai]);
                b_aligned.push('-');
                ai += 1;
            }
            Op::Insert => {
                a_aligned.push('-');
                b_aligned.push(bc[bi]);
                bi += 1;
            }
        }
    }
    let a_match: String = ac[al.a_range.0..al.a_range.1].iter().collect();
    let b_match: String = bc[al.b_range.0..al.b_range.1].iter().collect();

    StrAlignment {
        alignment: al,
        a_aligned,
        b_aligned,
        a_match,
        b_match,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn finds_exact_substring() {
        // "TTAC" appears verbatim inside "GATTACA".
        let r = align_str("GATTACA", "TTAC", Scoring::default());
        assert_eq!(r.alignment.score, 8); // 4 matches * 2
        assert_eq!(r.alignment.a_range, (2, 6));
        assert_eq!(r.alignment.b_range, (0, 4));
        assert_eq!(r.a_match, "TTAC");
        assert_eq!(r.b_match, "TTAC");
        assert!((r.alignment.identity() - 1.0).abs() < 1e-9);
    }

    #[test]
    fn locates_quote_in_document() {
        // word-level: find a quote inside a longer document.
        let doc: Vec<&str> = "the quick brown fox jumps over the lazy dog"
            .split(' ')
            .collect();
        let quote: Vec<&str> = "brown fox jumps".split(' ').collect();
        let r = align(&doc, &quote, Scoring::default());
        assert_eq!(r.a_range, (2, 5)); // words "brown fox jumps"
        assert_eq!(r.b_range, (0, 3));
        assert_eq!(r.matches(), 3);
    }

    #[test]
    fn tolerates_one_mismatch() {
        // "TTGC" vs region "TTAC": 3 matches, 1 mismatch.
        let r = align_str("GATTACA", "TTGC", Scoring::default());
        // best region should still span 4 positions with score 3*2 + (-1) = 5.
        assert_eq!(r.alignment.score, 5);
        assert_eq!(r.alignment.matches(), 3);
        assert_eq!(r.a_match, "TTAC");
    }

    #[test]
    fn handles_gaps() {
        // a deletion in the middle: "ACGT" vs "AGT" — best local align with one gap.
        let r = align_str("ACGT", "AGT", Scoring::default());
        // A match(2) + C gap(-1) + G match(2) + T match(2) = 5 ; or skip to GT.
        assert!(r.alignment.score >= 4);
        assert!(r.alignment.matches() >= 2);
        // the aligned strings have equal length.
        assert_eq!(r.a_aligned.chars().count(), r.b_aligned.chars().count());
    }

    #[test]
    fn no_similarity_is_empty() {
        let r = align_str("AAAA", "TTTT", Scoring::default());
        assert_eq!(r.alignment.score, 0);
        assert!(r.alignment.is_empty());
        assert_eq!(r.a_match, "");
        assert_eq!(r.alignment.identity(), 0.0);
    }

    #[test]
    fn empty_inputs() {
        let r = align::<char>(&[], &['a', 'b'], Scoring::default());
        assert!(r.is_empty());
        let r2 = align_str("", "", Scoring::default());
        assert!(r2.alignment.is_empty());
    }

    #[test]
    fn generic_over_integers() {
        let a = [1, 2, 3, 4, 5, 6];
        let b = [3, 4, 5];
        let r = align(&a, &b, Scoring::default());
        assert_eq!(r.a_range, (2, 5));
        assert_eq!(r.b_range, (0, 3));
        assert_eq!(r.score, 6);
    }

    #[test]
    fn aligned_strings_render_gaps() {
        let r = align_str("ACGT", "AGT", Scoring::default());
        // the rendered alignment must contain a gap dash on the b side somewhere.
        assert!(
            r.b_aligned.contains('-') || r.a_aligned.contains('-') || r.alignment.matches() == 3
        );
        // every non-gap char of a_aligned reconstructs a_match.
        let a_no_gap: String = r.a_aligned.chars().filter(|&c| c != '-').collect();
        assert_eq!(a_no_gap, r.a_match);
    }

    #[test]
    fn custom_scoring_changes_result() {
        // with a huge gap penalty, a gapped alignment is avoided.
        let strict = Scoring {
            match_score: 1,
            mismatch: -1,
            gap: -10,
        };
        let r = align_str("ACGT", "AGT", strict);
        // no gap should be opened: the best local match is a contiguous run.
        assert!(!r.a_aligned.contains('-') && !r.b_aligned.contains('-'));
    }

    #[test]
    fn serde_round_trip() {
        let r = align_str("GATTACA", "TTAC", Scoring::default());
        let j = serde_json::to_string(&r).unwrap();
        let back: StrAlignment = serde_json::from_str(&j).unwrap();
        assert_eq!(r, back);
    }

    #[test]
    fn schema_version_is_set() {
        assert_eq!(SCHEMA_VERSION, "1.0.0");
    }
}
