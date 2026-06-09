//! `sovereign-line-diff` — line-level diffing via longest common subsequence.
//!
//! When an agent rewrites a file, a runtime (and a human reviewing it) needs to
//! see *what changed*, not the whole new text. This crate computes that: it
//! finds the longest common subsequence of lines between the old and new text
//! and turns it into a sequence of [`DiffLine`]s — each line tagged
//! [`Tag::Equal`], [`Tag::Insert`] (only in the new), or [`Tag::Delete`] (only
//! in the old) — and renders the familiar unified `+`/`-` diff.
//!
//! LCS is the right basis: it produces the *minimal* edit that turns one line
//! sequence into the other, so unchanged regions stay unchanged and only the
//! real edits show. The algorithm is the standard `O(n·m)` dynamic program plus
//! a backtrack; it is deterministic.
//!
//! Standing rule: We do not minimize anything.

#![forbid(unsafe_code)]
#![warn(missing_docs)]

use serde::{Deserialize, Serialize};

/// Schema version of the line-diff surface.
pub const SCHEMA_VERSION: &str = "1.0.0";

/// How a line relates the two texts.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Tag {
    /// Present in both, unchanged.
    Equal,
    /// Added (only in the new text).
    Insert,
    /// Removed (only in the old text).
    Delete,
}

/// One line of a diff.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiffLine {
    /// The line's relationship to the two texts.
    pub tag: Tag,
    /// The line text (without a trailing newline).
    pub text: String,
}

/// Insertion/deletion counts for a diff.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub struct DiffStats {
    /// Lines inserted.
    pub insertions: usize,
    /// Lines deleted.
    pub deletions: usize,
}

/// Compute the line diff from `old` to `new`.
pub fn diff(old: &str, new: &str) -> Vec<DiffLine> {
    let a: Vec<&str> = old.lines().collect();
    let b: Vec<&str> = new.lines().collect();
    let (n, m) = (a.len(), b.len());

    // LCS length table
    let mut dp = vec![vec![0usize; m + 1]; n + 1];
    for i in (0..n).rev() {
        for j in (0..m).rev() {
            dp[i][j] = if a[i] == b[j] {
                dp[i + 1][j + 1] + 1
            } else {
                dp[i + 1][j].max(dp[i][j + 1])
            };
        }
    }

    // backtrack to emit the diff in order
    let mut out = Vec::new();
    let (mut i, mut j) = (0, 0);
    while i < n && j < m {
        if a[i] == b[j] {
            out.push(DiffLine {
                tag: Tag::Equal,
                text: a[i].to_string(),
            });
            i += 1;
            j += 1;
        } else if dp[i + 1][j] >= dp[i][j + 1] {
            out.push(DiffLine {
                tag: Tag::Delete,
                text: a[i].to_string(),
            });
            i += 1;
        } else {
            out.push(DiffLine {
                tag: Tag::Insert,
                text: b[j].to_string(),
            });
            j += 1;
        }
    }
    while i < n {
        out.push(DiffLine {
            tag: Tag::Delete,
            text: a[i].to_string(),
        });
        i += 1;
    }
    while j < m {
        out.push(DiffLine {
            tag: Tag::Insert,
            text: b[j].to_string(),
        });
        j += 1;
    }
    out
}

/// Insertion/deletion counts for a diff.
pub fn stats(d: &[DiffLine]) -> DiffStats {
    DiffStats {
        insertions: d.iter().filter(|l| l.tag == Tag::Insert).count(),
        deletions: d.iter().filter(|l| l.tag == Tag::Delete).count(),
    }
}

/// Whether `old` and `new` have no line-level differences.
pub fn is_unchanged(d: &[DiffLine]) -> bool {
    d.iter().all(|l| l.tag == Tag::Equal)
}

/// Render a unified `+`/`-`/space diff.
pub fn unified(old: &str, new: &str) -> String {
    diff(old, new)
        .iter()
        .map(|l| {
            let prefix = match l.tag {
                Tag::Equal => ' ',
                Tag::Insert => '+',
                Tag::Delete => '-',
            };
            format!("{prefix}{}", l.text)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tags(d: &[DiffLine]) -> Vec<Tag> {
        d.iter().map(|l| l.tag).collect()
    }

    #[test]
    fn identical_text_is_all_equal() {
        let d = diff("a\nb\nc", "a\nb\nc");
        assert!(is_unchanged(&d));
        assert_eq!(tags(&d), vec![Tag::Equal; 3]);
        assert_eq!(
            stats(&d),
            DiffStats {
                insertions: 0,
                deletions: 0
            }
        );
    }

    #[test]
    fn pure_insertion() {
        let d = diff("a\nc", "a\nb\nc");
        assert_eq!(tags(&d), vec![Tag::Equal, Tag::Insert, Tag::Equal]);
        assert_eq!(
            stats(&d),
            DiffStats {
                insertions: 1,
                deletions: 0
            }
        );
        assert_eq!(d[1].text, "b");
    }

    #[test]
    fn pure_deletion() {
        let d = diff("a\nb\nc", "a\nc");
        assert_eq!(tags(&d), vec![Tag::Equal, Tag::Delete, Tag::Equal]);
        assert_eq!(
            stats(&d),
            DiffStats {
                insertions: 0,
                deletions: 1
            }
        );
        assert_eq!(d[1].text, "b");
    }

    #[test]
    fn substitution_is_delete_then_insert() {
        let d = diff("a\nb\nc", "a\nX\nc");
        // unchanged a, then b removed + X added, then unchanged c
        let t = tags(&d);
        assert_eq!(t[0], Tag::Equal);
        assert_eq!(t[t.len() - 1], Tag::Equal);
        assert!(t.contains(&Tag::Delete) && t.contains(&Tag::Insert));
        assert_eq!(
            stats(&d),
            DiffStats {
                insertions: 1,
                deletions: 1
            }
        );
    }

    #[test]
    fn empty_old_is_all_insertions() {
        let d = diff("", "x\ny");
        assert_eq!(tags(&d), vec![Tag::Insert, Tag::Insert]);
        assert_eq!(stats(&d).insertions, 2);
    }

    #[test]
    fn empty_new_is_all_deletions() {
        let d = diff("x\ny", "");
        assert_eq!(tags(&d), vec![Tag::Delete, Tag::Delete]);
        assert_eq!(stats(&d).deletions, 2);
    }

    #[test]
    fn unified_format_has_prefixes() {
        let u = unified("a\nb\nc", "a\nX\nc");
        assert!(u.contains(" a"));
        assert!(u.contains("-b"));
        assert!(u.contains("+X"));
        assert!(u.contains(" c"));
    }

    #[test]
    fn reordered_lines_are_detected_as_edits() {
        let d = diff("a\nb", "b\na");
        // LCS keeps one common line; the other two are an insert+delete
        assert!(!is_unchanged(&d));
        let s = stats(&d);
        assert_eq!(s.insertions + s.deletions, 2);
    }

    #[test]
    fn diffline_serde_round_trip() {
        let d = diff("a\nb", "a\nc");
        let j = serde_json::to_string(&d).unwrap();
        let back: Vec<DiffLine> = serde_json::from_str(&j).unwrap();
        assert_eq!(d, back);
    }
}
